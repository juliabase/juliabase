# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
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


""".. py:data:: connection

    The connection to the database server.  It is of the type
    :py:class:`JuliaBaseConnection`.

.. py:data:: primary_keys

    A dict-like object of type :py:class:`PrimaryKeys` that is a mapping of
    identifying keys to IDs.  Possible keys are:

        ``"users"``
            mapping user names to user IDs.

        ``"external_operators"``
            mapping external operator names to external operator IDs.

        ``"topics"``
            mapping topic names to topic IDs.
"""

import mimetypes, json, logging, os, datetime, time, random, re, decimal, urllib, _thread, io
from http import cookiejar
from . import settings


__all__ = ["login", "logout", "connection", "primary_keys", "JuliaBaseError", "setup_logging",
           "format_timestamp", "parse_timestamp", "as_json"]


def setup_logging(destination=None, filepath=None):
    """Sets up the root logger.  Note that it replaces the old root logger
    configuration fully.  Client code should call this function as early as
    possible.

    :param destination: Where to log to; possible values are:

        ``"file"``
            Log to :file:`/var/lib/crawlers/jb_remote.log` if
            :file:`/var/lib/crawlers` is existing, otherwise (i.e. on Windows),
            log to :file:`jb_remote.log` in the current directory.  The
            directory is configurable by the environment variable
            ``CRAWLERS_DATA_DIR``.  See also the `filepath` parameter.

            Logging is appended to that file.

            It additionally enables logging to stderr, in order to be useful in
            containers.

        ``"console"``
            Log to stderr.

        ``None``
            Do not log.
    :param str filepath: Makes sense only if `destination` is “file”.  If
      given, the log output is sent to this path, and to stderr.

    :type destination: str
    """
    format_string = "%(asctime)s %(levelname)-8s %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    if destination == "file":
        if filepath is None:
            if settings.CRAWLERS_DATA_DIR.is_dir():
                filepath = settings.CRAWLERS_DATA_DIR/"jb_remote.log"
            else:
                filepath = "jb_remote.log"
        logging.basicConfig(force=True, level=logging.INFO, format=format_string, datefmt=date_format,
                            filename=filepath, filemode="a")
        formatter = logging.Formatter(format_string, date_format)
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        handler.setLevel(logging.INFO)
        logging.getLogger("").addHandler(handler)
    elif destination == "console":
        logging.basicConfig(force=True, level=logging.INFO, format=format_string, datefmt=date_format)
    else:
        class LogSink:
            def write(self, *args, **kwargs):
                pass
            def flush(self, *args, **kwargs):
                pass
        logging.basicConfig(force=True, stream=LogSink())


def clean_header(value):
    """Makes a scalar value fit for being used in POST data.  Note that
    booleans with the value ``False`` are excluded from the POST dictionary by
    returning ``None``.  This mimics HTML's behaviour then ``False`` values in
    forms are “not successful”.
    """
    if isinstance(value, bool):
        return "on" if value else None
    elif isinstance(value, io.IOBase):
        return value
    else:
        return str(value)


def comma_separated_ids(ids):
    return ",".join(str(id_) for id_ in ids)


def double_urlquote(string):
    """Returns a double-percent-quoted string.  This mimics the behaviour of
    Django, which quotes every URL retrieved by ``django.urls.resolve``.
    Because it does not quote the slash “/” for obvious reasons, I have to
    quote sample names, sample series names, deposition numbers, and non-int
    process “identifying fields” *before* they are fed into ``resolve`` (and
    quoted again).
    """
    return urllib.parse.quote(urllib.parse.quote(string, safe=""))


def parse_timestamp(timestamp):
    """Convert a timestamp coming from the server to a Python `datetime` object.
    The server serialises with the `DjangoJSONEncoder`, which in turn uses the
    ``.isoformat()`` method.  Note that the timestamp must use the UTC timezone
    (Z for zulu), which seems to be always the case for non-template responses
    (at least for PostgreSQL and SQLite).

    :param timestamp: the timestamp to parse, coming from the server.  It must
        have ISO 8601 format format exlicitly with the “Z” timezone.

    :type timestamp: str

    :return:
      the timestamp as a Python datetime object

    :rtype: datetime.datetime
    """
    return datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S" + (".%f" if "." in timestamp else "") + "Z")


def format_timestamp(timestamp):
    """Serializses a timestamp.  This is the counter function to `parse_timestamp`,
    however, there is an asymmetry: Here, we don't generate ISO 8601 timestamps
    (with the ``"T"`` inbetween).  The reason is that Django's `DateTimeField`
    would not be able to parse it.  But see
    <https://code.djangoproject.com/ticket/11385>.

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

    :type data: dict mapping str to str, int, float, bool, file, or list

    :return:
      the content type, the HTTP body

    :rtype: str, str
    """
    def get_content_type(filename):
        return mimetypes.guess_type(filename)[0] or "application/octet-stream"

    non_file_items = []
    file_items = []
    for key, value in data.items():
        if isinstance(value, io.IOBase):
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
        return "application/x-www-form-urlencoded", urllib.parse.urlencode(data, doseq=True).encode()
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


class JuliaBaseError(Exception):
    """Exception class for high-level JuliaBase errors.

    :ivar error_code: The numerical error code.  See :py:mod:`jb_common.utils`
      for further information, and the root ``__init__.py`` file of the various
      JuliaBase apps for the tables with the error codes.

    :ivar error_message: A description of the error.  If `error_code` is ``1``, it
      contains the URL to the error page (without the domain name).

    :type error_code: int
    :type error_message: str
    """

    def __init__(self, error_code, message):
        self.error_code, self.error_message = error_code, message

    def __str__(self):
        return "({0}) {1}".format(self.error_code, self.error_message)


class JuliaBaseConnection:
    """Class for the routines that connect to the database at HTTP level.
    This is a singleton class, and its only instance resides at top-level in
    this module.
    """
    cookie_jar = cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    http_headers = [("User-agent", "JuliaBase-Remote/1.0"),
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
                    error_code, error_message = json.loads(error.read().decode())
                    raise JuliaBaseError(error_code, error_message)
                server_error_message = error.read().decode()
                error.msg = "{}\n\n{}".format(error.msg, server_error_message)
                raise error
            except urllib.error.URLError:
                if max_cycles == 0:
                    logging.error("Request failed.")
                    raise
            time.sleep(3 * random.random())

    @staticmethod
    def _clean_data(data):
        if data is None:
            return None
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
        return cleaned_data

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
        :type data: dict mapping str to str, int, float, bool, file, or list
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
        if self.root_url is None:
            raise Exception("No root URL defined.  Maybe not logged-in?")
        response = self._do_http_request(self.root_url + relative_url, self._clean_data(data))
        if response_is_json:
            assert response.info()["Content-Type"].startswith("application/json")
            return json.loads(response.read().decode())
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

    :type username: str
    :type password: str
    :type testserver: bool
    """
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


class PrimaryKeys:
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

    :type text: str

    :return:
      the Markdown-ready string

    :rtype: str
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("_", "\\_").replace("*", "\\*").replace("`", "\\`"). \
        replace("\n#", "\n\\#").replace("\n>", "\n\\>").replace("\n+", "\n\\+").replace("\n-", "\n\\-")
    if text.startswith(tuple("#>+-")):
        text = "\\" + text
    paragraphs = re.split(r"\n\s*\n", text, flags=re.UNICODE)
    for i, paragraph in enumerate(paragraphs):
        lines = paragraph.split("\n")
        for j, line in enumerate(lines):
            if len(line) < 70:
                lines[j] += "  "
        paragraphs[i] = "\n".join(lines)
    return "\n\n".join(paragraphs) + "\n"


class JSONEncoder(json.JSONEncoder):
    """JSON encoding class which can handle way more than the basic datatypes the
    default encoder of Python can handle.
    """
    def default(self, o):
        try:
            return float(o)
        except (ValueError, TypeError):
            try:
                return list(o)
            except (ValueError, TypeError):
                try:
                    if isinstance(o, datetime.datetime):
                        r = o.isoformat()
                        if o.microsecond:
                            r = r[:23] + r[26:]
                        if r.endswith("+00:00"):
                            r = r[:-6] + "Z"
                        return r
                    elif isinstance(o, datetime.date):
                        return o.isoformat()
                    elif isinstance(o, datetime.time):
                        if o.tzinfo is not None and o.tzinfo.utcoffset(o) is not None:
                            raise ValueError("JSON can't represent timezone-aware times.")
                        r = o.isoformat()
                        if o.microsecond:
                            r = r[:12]
                        return r
                    elif isinstance(o, decimal.Decimal):
                        return str(o)
                    else:
                        return super().default(o)
                except (ValueError, TypeError):
                    return str(o)


def as_json(value):
    """Prints the value in JSON fromat to standard output.  This routine comes in
    handy if Python is called from another program which parses the standard
    output.  Then, you can say

    ::

        as_json(User("r.calvert").permissions)

    and the calling program (written e.g. in Delphi or LabVIEW) just has to
    convert JSON into its own data structures.

    :param value: the data to be printed as JSON.

    :type value: ``object`` (an arbitrary Python object)
    """
    print(json.dumps(value, cls=JSONEncoder))
