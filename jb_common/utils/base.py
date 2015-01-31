#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2015 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from __future__ import absolute_import, division, unicode_literals
import django.utils.six as six
from django.utils.six.moves import urllib_parse

import codecs, re, os, os.path, time, json, datetime, copy, mimetypes, string
from contextlib import contextmanager
from functools import wraps
from smtplib import SMTPException
from functools import update_wrapper
import dateutil.tz
import django.http
import django.contrib.auth.models
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.apps.registry import apps
from django.conf import settings
from django.utils.encoding import iri_to_uri
from django.forms.util import ErrorList, ValidationError
from django.contrib import messages
from django.core.mail import send_mail
from django.utils import translation
from django.utils.decorators import available_attrs
from django.utils.translation import ugettext_lazy as _, ugettext_lazy, ugettext
from django.utils.functional import allow_lazy
from jb_common import mimeparse


class HttpResponseUnauthorized(django.http.HttpResponse):
    """The response sent back in case of a permission error.  This is another
    missing response class in Django.  I have no clue why they leave out such
    trivial code.
    """
    status_code = 401


class HttpResponseSeeOther(django.http.response.HttpResponseRedirectBase):
    """Response class for HTTP 303 redirects.  Unfortunately, Django does the same
    wrong thing as most other web frameworks: it knows only one type of
    redirect, with the HTTP status code 302.  However, this is very often not
    desirable.  For example, you may experience the use case where an HTTP POST
    request was successful, and you want to redirect the user back to the main
    page.

    This must be done with status code 303, and therefore, this class exists.
    It can simply be used as a drop-in replacement of HttpResponseRedirect.
    """
    status_code = 303

    def __init__(self, redirect_to):
        super(HttpResponseSeeOther, self).__init__(redirect_to)
        self["Location"] = iri_to_uri(redirect_to)


class JSONRequestException(Exception):
    """Exception which is raised if a JSON response was requested and an error in
    the submitted data occured.  This will result in an HTTP 422 response with
    a JSON-encoded :samp:`({error code}, {error message})` body.  For example,
    in a JSON-only view function, you might say::

        if not request.user.is_staff:
            raise JSONRequestException(6, "Only admins can access this ressource.")

    The ranges for the error codes are:

    0–999
        special codes, codes common to all applications, and JuliaBase-common
    1000–1999
        JuliaBase-samples
    2000–2999
        institute-specific extensions to JuliaBase-samples
    3000–3999
        JuliaBase-kicker

    The complete table with the error codes is in the main ``__init__.py`` of
    the respective app.
    """

    def __init__(self, error_number, error_message):
        super(JSONRequestException, self).__init__()
        # If ``error_number`` equals 1, it is a 404.  If it equals 2, it is an
        # error in a web form of a view which is used by both the browser and
        # the JSON client.
        assert error_number > 2
        self.error_number, self.error_message = error_number, error_message


entities = {}
for line in codecs.open(os.path.join(os.path.dirname(__file__), "entities.txt"), encoding="utf-8"):
    if line.strip() and not line.startswith("#"):
        entities[line[:12].rstrip()] = line[12]
entity_pattern = re.compile(r"&[A-Za-z0-9]{2,8};")

def substitute_html_entities(text):
    """Searches for all ``&entity;`` named entities in the input and replaces
    them by their unicode counterparts.  For example, ``&alpha;``
    becomes ``α``.  Escaping is not possible unless you spoil the pattern with
    a character that is later removed.  But this routine doesn't have an
    escaping mechanism.

    :param text: the user's input to be processed

    :type text: unicode

    :return:
      ``text`` with all named entities replaced by single unicode characters

    :rtype: unicode
    """
    result = ""
    position = 0
    while position < len(text):
        match = entity_pattern.search(text, position)
        if match:
            start, end = match.span()
            character = entities.get(text[start + 1:end - 1])
            result += text[position:start] + character if character else text[position:end]
            position = end
        else:
            result += text[position:]
            break
    return result


def get_really_full_name(user):
    """Unfortunately, Django's ``get_full_name`` method for users returns the
    empty string if the user has no first and surname set.  However, it'd be
    sensible to use the login name as a fallback then.  This is realised here.

    :param user: the user instance
    :type user: django.contrib.auth.models.User

    :return:
      The full, human-friendly name of the user

    :rtype: unicode
    """
    return user.get_full_name() or six.text_type(user)


dangerous_markup_pattern = re.compile(r"([^\\]|\A)!\[|[\n\r](-+|=+)\s*$")
def check_markdown(text):
    """Checks whether the Markdown input by the user contains only permitted
    syntax elements.  I forbid images and headings so far.

    :param text: the Markdown input to be checked

    :raises ValidationError: if the ``text`` contained forbidden syntax
        elements.
    """
    if dangerous_markup_pattern.search(text):
        raise ValidationError(_("You mustn't use image and headings syntax in Markdown markup."))


def check_filepath(filepath, default_root, allowed_roots=frozenset(), may_be_directory=False):
    """Test whether a certain file is openable by JuliaBase.

    :param filepath: Path to the file to be tested.  This may be absolute or
      relative.  If empty, this function does nothing.
    :param default_root: If ``filepath`` is relative, this path is prepended to
      it.
    :param allowed_roots: All absolute root paths where ``filepath`` is allowed.
      ``default_root`` is implicitly added to it.
    :param may_be_directory: if ``True``, ``filepath`` may be a readable directory

    :type filepath: str
    :type default_root: str
    :type allowed_roots: iterable of str
    :type may_be_directory: bool

    :return:
      the normalised ``filepath``

    :rtype: str

    :raises ValidationError: if the ``text`` contained forbidden syntax
        elements.
    """
    if filepath:
        def raise_inaccessible_exception():
            raise ValidationError(_("Couldn't open {filename}.").format(filename=filepath))
        filepath = os.path.normpath(filepath)
        assert os.path.isabs(default_root)
        assert all(os.path.isabs(path) for path in allowed_roots)
        default_root = os.path.normpath(default_root)
        allowed_roots = set(os.path.normpath(path) for path in allowed_roots)
        allowed_roots.add(default_root)
        assert all(os.path.isdir(path) for path in allowed_roots)
        absolute_filepath = filepath if os.path.isabs(filepath) else os.path.abspath(os.path.join(default_root, filepath))
        if os.path.isdir(absolute_filepath):
            if not may_be_directory:
                raise_inaccessible_exception()
            absolute_filepath = os.path.join(absolute_filepath, ".")
        if not any(os.path.commonprefix([absolute_filepath, path]) for path in allowed_roots):
            raise ValidationError(_("This file is not in an allowed directory."))
        if not os.path.exists(absolute_filepath):
            raise_inaccessible_exception()
        if os.path.isfile(absolute_filepath):
            try:
                open(absolute_filepath)
            except IOError:
                raise_inaccessible_exception()
        return filepath
    else:
        return ""


def find_file_in_directory(filename, path, max_depth=None):
    """Searches for a file in a directory recursively to a given depth.

    :param filename: The file to be searched for.  Only the basename is
        required.
    :param path: The path from the top level directory where the searching
        starts.
    :param max_depth: The maximum recursion depth; if ``None``, there is no
        limit.

    :type filename: str
    :type path: str
    :type max_depth: int

    :return:
        The relative path to the searched file, or ``None`` if not found.

    :rtype: str
    """
    filename = os.path.basename(filename)
    assert os.path.isdir(path)
    for root, dirs, files in os.walk(path):
        if filename in files:
            return os.path.join(root, filename)
        depth = root[len(path) + len(os.path.sep):].count(os.path.sep)
        if depth == max_depth:
            # prevents further searches in the subdirectories.
            dirs[:] = []


class _AddHelpLink(object):
    """Internal helper class in order to realise the `help_link` function
    decorator.
    """

    def __init__(self, original_view_function, help_link):
        self.original_view_function = original_view_function
        self.help_link = help_link
        update_wrapper(self, original_view_function)

    def __call__(self, request, *args, **kwargs):
        request.juliabase_help_link = self.help_link
        return self.original_view_function(request, *args, **kwargs)


def help_link(link):
    """Function decorator for views functions to set a help link for the view.  The
    help link is embedded into the top line in the layout, see the template
    ``base.html``.  The default template :file:`jb_base.html` prepends
    ``"http://www.juliabase.org/"``.  But you may change that by overriding the
    ``help_link`` block in your own :file:`jb_base.html`.

    :param link: the relative URL to the help page.

    :type link: str
    """

    def decorate(original_view_function):
        return _AddHelpLink(original_view_function, link)

    return decorate


def successful_response(request, success_report=None, view=None, kwargs={}, query_string="", forced=False):
    """After a POST request was successfully processed, there is typically a
    redirect to another page – maybe the main menu, or the page from where the
    add/edit request was started.

    The latter is appended to the URL as a query string with the ``next`` key,
    e.g.::

        /juliabase/5-chamber_deposition/08B410/edit/?next=/juliabase/samples/08B410a

    This routine generated the proper HttpResponse object that contains the
    redirection.  It always has HTTP status code 303 (“see other”).

    :param request: the current HTTP request
    :param success_report: an optional short success message reported to the
        user on the next view
    :param view: the view name/function to redirect to; defaults to the main
        menu page (same when ``None`` is given)
    :param kwargs: group parameters in the URL pattern that have to be filled
    :param query_string: the *quoted* query string to be appended, without the
        leading ``"?"``
    :param forced: If ``True``, go to ``view`` even if a “next” URL is
        available.  Defaults to ``False``.  See `bulk_rename.bulk_rename` for
        using this option to generate some sort of nested forwarding.

    :type request: HttpRequest
    :type success_report: unicode
    :type view: str or function
    :type kwargs: dict
    :type query_string: unicode
    :type forced: bool

    :return:
      the HTTP response object to be returned to the view's caller

    :rtype: HttpResponse
    """
    if success_report:
        messages.success(request, success_report)
    next_url = request.GET.get("next")
    if next_url is not None:
        if forced:
            # FixMe: Pass "next" to the next URL somehow in order to allow for
            # really nested forwarding.  So far, the “deeper” views must know
            # by themselves how to get back to the first one (which is the case
            # for all current JuliaBase views).
            pass
        else:
            # FixMe: So far, the outmost next-URL is used for the See-Other.
            # However, this is wrong behaviour.  Instead, the
            # most-deeply-nested next-URL must be used.  This could be achieved
            # by iterated unpacking.
            return HttpResponseSeeOther(next_url)
    if query_string:
        query_string = "?" + query_string
    # FixMe: Once jb_common has gotten its main menu view, this must be
    # used here as default vor ``view`` instead of the bogus ``None``.
    return HttpResponseSeeOther(django.core.urlresolvers.reverse(view or None, kwargs=kwargs) + query_string)


def unicode_strftime(timestamp, format_string):
    """Formats a timestamp to a string.  Unfortunately, the built-in method
    ``strftime`` of datetime.datetime objects is not unicode-safe.
    Therefore, I have to do a conversion into an UTF-8 intermediate
    representation.  In Python 3.0, this problem is gone.

    :param timestamp: the timestamp to be converted
    :param format_string: The format string that contains the pattern (i.e. all
        the ``"%..."`` sequences) according to which the timestamp should be
        formatted.  Note that if it should be translatable, you mast do this in
        the calling context.

    :type timestamp: datetime.datetime
    :type format_string: unicode

    :return:
      the formatted timestamp, as a Unicode string

    :rtype: unicode
    """
    if six.PY2:
        return timestamp.strftime(format_string.encode("utf-8")).decode("utf-8")
    else:
        return timestamp.strftime(format_string)


def adjust_timezone_information(timestamp):
    """Adds proper timezone information to the timestamp.  It assumes that the
    timestamp has no previous ``tzinfo`` set, but it refers to the
    ``TIME_ZONE`` Django setting.  This is the case with the PostgreSQL backend
    as long as http://code.djangoproject.com/ticket/2626 is not fixed.

    FixMe: This is not tested with another database backend except PostgreSQL.

    :param timestamp: the timestamp whose ``tzinfo`` should be modified

    :type timestamp: datetime.datetime

    :return:
      the timestamp with the correct timezone setting

    :rtype: datetime.datetime
    """
    return timestamp.replace(tzinfo=dateutil.tz.tzlocal())


def send_email(subject, content, recipients, format_dict=None):
    """Sends one email to a user.  Both subject and content are translated to
    the recipient's language.  To make this work, you must tag the original
    text with a dummy ``_`` function in the calling content, e.g.::

        _ = lambda x: x
        send_mail(_("Error notification"), _("An error has occured."), user)
        _ = ugettext

    If you need to use string formatting à la

    ::

        "Hello {name}".format(name=user.name)

    you must pass a dictionary like ``{"name": user.name}`` to this function.
    Otherwise, translating wouldn't work.

    :param subject: the subject of the email
    :param content: the content of the email; it may contain substitution tags
    :param recipients: the recipients of the email
    :param format_dict: the substitions used for the ``format`` string method
        for both the subject and the content

    :type subject: unicode
    :type content: unicode
    :type recipient: django.contrib.auth.models.User or list of
      django.contrib.auth.models.User
    :type format_dict: dict mapping unicode to unicode
    """
    current_language = translation.get_language()
    if not isinstance(recipients, list):
        recipients = [recipients]
    if settings.DEBUG:
        recipients = list(django.contrib.auth.models.User.objects.filter(username=settings.DEBUG_EMAIL_REDIRECT_USERNAME))
    for recipient in recipients:
        translation.activate(recipient.jb_user_details.language)
        subject, content = ugettext(subject), ugettext(content)
        if format_dict is not None:
            subject = subject.format(**format_dict)
            content = content.format(**format_dict)
        cycles_left = 3
        while cycles_left:
            try:
                send_mail(subject, content, settings.DEFAULT_FROM_EMAIL, [recipient.email])
            except SMTPException:
                cycles_left -= 1
                time.sleep(0.3)
            else:
                break
    translation.activate(current_language)


def is_json_requested(request):
    """Tests whether the current request should be answered in JSON format
    instead of HTML.  Typically this means that the request was made by the
    JuliaBase Remote Client or by JavaScript code.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      whether the request should be answered in JSON

    :rtype: bool
    """
    requested_mime_type = mimeparse.best_match(["text/html", "application/xhtml+xml", "application/json"],
                                               request.META.get("HTTP_ACCEPT", "text/html"))
    return requested_mime_type == "application/json"


class JSONEncoder(DjangoJSONEncoder):
    def default(self, o):
        try:
            return float(o)
        except (ValueError, TypeError):
            try:
                return list(o)
            except (ValueError, TypeError):
                try:
                    return super(JSONEncoder, self).default(o)
                except (ValueError, TypeError):
                    return six.text_type(o)


def respond_in_json(value):
    """The communication with the JuliaBase Remote Client or to AJAX clients
    should be done without generating HTML pages in order to have better
    performance.  Thus, all responses are Python objects, serialised in JSON
    notation.

    The views that can be accessed by the Remote Client/AJAX as well as normal
    browsers should distinguish between both by using `is_json_requested`.

    :param value: the data to be sent back to the client that requested JSON.

    :type value: ``object`` (an arbitrary Python object)

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    return django.http.JsonResponse(value, JSONEncoder, safe=False)


all_models = None
def get_all_models(app_label=None):
    """Returns all model classes of all apps, including registered abstract
    ones.  The resulting data structure is a dictionary which maps the class
    names to the model classes.  Note that every app must have a ``models.py``
    module.  This ``models.py`` may be empty, though.

    :param app_label: the name of the app whose models should be returned

    :type app_label: unicode

    :return:
      all models of all apps

    :rtype: dict mapping str to ``class``
    """
    global all_models, abstract_models
    if app_label:
        result = dict((model.__name__, model) for model in apps.get_app_config(app_label).get_models())
        result.update((model.__name__, model) for model in abstract_models if model._meta.app_label == app_label)
        return result
    if all_models is None:
        abstract_models = frozenset(abstract_models)
        all_models = dict((model.__name__, model) for model in apps.get_models())
        all_models.update((model.__name__, model) for model in abstract_models)
    return all_models.copy()


abstract_models = set()
def register_abstract_model(abstract_model):
    """Register an abstract model class.  This way, it is returned by
    `get_all_models`.  In particular, it means that the model can be search for
    in the advanced search.

    :param abstract_model: the abstract model class to be registered

    :type abstract_model: ``class```
    """
    abstract_models.add(abstract_model)


def is_update_necessary(destination, source_files=[], timestamps=[], additional_inaccuracy=0):
    """Returns whether the destination file needs to be re-created from the
    sources.  It bases of the timestamps of last file modification.  If the
    union of `source_files` and `timestamps` is empty, the function returns
    ``False``.

    :param destination: the path to the destination file
    :param source_files: the paths of the source files
    :param timestamps: timestamps of non-file source objects
    :param additional_inaccuracy: When comparing file timestamps across
        computers, there may be trouble due to inaccurate clocks or filesystems
        where the modification timestamps have an accuracy of only 2 seconds
        (some Windows FS'es).  Set this parameter to a positive number to avoid
        this.  Note that usually, JuliaBase *copies* *existing* timestamps, so
        inaccurate clocks should not be a problem.

    :type destination: unicode
    :type source_files: list of unicode
    :type timestamps: list of datetime.datetime
    :type additional_inaccuracy: int or float

    :return:
      whether the destination file needs to be updated

    :rtype: bool

    :raises OSError: if one of the source paths is not found
    """
    all_timestamps = copy.copy(timestamps)
    all_timestamps.extend(datetime.datetime.fromtimestamp(os.path.getmtime(filename)) for filename in source_files)
    if not all_timestamps:
        return False
    # The ``+1`` is for avoiding false positives due to floating point
    # inaccuracies.
    return not os.path.exists(destination) or \
        datetime.datetime.fromtimestamp(os.path.getmtime(destination) + additional_inaccuracy + 1) < max(all_timestamps)


def format_lazy(string, *args, **kwargs):
    """Implements a lazy variant of the ``format`` string method.  For
    example, you might say::

        verbose_name = format_lazy(_(u"Raman {0} measurement"), 1)

    Here, “``_``” is ``ugettext_lazy``.
    """
    return string.format(*args, **kwargs)
# Unfortunately, ``allow_lazy`` doesn't work as a real Python decorator, for
# whatever reason.
format_lazy = allow_lazy(format_lazy, six.text_type)


def static_file_response(filepath, served_filename=None):
    """Serves a file of the local file system.

    :param filepath: the absolute path to the file to be served
    :param served_filename: the filename the should be transmitted; if given,
        the response will be an "attachment"

    :return:
      the HTTP response with the static file

    :rype: ``django.http.HttpResponse``
    """
    response = django.http.HttpResponse()
    if not settings.USE_X_SENDFILE:
        response.write(open(filepath, "rb").read())
    response["X-Sendfile"] = filepath
    response["Content-Type"] = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    response["Content-Length"] = os.path.getsize(filepath)
    if served_filename:
        response["Content-Disposition"] = 'attachment; filename="{0}"'.format(served_filename)
    return response


def mkdirs(path):
    """Creates a directory and all of its parents if necessary.  If the given
    path doesn't end with a slash, it's interpreted as a filename and removed.
    If the directory already exists, nothing is done.  (In particular, no
    exception is raised.)

    :param path: absolute path which should be created

    :type path: str
    """
    try:
        os.makedirs(os.path.dirname(path))
    except OSError:
        pass


@contextmanager
def cache_key_locked(key):
    """Locks the ``key`` in the cache.  If ``key`` already exists, it waits for
    max. 6 seconds.  If it's still not released, the whole cache is cleared.
    In all cases, ``key`` is hold in the context.  After the context is left
    (even via an exception), the key is deleted, i.e. the lock is removed.  Use
    it like this::

        with cache_key_locked("my_lock_name"):
            ...
    """
    cycles = 20
    while cycles:
        if cache.add(key, 1):
            break
        cycles -= 1
        time.sleep(0.3)
    else:
        cache.clear()
        successful = cache.add(key, 1)
        assert successful
    try:
        yield
    finally:
        cache.delete(key)


class MyNone:
    """Singleton class for detecting cache misses in `get_from_cache`
    reliably.
    """
    pass

my_none = MyNone()


def _incr_cache_item(key, increment):
    """Internal routine for incrementing a cache value, or creating it if
    non-existing.
    """
    try:
        cache.incr(key, increment)
    except ValueError:
        cache.add(key, increment)


def get_from_cache(key, default=None, hits=1, misses=1):
    """Gets an item from the cache and records statistics for
    `cache_hit_rate`.  The semantics of this routine are the same as for
    Django's `cache.get`.  So, you can use it as a drop-in replacement for it.

    With `hits` and `misses` you can set the number of hits and misses that
    should be equivalent with this cache access.  For example, if you fetch a
    very expensive objects like a sample, you may set them to a high values.
    However, if it fails, `misses` should still be small for samples because
    the generation of processes will call this method itself anyway.
    """
    result = cache.get(key, my_none)
    if result is my_none:
        _incr_cache_item("samples-cache-misses", misses)
        return default
    else:
        _incr_cache_item("samples-cache-hits", hits)
        return result


def cache_hit_rate():
    """Returns the current cache hit rate.  This value is between 0 and 1.  It
    returns ``None`` is no such value could be calculated.

    :return:
      the hit rate, or ``None`` if neither hits nor misses have been recorded

    :rtype: float or NoneType
    """
    hits = cache.get("samples-cache-hits", 0)
    misses = cache.get("samples-cache-misses", 0)
    if hits + misses == 0:
        return None
    else:
        return hits / (hits + misses)


def unlazy_object(lazy_object):
    """Returns the actual (wrapped) instance of a lazy object.  Note that the
    lazy object may be changed by this function: Afterwards, it definitely
    contains the wrapped instance.

    :param lazy_object: the lazy object

    :type lazy_object: django.utils.functional.LazyObject

    :return:
      the actual object

    :rtype: object
    """
    if lazy_object._wrapped is None:
        lazy_object._setup()
    return lazy_object._wrapped


def convert_bytes_to_str(byte_array):
    """Converts an array of bytes representing the string literals as decimal
    integers to unicode letters.

    :param byte_array: list of integers representing unicode codes.

    :type byte_array: list of int

    :return:
        the unicode string

    :rtype: unicode
    """
    try:
        return "".join(map(unichr, byte_array)).strip()
    except ValueError:
        return ""


def convert_bytes_to_bool(byte_array):
    """Converts an array of bytes to  booleans.

    :param byte_array: list of integers (1 or 0).

    :type byte_array: list of int

    :return:
     a tuple with True or False values

    :rtype: tuple of boolean
    """
    return tuple(True if byte else False for byte in byte_array)


def format_enumeration(items):
    """Generates a pretty-printed enumeration of all given names.  For
    example, if the list contains ``["a", "b", "c"]``, it yields ``"a, b, and
    c"``.

    :param items: iterable of names to be put into the enumeration

    :type items: iterable of unicode

    :return:
      human-friendly enumeration of all names

    :rtype: unicode
    """
    items = sorted(six.text_type(item) for item in items)
    if len(items) > 2:
        # Translators: Intended as a separator in an enumeration of three or more items
        return _(", ").join(items[:-1]) + _(", and ") + items[-1]
    elif len(items) == 2:
        # Translators: Intended to be used in an enumeration of exactly two items
        return _(" and ").join(items)
    else:
        return "".join(items)


def unquote_view_parameters(view):
    """Decorator for view functions with URL-quoted parameters.  Using this
    decorator unquotes the values of all but the ``request`` parameter.  Mind
    the ordering: All decorators *after* this one in the source get the
    unquoted parameters.

    :param view: the view function

    :type view: function
    """
    # FixMe: Actually, percent-encoding "/" and "%" is enough.
    @wraps(view, assigned=available_attrs(view))
    def unquoting_view(request, *args, **kwargs):
        if six.PY2:
            return view(request,
                        *[urllib_parse.unquote(six.binary_type(value)).decode("utf-8") for value in args],
                        **dict((key, urllib_parse.unquote(six.binary_type(value)).decode("utf-8"))
                               for key, value in kwargs.items()))
        return view(request,
                    *[urllib_parse.unquote(value) for value in args],
                    **dict((key, urllib_parse.unquote(value)) for key, value in kwargs.items()))
    return unquoting_view


def int_or_zero(number):
    """Converts ``number`` to an integer.  If this doesn't work, return ``0``.

    :param number: a string that is supposed to contain an integer number

    :type number: str or unicode or NoneType

    :return:
      the ``int`` representation of ``number``, or 0 if it didn't represent a
      valid integer number

    :rtype: int
    """
    try:
        return int(number)
    except (ValueError, TypeError):
        return 0


def camel_case_to_underscores(name):
    """Converts a CamelCase identifier to one using underscores.  For example,
    ``"MySamples"`` is converted to ``"my_samples"``, and ``"PDSMeasurement"``
    to ``"pds_measurement"``.

    :param name: the camel-cased identifier

    :type name: str

    :return:
      the identifier in underscore notation

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i > 0 and character in string.ascii_uppercase + string.digits and (
            (i + 1 < len(name) and name[i + 1] not in string.ascii_uppercase + string.digits) or
            (name[i - 1] not in string.ascii_uppercase + string.digits)):
            result.append("_")
        result.append(character.lower())
    return "".join(result)


def camel_case_to_human_text(name):
    """Converts a CamelCase identifier to one intended to be read by humans.
    For example, ``"MySamples"`` is converted to ``"my samples"``, and
    ``"PDSMeasurement"`` to ``"PDS measurement"``.

    :param name: the camel-cased identifier

    :type name: str

    :return:
      the pretty-printed identifier

    :rtype: str
    """
    result = []
    for i, character in enumerate(name):
        if i > 0 and character in string.ascii_uppercase and (
            (i + 1 < len(name) and name[i + 1] not in string.ascii_uppercase) or
            (name[i - 1] not in string.ascii_uppercase)):
            result.append(" ")
        result.append(character if i + 1 >= len(name) or name[i + 1] in string.ascii_uppercase else character.lower())
    return "".join(result)


def remove_file(path):
    """Removes the file.  If the file didn't exist, this is a no-op.

    :param path: absolute path to the file to be removed

    :type path: str

    :return:
      whether the file was removed; if ``False``, it hadn't existed

    :rtype: bool
    """
    try:
        os.remove(path)
    except OSError:
        return False
    else:
        return True


def capitalize_first_letter(text):
    """Capitalise the first letter of the given string.

    :param text: text whose first letter should be capitalised

    :type text: unicode

    :return:
      the text with capitalised first letter

    :rtype: unicode
    """
    # FixMe: Remove this function in favour of django.utils.text.capfirst.
    if text:
        return text[0].upper() + text[1:]
    else:
        return ""


def round(value, digits):
    """Method for rounding a numeric value to a fixed number of significant
    digits.

    :param value: the numeric value
    :param digit: number of significant digits

    :type value: float
    :type digits: int

    :return:
        rounded value

    :rtype: str
    """
    try:
        value = float(value)
    except (ValueError, TypeError):
        pass
    else:
        try:
            digits = int(digits)
        except (ValueError, TypeError):
            pass
        else:
            return "{{0:.{0}g}}".format(digits).format(value)


def sorted_users(users):
    """Return a list of users sorted by family name.  In particular, it sorts
    case-insensitively.

    :param users: the users to be sorted; it may also be a QuerySet

    :type users: an iterable of django.contrib.auth.models.User

    :return:
      the sorted users

    :rtype: list of django.contrib.auth.models.User
    """
    return sorted(users, key=lambda user: user.last_name.lower() if user.last_name else user.username)


def sorted_users_by_first_name(users):
    """Return a list of users sorted by first name.  In particular, it sorts
    case-insensitively.

    :param users: the users to be sorted; it may also be a QuerySet

    :type users: an iterable of django.contrib.auth.models.User

    :return:
      the sorted users

    :rtype: list of django.contrib.auth.models.User
    """
    return sorted(users, key=lambda user: user.first_name.lower() if user.first_name else user.username)


_ = lambda s: s
_permissions = {"add": ("add_{class_name}", _("Can add {class_name}")),
                "change": ("change_{class_name}", _("Can edit every {class_name}")),
                "view_every": ("view_every_{class_name}", _("Can view every {class_name}")),
                "edit_permissions": ("edit_permissions_for_{class_name}", _("Can edit permissions for {class_name}"))}
_ = ugettext_lazy

def generate_permissions(permissions, class_name):
    """Auto-generates model permissions.  It may be used in physical process
    classes – but not only there – like this::

        class Meta(samples.models.PhysicalProcess.Meta):
            permissions = generate_permissions(
                {"add", "change", "view_every", "edit_permissions"}, "ModelClassName")


    :param permissions: The permissions to generate.  Possible values are
      ``"add"``, ``"change"``, ``"view_every"``, and ``"edit_permissions"``.
    :param class_name: python class name of the model class,
      e.g. ``"LayerThicknessMeasurement"``.

    :type permissions: set of unicode
    :type class_name: str

    :return:
      the permissions tuple

    :rtype: tuple of (unicode, unicode)
    """
    class_name_lower = class_name.lower()
    class_name_human = camel_case_to_human_text(class_name)
    max_length = django.contrib.auth.models.Permission._meta.get_field("name").max_length - len("Can edit permissions for ''")
    if len(class_name_human) > max_length:
        class_name_human = class_name_human[:max_length - 1] + "…"
    class_name_human = "'{}'".format(class_name_human)
    result = []
    for permission in permissions:
        codename, name = _permissions[permission]
        codename = codename.format(class_name=class_name_lower)
        name = name.format(class_name=class_name_human)
        result.append((codename, name))
    return tuple(result)


_ = ugettext
