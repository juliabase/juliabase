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

import urllib, urllib2, cookielib, mimetools, mimetypes, json, logging, os.path, datetime, re, time, random, sys, \
    subprocess

__all__ = ["login", "logout", "PIDLock", "find_changed_files", "defer_files", "send_error_mail", "JuliaBaseError", "setup_logging"]

from . import settings


def setup_logging(enable=False):
    """If the user wants to call this in order to enable logging, he must do
    so before logging in.  Note that it is a no-op if called a second time.
    """
    # This is not totally clean because it doesn't guarantee that logging is
    # properly configured *before* the first log message is generated but I'm
    # pretty sure that this is the case.  The clean solution would involve more
    # boilerplate code for the end-user, which I don't want, or replacing all
    # ``logging.info`` etc. calls with an own wrapper.
    if enable:
        logging.basicConfig(level=logging.INFO,
                            format="%(asctime)s %(levelname)-8s %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S",
                            filename="/tmp/jb_remote.log" if os.path.exists("/tmp") else "jb_remote.log",
                            filemode="w")
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
        return unicode(value).encode("utf-8")


def comma_separated_ids(ids):
    return ",".join(str(id_) for id_ in ids)


def format_timestamp(timestamp):
    try:
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        return timestamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def encode_multipart_formdata(data):
    """Generates content type and body for an HTTP POST request.  It can also
    handle file uploads: For them, the value of the item in ``data`` is an open
    file object.  Taken from <http://code.activestate.com/recipes/146306/#c5>.

    :Parameters:
      - `data`: the POST data; it must not be ``None``

    :type data: dict mapping unicode to unicode, int, float, bool, file, or
      list

    :Return:
      the content type, the HTTP body

    :rtype: str, str
    """
    def get_content_type(filename):
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"

    non_file_items = []
    file_items = []
    for key, value in data.iteritems():
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
        return "application/x-www-form-urlencoded", urllib.urlencode(data, doseq=True)
    boundary = mimetools.choose_boundary()
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


class JuliaBaseError(Exception):
    """Exception class for high-level JuliaBase errors.

    :ivar error_code: The numerical error code.  See ``jb_common.utils``
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
        # FixMe: In Python3, the ``encode`` call must be dropped.
        return "({0}) {1}".format(self.error_code, self.error_message.encode("utf-8"))

    def __unicode__(self):
        return self.__str__()


class JuliaBaseConnection(object):
    """Class for the routines that connect to the database at HTTP level.
    This is a singleton class, and its only instance resides at top-level in
    this module.
    """
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
    opener.addheaders = [("User-agent", "JuliaBase-Remote/0.1"),
                         ("Accept", "application/json,text/html;q=0.9,application/xhtml+xml;q=0.9,text/*;q=0.8,*/*;q=0.7")]

    def __init__(self):
        self.username = None
        self.root_url = None

    def _do_http_request(self, url, data=None):
        logging.debug("{0} {1!r}".format(url, data))
        if data is None:
            request = urllib2.Request(url)
        else:
            content_type, body = encode_multipart_formdata(data)
            headers = {"Content-Type": content_type}
            request = urllib2.Request(url, body, headers)
        max_cycles = 10
        while max_cycles > 0:
            max_cycles -= 1
            try:
                return self.opener.open(request)
            except urllib2.HTTPError as error:
                if error.code in [404, 422] and error.info()["Content-Type"].startswith("application/json"):
                    error_code, error_message = json.loads(error.read())
                    raise JuliaBaseError(error_code, error_message)
                try:
                    open("/tmp/juliabase_error.html", "w").write(error.read())
                except IOError:
                    pass
                raise error
            except urllib2.URLError:
                if max_cycles == 0:
                    logging.error("Request failed.")
                    raise
            time.sleep(3 * random.random())

    def open(self, relative_url, data=None, response_is_json=True):
        """Do an HTTP request with the JuliaBase server.  If ``data`` is not
        ``None``, its a POST request, and GET otherwise.

        :Parameters:
          - `relative_url`: the non-domain part of the URL, for example
            ``"/samples/10-TB-1"``.  “Relative” may be misguiding here: only
            the domain is omitted.
          - `data`: the POST data, or ``None`` if it's supposed to be a GET
            request.
          - `response_is_json`: whether the content type of the response must
            be JSON

        :type relative_url: str
        :type data: dict mapping unicode to unicode, int, float, bool, file, or
          list
        :type response_is_json: bool

        :Return:
          the response to the request

        :rtype: ``object``

        :Exceptions:
          - `JuliaBaseError`: raised if JuliaBase couldn't fulfill the request
            because it contained errors.  For example, you requested a sample
            that doesn't exist, or the transmitted measurement data was
            incomplete.
          - `urllib2.URLError`: raise if a lower-level error occured, e.g. the
            HTTP connection couldn't be established.
        """
        if data is not None:
            cleaned_data = {}
            for key, value in data.iteritems():
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
            response = self._do_http_request(settings.self.root_url + relative_url, cleaned_data)
        else:
            response = self._do_http_request(settings.self.root_url + relative_url)
        if response_is_json:
            assert response.info()["Content-Type"].startswith("application/json")
            return json.loads(response.read())
        else:
            return response.read()

    def login(self, root_url, username, password):
        self.root_url = root_url
        self.username = username
        self.open("login_remote_client", {"username": username, "password": password})

    def logout(self):
        self.open("logout_remote_client")

connection = JuliaBaseConnection()


def login(username, password, testserver=False):
    """Logins to JuliaBase.

    :Parameters:
      - `username`: the username used to log in
      - `password`: the user's password
      - `testserver`: whether the testserver should be user.  If ``False``, the
        production server is used.

    :type username: unicode
    :type password: unicode
    :type testserver: bool
    """
    setup_logging()
    if testserver:
        logging.info("Logging into the testserver.")
        connection.login(settings.testserver_root_url, username, password)
    else:
        connection.login(settings.root_url, username, password)
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

    def __init__(self, connection):
        self.connection = connection
        self.primary_keys = None
        self.components = {"topics=*", "users=*"}

    def __getitem__(self, key):
        if self.primary_keys is None:
            self.primary_keys = self.connection.open("primary_keys?" + "&".join(self.components))
        return self.primary_keys[key]

primary_keys = PrimaryKeys(connection)
