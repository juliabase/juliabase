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
import six
from six.moves import cPickle as pickle
from six.moves.email_mime_multipart import MIMEMultipart
from six.moves.email_mime_text import MIMEText

import os, sys, re, subprocess, time, smtplib, email

from . import settings


class PIDLock(object):
    """Class for process locking in with statements.  It works only on UNIX.  You
    can use this class like this::

        with PIDLock("my_program") as locked:
            if locked:
                do_work()
            else:
                print "I'am already running.  I just exit."

    The parameter ``"my_program"`` is used for determining the name of the PID
    lock file.
    """

    def __init__(self, name):
        self.lockfile_path = os.path.join("/tmp/", name + ".pid")
        self.locked = False

    def __enter__(self):
        import fcntl  # local because only available on Unix
        try:
            self.lockfile = open(self.lockfile_path, "r+")
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            pid = int(self.lockfile.read().strip())
        except IOError as e:
            if e.strerror == "No such file or directory":
                self.lockfile = open(self.lockfile_path, "w")
                fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_EX)
                already_running = False
            elif e.strerror == "Resource temporarily unavailable":
                already_running = True
                sys.stderr.write("WARNING: Lock {0} of other process active\n".format(self.lockfile_path))
            else:
                raise
        except ValueError:
            # Ignore invalid lock
            already_running = False
            self.lockfile.seek(0)
            self.lockfile.truncate()
            sys.stderr.write("ERROR: Lock {0} of other process has invalid content\n".format(self.lockfile_path))
        else:
            try:
                os.kill(pid, 0)
            except OSError as error:
                if error.strerror == "No such process":
                    # Ignore invalid lock
                    already_running = False
                    self.lockfile.seek(0)
                    self.lockfile.truncate()
                    sys.stderr.write("WARNING: Lock {0} of other process is orphaned\n".format(self.lockfile_path))
                else:
                    raise
            else:
                # sister process is already active
                already_running = True
                sys.stderr.write("WARNING: Lock {0} of other process active (but strangely not locked)\n".
                                 format(self.lockfile_path))
        if not already_running:
            self.lockfile.write(str(os.getpid()))
            self.lockfile.flush()
            self.locked = True
        return self.locked

    def __exit__(self, type_, value, tb):
        import fcntl
        if self.locked:
            fcntl.flock(self.lockfile.fileno(), fcntl.LOCK_UN)
            self.lockfile.close()
            os.remove(self.lockfile_path)
            logging.info("Removed lock {0}".format(self.lockfile_path))


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

    :Parameters:
      - `root`: absolute root path of the files to be scanned
      - `diff_file`: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
      - `pattern`: Regular expression for filenames (without path) that should
        be scanned.  By default, all files are scanned.

    :type root: str
    :type diff_file: str
    :type pattern: unicode

    :Return:
      files changed, files removed

    :rtype: list of str, list of str
    """
    compiled_pattern = re.compile(pattern, re.IGNORECASE)
    if os.path.exists(diff_file):
        statuses, last_pattern = pickle.load(open(diff_file, "rb"))
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
        xargs_output = xargs_process.communicate(b"\0".join(touched))[0]
        if xargs_process.returncode != 0:
            raise subprocess.CalledProcessError(xargs_process.returncode, "xargs")
        for line in xargs_output.splitlines():
            md5sum, __, filepath = line.partition(b"  ")
            status = statuses[os.path.relpath(filepath, root)]
            if md5sum != status[1]:
                status[1] = md5sum
                changed.append(filepath)
                timestamps[filepath] = status[0]
    changed.sort(key=lambda filepath: timestamps[filepath])
    if touched or removed or last_pattern != pattern:
        pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)
    return changed, removed


def defer_files(diff_file, filepaths):
    """Removes filepaths from a diff file created by `find_changed_files`.
    This is interesting if you couldn't process certain files so they should be
    re-visited in the next run of the crawler.  Typical use case: Some
    measurement files could not be processed because the sample was not found
    in JuliaBase.  Then, this sample is added to JuliaBase, and the files should be
    processed although they haven't changed.

    If the file is older than 12 weeks, it is not defered.

    If a filepath is not found in the diff file, this is ignored.

    :Parameters:
      - `diff_file`: path to a writable pickle file which contains the
        modification status of all files of the last run; it is created if it
        doesn't exist yet
      - `filepaths`: all relative paths that should be removed from the diff
        file; they are relative to the root that was used when creating the
        diff file;  see `find_changed_files`

    :type diff_file: str
    :type filepaths: iterable of str
    """
    statuses, pattern = pickle.load(open(diff_file, "rb"))
    twelve_weeks_ago = time.time() - 12 * 7 * 24 * 3600
    for filepath in filepaths:
        if filepath in statuses and statuses[filepath][0] > twelve_weeks_ago:
            del statuses[filepath]
    pickle.dump((statuses, pattern), open(diff_file, "wb"), pickle.HIGHEST_PROTOCOL)


def send_error_mail(from_, subject, text, html=None):
    """Sends an email to JuliaBase's administrators.  Normally, it is about an
    error condition but it may be anything.

    :Parameters:
      - `from_`: name (and only the name, not an email address) of the sender;
        this typically is the name of the currently running program
      - `subject`: the subject of the message
      - `text`: text body of the message
      - `html`: optional HTML attachment

    :type from_: unicode
    :type subject: unicode
    :type text: unicode
    :type html: unicode
    """
    cycles = 5
    while cycles:
        try:
            server = smtplib.SMTP(settings.smtp_server)
            if settings.smtp_login:
                s.starttls()
                s.login(settings.smtp_login, settings.smtp_password)
            message = MIMEMultipart()
            message["Subject"] = subject
            message["From"] = '"{0}" <{1}>'. \
                format(from_.replace('"', ""), settings.email_from).encode("ascii", "replace")
            message["To"] = settings.email_to
            message["Date"] = email.utils.formatdate()
            message.attach(MIMEText(text.encode("utf-8"), _charset="utf-8"))
            if html:
                message.attach(MIMEText(html.encode("utf-8"), "html", _charset="utf-8"))
            server.sendmail(settings.email_from, message["To"], message.as_string())
            server.quit()
        except smtplib.SMTPException:
            pass
        else:
            break
        cycles -= 1
        time.sleep(10)
