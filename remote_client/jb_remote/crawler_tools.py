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


import os, re, subprocess, time, smtplib, email, logging, pickle, contextlib, pathlib, itertools, socket, json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import deprecation
from . import settings


class Locked(Exception):
    def __init__(self, lockfile_path):
        super().__init__("Could not acquire lock for {}".format(lockfile_path))


class PIDLock:
    """Class for process locking in with statements.  It works only on UNIX.  You
    can use this class like this::

        with PIDLock("my_program"):
            ...

    The parameter ``"my_program"`` is used for determining the name of the PID
    lock file.

    Note that in containerised environments, or if crawlers may run on
    different hosts on the same data, this lock is ineffective.  At least, it
    does not block.  In such a scenario, you have to use other means
    (e.g. settings in Kubernetes) to avoid cuncurrent running.
    """

    def __init__(self, name, timeout=10*60):
        """Class constructor.  If the lock cannot be acquired at the first try, it is
        re-tried every 30 seconds.

        :param name: program name, from which the PID lock file name is derived
        :param timeout: time to wait for the lock in seconds; if set to 0, it
          is tried to acquire the lock exactly once.

        :type name: str
        :type timeout: int
        """
        self.lockfile_path = settings.CRAWLERS_DATA_DIR/(name + ".pid")
        self.lockfile = None
        self.timeout = timeout

    def try_acquire_lock(self):
        my_hostname = socket.gethostname()
        import fcntl  # local because only available on Unix
        try:
            self.lockfile = open(self.lockfile_path, "r+")
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            hostname, pid = json.load(self.lockfile)
        except FileNotFoundError:
            self.lockfile = open(self.lockfile_path, "w")
            try:
                fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX)
                already_running = False
            except BlockingIOError:
                already_running = True
                logging.warning("Lock {0} of other process active".format(self.lockfile_path))
        except BlockingIOError:
            already_running = True
            logging.warning("Lock {0} of other process active".format(self.lockfile_path))
        except (ValueError, json.decoder.JSONDecodeError):
            # Ignore invalid lock
            already_running = False
            self.lockfile.seek(0)
            self.lockfile.truncate()
            logging.warning("Lock {0} of other process has invalid content".format(self.lockfile_path))
        else:
            if hostname == my_hostname:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    # Ignore invalid lock
                    already_running = False
                    self.lockfile.seek(0)
                    self.lockfile.truncate()
                    logging.warning("Lock {0} of other process is orphaned".format(self.lockfile_path))
                else:
                    # sister process is already active
                    already_running = True
                    logging.warning("Lock {0} of other process active (but strangely not locked)".format(self.lockfile_path))
            else:
                # Assume container orchestration avoids cuncurrent processes
                already_running = False
                self.lockfile.seek(0)
                self.lockfile.truncate()
                logging.warning("Lock {0} of other process belongs to process on other host; assume it is orphaned".format(
                    self.lockfile_path))
        if not already_running:
            json.dump((my_hostname, os.getpid()), self.lockfile)
            self.lockfile.flush()
        else:
            self.lockfile.close()
            self.lockfile = None

    def __enter__(self):
        self.try_acquire_lock()
        stop_timestamp = time.time() + self.timeout
        while self.timeout and time.time() < stop_timestamp and not self.lockfile:
            time.sleep(30)
            self.try_acquire_lock()
        if not self.lockfile:
            raise Locked(self.lockfile_path)
        # FixMe: Only for compatibility.  This should be removed in future
        # versions.
        return True

    def __exit__(self, type_, value, tb):
        import fcntl
        fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
        self.lockfile.close()
        os.remove(self.lockfile_path)
        logging.info("Removed lock {0}".format(self.lockfile_path))


class Path:
    """Class that holds one absolut file system path.  All the “``was_...``”
    properties compare to the situation at the last run of `changed_files`.  It
    implements the path-like protocol.

    :ivar was_changed: this path was changed (i.e. created or modified)

    :ivar was_modified: this path was modified

    :ivar was_created: this path was newly created

    :ivar was_removed: this path was removed

    :ivar path: the actual absolute path

    :ivar relative_path: the original relative path given to the constructor

    :type was_changed: bool
    :type was_modified: bool
    :type was_created: bool
    :type was_removed: bool
    :type path: pathlib.path
    :type relative_path: str
    """

    def __init__(self, root, relative_path, type_, mtime):
        self.relative_path = relative_path
        self.path = pathlib.Path(root)/relative_path
        self.type_, self.mtime = type_, mtime
        self.done = False

    @property
    def was_changed(self):
        return self.type_ in {"modified", "created"}

    @property
    def was_modified(self):
        return self.type_ == "modified"

    @property
    def was_created(self):
        return self.type_ == "created"

    @property
    def was_removed(self):
        return self.type_ == "removed"

    def check_off(self):
        """Checks off the path as done.  Call this only if the path has be dealt with
        completely successfully, so that it does not need to be re-visited.
        You may call this method multiple times for the same filepath; it is
        idempotent.
        """
        self.done = True

    def __str__(self):
        return str(self.path)

    def __fspath__(self):
        return str(self.path)

    def __eq__(self, other):
        return self.path == other.path

    def __hash__(self):
        return hash(self.path)

    def __lt__(self, other):
        return self.mtime < other.mtime


class TrackingIterator:
    """Iterator class that allows to get the previous items.  Moreover, it allows
    multiple iterators to be given in its constructor.  This iterator is
    returned by the context manager `changed_files` to denote absolute paths to
    raw data files that have changed since its last run.

    :ivar iterator: iterable over all items that should be yielded by this
      iterator

    :ivar items: The items as returned by `__next__` so far.

    :ivar finished: whether the iterator has finished

    :type iterator: iterable of str
    :type current: str
    :type finished: bool
    """

    def __init__(self, *iterators):
        """Class constructor.

        :param iterators: all iterators the items of which should be yielded by
          this iterator

        :type iterators: tuple of iterators
        """
        self.iterator = itertools.chain(*iterators)
        self.items = []
        self.finished = False

    def __iter__(self):
        return self

    def __next__(self):
        try:
            current = next(self.iterator)
        except StopIteration:
            self.finished = True
            raise
        else:
            self.items.append(current)
            return current


def _crawl_all(root, statuses, compiled_pattern):
    """Crawls through the `root` directory and scans for all files matching
    `compiled_pattern`.  This is a helper function for `changed_files`.  It
    creates data structures that document the found files.  In this function,
    “relative” path means relative to `root`.

    :param root: absolute root path of the files to be scanned
    :param statuses: Mapping of relative file paths to the current mtime of the
      file, and its MD5 checksum.  It contains the content of the pickle file
      as read as at the beginning of `changed_files`, or is empty.
    :param compiled_pattern: compiled regular expression for filenames (without
        path) that should be scanned.

    :type root: str
    :type statuses: dict mapping str to (float, str)
    :type compiled_pattern: ``_sre.SRE_Pattern``

    :returns:
      all found relative paths, all new or mtime-changed absolute paths, and a
      mapping of all new relative paths to (mtime, ``None``)

    :rtype: set of str, list of str, dict mapping str to (float, ``NoneType``)
    """
    touched = []
    found = set()
    new_statuses = {}
    for dirname, __, filenames in os.walk(root):
        for filename in filenames:
            if compiled_pattern.match(filename):
                filepath = os.path.join(dirname, filename)
                relative_filepath = os.path.relpath(filepath, root)
                found.add(relative_filepath)
                mtime = os.path.getmtime(filepath)
                try:
                    status = statuses[relative_filepath]
                except KeyError:
                    status = new_statuses[relative_filepath] = [None, None]
                if mtime != status[0]:
                    status[0] = mtime
                    touched.append(filepath)
    return found, touched, new_statuses

def _enrich_new_statuses(new_statuses, root, statuses, touched):
    """Adds MD5-changed files to `new_statuses`.  This is a helper function for
    `changed_files`.  Before calling this function, `new_statuses` only
    contains new files.  In this function, “relative” path means relative to
    `root`.

    :param new_statuses: Mapping of relative file paths to the current mtime of
      the file, and its MD5 checksum.  It is modified in place.  After this
      function, it contains all files that are new or have changed content
      (based on checksum).
    :param root: absolute root path of the files to be scanned
    :param statuses: Mapping of relative file paths to the current mtime of the
      file, and its MD5 checksum.  It contains the content of the pickle file
      as read as at the beginning of `changed_files`, or is empty.
    :param touched: list of all files which are new or have their mtime changed
      since the last run (i.e., the last pickle file)

    :type new_statuses: dict mapping str to (float, str)
    :type root: str
    :type statuses: dict mapping str to (float, str)
    :type touched: list of str

    :returns:
      all absolute paths which are new or have changed (checksum-wise) content,
      sorted by mtime (ascending)

    :rtype: list of str
    """
    changed = []
    if touched:
        xargs_process = subprocess.Popen(["xargs", "-0", "md5sum"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        xargs_output = xargs_process.communicate(b"\0".join(path.encode() for path in touched))[0]
        if xargs_process.returncode != 0:
            raise subprocess.CalledProcessError(xargs_process.returncode, "xargs")
        for line in xargs_output.decode().splitlines():
            md5sum, __, filepath = line.partition("  ")
            relative_filepath = os.path.relpath(filepath, root)
            status = statuses.get(relative_filepath)
            if not status or md5sum != status[1]:
                new_status = new_statuses.get(relative_filepath) or \
                    new_statuses.setdefault(relative_filepath, statuses[relative_filepath].copy())
                new_status[1] = md5sum
                path = Path(root, relative_filepath, "modified" if status else "created", new_status[0])
                changed.append(path)
    assert set(changed) == {Path(root, path, "modified", 0) for path in new_statuses}, (set(changed), set(new_statuses))
    changed.sort()
    return changed

@contextlib.contextmanager
def changed_files(root, diff_file, pattern=""):
    """Returns the files changed since the last run of this function.  The files
    are given as an iterator over `Path` obejcts.  Changed files are files
    which have been added, modified or removed.  If a file was moved, the new
    path is returned as “created”, and the old one as “removed”.  The returned
    files are sorted by timestamp; first the removed, then from oldest to
    newest.

    If you move all files to another root and give that new root to this
    function, still only the modified files are returned.  In other words, the
    modification status of the last run only refers to file paths relative to
    ``root``.

    You use this context manager like this (for example)::

        with changed_files(root, diff_file) as paths:
            for path in path:
                ...  # process `path`
                if any_error:
                    continue
                path.check_off()

    Files older than 12 weeks are checked off implicitly.  In other words, they
    are tried to be processed only once.

    :param root: absolute root path of the files to be scanned
    :param diff_file: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
    :param pattern: Regular expression for filenames (without path) that should
        be scanned.  By default, all files are scanned.

    :type root: str
    :type diff_file: str
    :type pattern: str

    :return:
      files changed

    :rtype: iterator of `Path`
    """
    compiled_pattern = re.compile(pattern, re.IGNORECASE)
    if os.path.exists(diff_file):
        statuses, last_pattern = pickle.load(open(diff_file, "rb"), encoding="utf-8")
        if last_pattern != pattern:
            for relative_filepath in [relative_filepath for relative_filepath in statuses
                                      if not compiled_pattern.match(os.path.basename(relative_filepath))]:
                del statuses[relative_filepath]
    else:
        statuses, last_pattern = {}, None

    found, touched, new_statuses = _crawl_all(root, statuses, compiled_pattern)
    changed = _enrich_new_statuses(new_statuses, root, statuses, touched)
    removed = set(statuses) - found
    removed = [Path(root, relative_filepath, "removed", 0) for relative_filepath in removed]

    iterator = TrackingIterator(changed, removed)
    try:
        yield iterator
    except Exception as error:
        path = iterator.items and iterator.items[-1]
        relative_path = '"{}"'.format(path.relative_path) if path else "unknown file"
        logging.critical('Crawler error at {0} (aborting): {1}'.format(relative_path, error))

    twelve_weeks_ago = time.time() - 12 * 7 * 24 * 3600
    statuses_changed = False
    for path in iterator.items:
        relative_path = path.relative_path
        if path.done:
            statuses_changed = True
            if path.was_changed:
                statuses[relative_path] = new_statuses[relative_path]
            elif path.was_removed:
                del statuses[relative_path]
        elif path.was_changed and path.mtime < twelve_weeks_ago:
            statuses[relative_path] = new_statuses[relative_path]

    if statuses_changed or last_pattern != pattern:
        pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)


@deprecation.deprecated()
def find_changed_files(root, diff_file, pattern=""):
    """Returns the files changed or removed since the last run of this
    function.  The files are given as a list of absolute paths.  Changed files
    are files which have been added or modified.  If a file was moved, the new
    path is returned in the “changed” list, and the old one in the “removed”
    list.  Changed files are sorted by timestamp, oldest first.

    If you move all files to another root and give that new root to this
    function, still only the modified files are returned.  In other words, the
    modification status of the last run only refers to file paths relative to
    ``root``.

    :param root: absolute root path of the files to be scanned
    :param diff_file: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
    :param pattern: Regular expression for filenames (without path) that should
        be scanned.  By default, all files are scanned.

    :type root: str
    :type diff_file: str
    :type pattern: str

    :return:
      files changed, files removed

    :rtype: list of str, list of str
    """
    compiled_pattern = re.compile(pattern, re.IGNORECASE)
    if os.path.exists(diff_file):
        statuses, last_pattern = pickle.load(open(diff_file, "rb"), encoding="utf-8")
        if last_pattern != pattern:
            for relative_filepath in [relative_filepath for relative_filepath in statuses
                                      if not compiled_pattern.match(os.path.basename(relative_filepath))]:
                del statuses[relative_filepath]
    else:
        statuses, last_pattern = {}, None
    touched = []
    found = set()
    for dirname, __, filenames in os.walk(root):
        for filename in filenames:
            if compiled_pattern.match(filename):
                filepath = os.path.join(dirname, filename)
                relative_filepath = os.path.relpath(filepath, root)
                found.add(relative_filepath)
                mtime = os.path.getmtime(filepath)
                status = statuses.setdefault(relative_filepath, [None, None])
                if mtime != status[0]:
                    status[0] = mtime
                    touched.append(filepath)
    removed = set(statuses) - found
    for relative_filepath in removed:
        del statuses[relative_filepath]
    removed = [os.path.join(root, relative_filepath) for relative_filepath in removed]
    changed = []
    timestamps = {}
    if touched:
        xargs_process = subprocess.Popen(["xargs", "-0", "md5sum"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        xargs_output = xargs_process.communicate(b"\0".join(path.encode() for path in touched))[0]
        if xargs_process.returncode != 0:
            raise subprocess.CalledProcessError(xargs_process.returncode, "xargs")
        for line in xargs_output.decode().splitlines():
            md5sum, __, filepath = line.partition("  ")
            status = statuses[os.path.relpath(filepath, root)]
            if md5sum != status[1]:
                status[1] = md5sum
                changed.append(filepath)
                timestamps[filepath] = status[0]
    changed.sort(key=lambda filepath: timestamps[filepath])
    if touched or removed or last_pattern != pattern:
        pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)
    return changed, removed


@deprecation.deprecated()
def defer_files(diff_file, filepaths):
    """Removes filepaths from a diff file created by `find_changed_files`.
    This is interesting if you couldn't process certain files so they should be
    re-visited in the next run of the crawler.  Typical use case: Some
    measurement files could not be processed because the sample was not found
    in JuliaBase.  Then, this sample is added to JuliaBase, and the files should be
    processed although they haven't changed.

    If the file is older than 12 weeks, it is not defered.

    If a filepath is not found in the diff file, this is ignored.

    :param diff_file: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
    :param filepaths: all relative paths that should be removed from the diff
        file; they are relative to the root that was used when creating the
        diff file;  see `find_changed_files`

    :type diff_file: str
    :type filepaths: iterable of str
    """
    statuses, pattern = pickle.load(open(diff_file, "rb"), encoding="utf-8")
    twelve_weeks_ago = time.time() - 12 * 7 * 24 * 3600
    for filepath in filepaths:
        if filepath in statuses and statuses[filepath][0] > twelve_weeks_ago:
            del statuses[filepath]
    pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)


def send_error_mail(from_, subject, text, html=None):
    """Sends an email to JuliaBase's administrators.  Normally, it is about an
    error condition but it may be anything.

    :param from_: name (and only the name, not an email address) of the sender;
        this typically is the name of the currently running program
    :param subject: the subject of the message
    :param text: text body of the message
    :param html: optional HTML attachment

    :type from_: str
    :type subject: str
    :type text: str
    :type html: str
    """
    cycles = 5
    while cycles:
        try:
            server = smtplib.SMTP(settings.SMTP_SERVER)
            if settings.SMTP_LOGIN:
                server.starttls()
                server.login(settings.SMTP_LOGIN, settings.SMTP_PASSWORD)
            message = MIMEMultipart()
            message["Subject"] = subject
            message["From"] = '"{0}" <{1}>'. \
                format(from_.replace('"', ""), settings.EMAIL_FROM).encode("ascii", "replace")
            message["To"] = settings.EMAIL_TO
            message["Date"] = email.utils.formatdate()
            message.attach(MIMEText(text.encode(), _charset="utf-8"))
            if html:
                message.attach(MIMEText(html.encode(), "html", _charset="utf-8"))
            server.sendmail(settings.EMAIL_FROM, message["To"], message.as_string())
            server.quit()
        except smtplib.SMTPException:
            pass
        else:
            break
        cycles -= 1
        time.sleep(10)
