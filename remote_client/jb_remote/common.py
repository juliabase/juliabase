#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, the samples database.
#
# Copyright © 2008–2014 Forschungszentrum Jülich, Germany,
#                       Marvin Goblet <m.goblet@fz-juelich.de>,
#                       Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

from __future__ import absolute_import, unicode_literals, division
from . import six
from .six.moves import urllib, http_cookiejar, _thread

import mimetypes, json, logging, os, datetime, time, random, re
from io import IOBase
if six.PY3:
    file = IOBase

from . import settings


def setup_logging(destination=None):
    """If the user wants to call this in order to enable logging, he must do
    so before logging in.  Note that it is a no-op if called a second time.
    """
    # This is not totally clean because it doesn't guarantee that logging is
    # properly configured *before* the first log message is generated but I'm
    # pretty sure that this is the case.  The clean solution would involve more
    # boilerplate code for the end-user, which I don't want, or replacing all
    # ``logging.info`` etc. calls with an own wrapper.
    if destination == "file":
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)-8s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            filename="/tmp/jb_remote.log" if os.path.exists("/tmp") else "jb_remote.log",
                            filemode="w")
    elif destination == "console":
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)-8s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    else:
        class LogSink(object):
            def write(self, *args, **kwargs):
                pass
            def flush(self, *args, **kwargs):
                pass
        logging.basicConfig(stream=LogSink())


def clean_header(value):
    """Makes a scalar value fit for being used in POST data.  Note that
    booleans with the value ``False`` are excluded from the POST dictionary by
    returning ``None``.  This mimics HTML's behaviour then ``False`` values in
    forms are “not successful”.
    """
    if isinstance(value, bool):
        return "on" if value else None
    elif isinstance(value, file):
        return value
    else:
        if six.PY2:
            return unicode(value).encode("utf-8")
        else:
            return str(value)


def comma_separated_ids(ids):
    return ",".join(str(id_) for id_ in ids)


def double_urlquote(string):
    """Returns a double-percent-quoted string.  This mimics the behaviour of
    Django, which quotes every URL retrieved by
    ``django.core.urlresolvers.resolve``.  Because it does not quote the slash
    “/” for obvious reasons, I have to quote sample names, sample series names,
    deposition numbers, and non-int process “identifying fields” *before* they
    are fed into ``resolve`` (and quoted again).
    """
    return urllib.parse.quote(urllib.parse.quote(string, safe=""))


def parse_timestamp(timestamp):
    """Convert a timestamp coming from the server to a Python `datetime` object.
    The server serialises with the `DjangoJSONEncoder`, which in turn uses the
    ``.isoformat()`` method.  As long as the server does not handle
    timezone-aware timestamps (i.e., ``USE_TZ=False``), this works.

    :param timestamp: the timestamp to parse, coming from the server.  It must
        have ISO 8601 format format without timezone information.

    :type timestamp: str

    :return:
      the timestamp as a Python datetime object

    :rtype: datetime.datetime
    """
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S" + (".%f" if "." in timestamp else ""))


def format_timestamp(timestamp):
    """Serializses a timestamp.  This is the counter function to `parse_timestamp`,
    however, there is an asymmetry: Here, we don't generate ISO 8601 timestamps
    (with the ``"T"`` inbetween).  The reason is that Django's `DateTimeField`
    would not be able to parse it.

    :param timestamp: the timestamp to format

    :type timestamp: datetime.datetime

    :return:
      the timestamp in the format “YYYY-MM-DD HH:MM:SS”.

    :rtype: str
    """
    try:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def python_2_unicode_compatible(klass):
    """Taken from Django 1.7.  See
    https://github.com/django/django/blob/master/LICENSE for the license.

    A decorator that defines __unicode__ and __str__ methods under Python 2.
    Under Python 3 it does nothing.

    To support Python 2 and 3 with a single code base, define a __str__ method
    returning text and apply this decorator to the class.
    """
    if six.PY2:
        if '__str__' not in klass.__dict__:
            raise ValueError("@python_2_unicode_compatible cannot be applied "
                             "to %s because it doesn't define __str__()." %
                             klass.__name__)
        klass.__unicode__ = klass.__str__
        klass.__str__ = lambda self: self.__unicode__().encode('utf-8')
    return klass


# The following is taken from Python2's mimetools.py.  FixMe: Find a better way
# to have the functionality of ``encode_multipart_formdata()``.  See
# <http://stackoverflow.com/questions/680305>.

_counter_lock = _thread.allocate_lock()

_counter = 0
def _get_next_counter():
    global _counter
    _counter_lock.acquire()
    _counter += 1
    result = _counter
    _counter_lock.release()
    return result

_prefix = None

def choose_boundary():
    """Return a string usable as a multipart boundary.

    The string chosen is unique within a single program run, and
    incorporates the user id (if available), process id (if available),
    and current time.  So it's very unlikely the returned string appears
    in message text, but there's no guarantee.

    The boundary contains dots so you have to quote it in the header.
    """
    global _prefix
    if _prefix is None:
        import socket
        try:
            hostid = socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            hostid = "127.0.0.1"
        try:
            uid = repr(os.getuid())
        except AttributeError:
            uid = "1"
        try:
            pid = repr(os.getpid())
        except AttributeError:
            pid = "1"
        _prefix = "{}.{}.{}".format(hostid, uid, pid)
    return "{}.{:.3f}.{}".format(_prefix, time.time(), _get_next_counter())

# End of taken from Python2's mimetools.py.

def encode_multipart_formdata(data):
    """Generates content type and body for an HTTP POST request.  It can also
    handle file uploads: For them, the value of the item in ``data`` is an open
    file object.  Taken from <http://code.activestate.com/recipes/146306/#c5>.

    :param data: the POST data; it must not be ``None``

    :type data: dict mapping unicode to unicode, int, float, bool, file, or
      list

    :return:
      the content type, the HTTP body

    :rtype: str, str
    """
    def get_content_type(filename):
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"

    non_file_items = []
    file_items = []
    for key, value in data.items():
        if isinstance(value, file):
            file_items.append((key, value))
        else:
            if isinstance(value, list):
                for single_value in value:
                    non_file_items.append((key, single_value))
            else:
                non_file_items.append((key, value))
    # Otherwise, we would have to implement multipart/mixed, see
    # http://www.w3.org/TR/html401/interact/forms.html#h-17.13.4.2
    assert len(file_items) <= 1
    if not file_items:
        return "application/x-www-form-urlencoded", urllib.parse.urlencode(data, doseq=True).encode("utf-8")
    boundary = choose_boundary()
    lines = []
    for key, value in non_file_items:
        lines.append("--" + boundary)
        lines.append('Content-Disposition: form-data; name="{0}"'.format(key))
        lines.append("Content-Type: text/plain; charset=utf-8")
        lines.append("")
        lines.append(value)
    if file_items:
        key, value = file_items[0]
        lines.append("--" + boundary)
        filename = os.path.basename(value.name)
        lines.append('Content-Disposition: form-data; name="{0}"; filename="{1}"'.format(key, filename))
        lines.append("Content-Type: {0}".format(get_content_type(filename)))
        lines.append("Content-Transfer-Encoding: binary")
        lines.append("")
        lines.append(value.read())
    lines.append("--" + boundary + "--")
    lines.append("")
    body = "\r\n".join(lines)
    content_type = "multipart/form-data; boundary={0}".format(boundary)
    return content_type, body


@python_2_unicode_compatible
class JuliaBaseError(Exception):
    """Exception class for high-level JuliaBase errors.

    :ivar error_code: The numerical error code.  See :py:mod:`jb_common.utils`
      for further information, and the root ``__init__.py`` file of the various
      JuliaBase apps for the tables with the error codes.

    :ivar error_message: A description of the error.  If `error_code` is ``1``, it
      contains the URL to the error page (without the domain name).

    :type error_code: int
    :type error_message: unicode
    """

    def __init__(self, error_code, message):
        self.error_code, self.error_message = error_code, message

    def __str__(self):
        return "({0}) {1}".format(self.error_code, self.error_message)


class JuliaBaseConnection(object):
    """Class for the routines that connect to the database at HTTP level.
    This is a singleton class, and its only instance resides at top-level in
    this module.
    """
    cookie_jar = http_cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    http_headers = [("User-agent", "JuliaBase-Remote/0.1"),
                    ("X-requested-with", "XMLHttpRequest"),
                    ("Accept", "application/json,text/html;q=0.9,application/xhtml+xml;q=0.9,text/*;q=0.8,*/*;q=0.7")]
    opener.addheaders = http_headers

    def __init__(self):
        self.username = None
        self.root_url = None

    def _do_http_request(self, url, data=None):
        logging.debug("{0} {1!r}".format(url, data))
        if data is None:
            request = urllib.request.Request(url)
        else:
            content_type, body = encode_multipart_formdata(data)
            headers = {"Content-Type": content_type, "Referer": url}
            request = urllib.request.Request(url, body, headers)
        max_cycles = 10
        while max_cycles > 0:
            max_cycles -= 1
            try:
                return self.opener.open(request)
            except urllib.error.HTTPError as error:
                if error.code in [404, 422] and error.info()["Content-Type"].startswith("application/json"):
                    error_code, error_message = json.loads(error.read().decode("utf-8"))
                    raise JuliaBaseError(error_code, error_message)
                server_error_message = error.read().decode("utf-8")
                error.msg = "{}\n\n{}".format(error.msg, server_error_message)
                if six.PY2:
                    error.msg = error.msg.encode("utf-8")
                raise error
            except urllib.error.URLError:
                if max_cycles == 0:
                    logging.error("Request failed.")
                    raise
            time.sleep(3 * random.random())

    def open(self, relative_url, data=None, response_is_json=True):
        """Do an HTTP request with the JuliaBase server.  If ``data`` is not
        ``None``, its a POST request, and GET otherwise.

        :param relative_url: the non-domain part of the URL, for example
            ``"/samples/10-TB-1"``.  “Relative” may be misguiding here: only
            the domain is omitted.
        :param data: the POST data, or ``None`` if it's supposed to be a GET
            request.
        :param response_is_json: whether the content type of the response must
            be JSON

        :type relative_url: str
        :type data: dict mapping unicode to unicode, int, float, bool, file, or
          list
        :type response_is_json: bool

        :return:
          the response to the request

        :rtype: ``object``

        :raises JuliaBaseError: if JuliaBase couldn't fulfill the request
            because it contained errors.  For example, you requested a sample
            that doesn't exist, or the transmitted measurement data was
            incomplete.
        :raises urllib.error.URLError: if a lower-level error occured, e.g. the
            HTTP connection couldn't be established.
        """
        if not self.root_url:
            raise Exception("No root URL defined.  Maybe not logged-in?")
        if data is not None:
            cleaned_data = {}
            for key, value in data.items():
                key = clean_header(key)
                if value is not None:
                    if not isinstance(value, list):
                        cleaned_header = clean_header(value)
                        if cleaned_header:
                            cleaned_data[key] = cleaned_header
                    else:
                        cleaned_list = [clean_header(item) for item in value if value is not None]
                        if cleaned_list:
                            cleaned_data[key] = cleaned_list
            response = self._do_http_request(self.root_url + relative_url, cleaned_data)
        else:
            response = self._do_http_request(self.root_url + relative_url)
        if response_is_json:
            assert response.info()["Content-Type"].startswith("application/json")
            return json.loads(response.read().decode("utf-8"))
        else:
            return response.read()

    def set_csrf_header(self):
        csrf_cookies = {cookie for cookie in self.cookie_jar if cookie.name == "csrftoken"}
        if csrf_cookies:
            assert len(csrf_cookies) == 1
            self.opener.addheaders = self.http_headers + [("X-CSRFToken", csrf_cookies.pop().value)]

    def login(self, root_url, username, password):
        self.root_url = root_url
        self.username = username
        # First, a GET request to get the CSRF cookie used only for the
        # following POST request.
        self.open("login_remote_client")
        self.set_csrf_header()
        self.open("login_remote_client", {"username": username, "password": password})
        # Now, set the CSRF token for the rest of the communication.
        self.set_csrf_header()

    def logout(self):
        self.open("logout_remote_client")
        self.username = self.root_url = None

connection = JuliaBaseConnection()


def login(username, password, testserver=False):
    """Logins to JuliaBase.

    :param username: the username used to log in
    :param password: the user's password
    :param testserver: whether the testserver should be user.  If ``False``, the
        production server is used.

    :type username: unicode
    :type password: unicode
    :type testserver: bool
    """
    setup_logging()
    if testserver:
        logging.info("Logging into the testserver.")
        connection.login(settings.TESTSERVER_ROOT_URL, username, password)
    else:
        connection.login(settings.ROOT_URL, username, password)
    logging.info("Successfully logged-in as {0}.".format(username))


def logout():
    """Logs out of JuliaBase.
    """
    connection.logout()
    logging.info("Successfully logged-out.")


class PrimaryKeys(object):
    """Dictionary-like class for storing primary keys.  I use this class only
    to delay the costly loading of the primary keys until they are really
    accessed.  This way, GET-request-only usage of the Remote Client becomes
    faster.  It is a singleton.

    :ivar components: set of types of primary keys that should be fetched.  For
        example, it may contain ``"external_operators=*"`` if all external
        operator's primary keys should be fetched.  The modules the are part of
        jb_remote are supposed to populate this attribute in top-level module
        code.

    :type components: set of str
    """

    def __init__(self):
        self.primary_keys = None
        self.components = {"topics=*", "users=*"}

    def __getitem__(self, key):
        if self.primary_keys is None:
            self.primary_keys = connection.open("primary_keys?" + "&".join(self.components))
        return self.primary_keys[key]

primary_keys = PrimaryKeys()


def sanitize_for_markdown(text):
    """Convert a raw string to Markdown syntax.  This is used when external
    (legacy) strings are imported.  For example, comments found in data files
    must be sent through this function before being stored in the database.

    :param text: the original string

    :type text: unicode

    :return:
      the Markdown-ready string

    :rtype: unicode
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`"). \
        replace("\n#", "\n\\#").replace("\n>", "\n\\>").replace("\n+", "\n\\+").replace("\n-", "\n\\-")
    if text.startswith(tuple("#>+-")):
        text = "\\" + text
    # FixMe: Add ``flags=re.UNICODE`` with Python 2.7+
    paragraphs = re.split(r"\n\s*\n", text)
    for i, paragraph in enumerate(paragraphs):
        lines = paragraph.split("\n")
        for j, line in enumerate(lines):
            if len(line) < 70:
                lines[j] += "  "
        paragraphs[i] = "\n".join(lines)
    return "\n\n".join(paragraphs) + "\n"
