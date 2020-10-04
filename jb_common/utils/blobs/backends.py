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


"""The blob storage backends.  Currently, it is used for storing uploaded files
(with result processes).  You have to set a blob storage backend in the
``BLOB_STORAGE_BACKEND`` settings like this::

    BLOB_STORAGE_BACKEND = ("jb_common.utils.blobs.backends.Filesystem",
                            (MEDIA_ROOT,))
"""

import os, uuid, datetime, io
from contextlib import contextmanager
import psycopg2
from django.conf import settings
from jb_common.utils.base import mkdirs, getmtime_utc
from jb_common.signals import storage_changed


class BlobStorage:
    """Abstract base class for blob storage backends.  It lists all methods that
    may be implemented and their signatures.  Currently, core JuliaBase only
    calls the methods `open` and `export`.

    Note the “full path” means that it must be complete.  *Important*: Any
    paths in the blob storage must not start with a slash.
    """

    def list(self, path):
        """Lists all files in the directory ``path``.  If ``path`` points to a file, an
        empty list is returned.

        :param path: full path to a directory

        :type path: str

        :return:
          all files in the directory, as simple names (rather than full
          paths)

        :rtype: list of str
        """
        raise NotImplementedError

    def getmtime(self, path):
        """Returns the modification timestamp of the file at ``path``.

        :param path: full path to a directory

        :type path: str

        :return:
          the modification timestamp

        :rtype: datetime.datetime
        """
        raise NotImplementedError

    def unlink(self, path):
        """Removes the file at ``path``.  This must not be a directory.

        :param path: full path to a file

        :type path: str
        """
        raise NotImplementedError

    def open(self, path, mode="r"):
        """Opens the file at ``path`` as a binary stream.  Note that ``close()`` should
        be called explicitly!

        :param path: full path to a file
        :param mode: mode in which the file should be opened; may be ``"r"`` or
          ``"w"``

        :type path: str

        :return:
          the opened file

        :rtype: binary stream
        """
        raise NotImplementedError

    def export(self, path):
        """Returns a removable path to the file.  This is used when serving files.  The
        Web server gets the result of this method in the ``X-Sendfile`` header,
        serves the file content at this path directly to the client, and (if
        Apache's ``X-SENDFILE-TEMPORARY`` is used) unlinks the path afterwards.
        For obvious reasons, this unlinking must not remove the original file.

        Note that the resulting path should be unlinked afterwards (e.g. by the
        Web server, or in ``/tmp`` after a reboot), else, a temporary file is
        staying around.

        :param path: full path to a file

        :type path: str

        :return:
          path to the file which can be removed

        :rtype: str
        """
        raise NotImplementedError


class Filesystem(BlobStorage):
    """Filesystem backend.  It stores all blobs under their pathname in the root
    directory given to the constructor.  You may use ``settings.MEDIA_ROOT``
    for it.  Note that this blob storage backend only makes sense if you run
    JuliaBase only on one computer, or use a cluster file systems for all
    cluster nodes.

    This backend always exports hard links, preferably to /tmp, else to
    CACHE_ROOT or to the root directory.
    """

    class File(io.FileIO):

        def close(self):
            super().close()
            storage_changed.send(Filesystem)


    def __init__(self, root=None):
        """Class constructor.

        :param root: root directory of the file system storage of BLOB files;
          it defaults to ``MEDIA_ROOT``

        :type root: str
        """
        self.root = root or settings.MEDIA_ROOT

    def getmtime(self, path):
        return getmtime_utc(os.path.join(self.root, path))

    def unlink(self, path):
        os.unlink(os.path.join(self.root, path))

    def open(self, path, mode="r"):
        filepath = os.path.join(self.root, path)
        if mode == "w":
            mkdirs(filepath)
        return Filesystem.File(filepath, mode + "b")

    def export(self, path):
        """Create a hard link to the file.  Three directories are tried, in this order:

        1. /tmp
        2. CACHE_ROOT
        3. `root` (as given to `__init__`

        A failure means the the original file and the link are not on the same
        filesystem, which must be the case at least for (3).
        """
        path = os.path.join(self.root, path)
        filename = str(uuid.uuid4())
        result = os.path.join("/tmp", filename)
        try:
            os.link(path, result)
        except OSError:
            result = os.path.join(settings.CACHE_ROOT, filename)
            mkdirs(result)
            try:
                os.link(path, result)
            except OSError:
                result = os.path.join(self.root, filename)
                os.link(path, result)
        return result


class PostgreSQL(BlobStorage):
    """PostgreSQL large objects backend.  It stores all blobs in a PostgreSQL
    database using PostgreSQL's “large object” facility.  Moreover, it creates
    one table called “blobs” in the database to link the large object IDs
    (OIDs) with the pathname and an mtime timestamp.
    """

    class BlobFile(psycopg2.extensions.lobject):

        def init_additional_attributes(self, path, connection, cursor):
            self.path, self.connection, self.cursor = path, connection, cursor

        def close(self):
            if self.mode == "wb":
                self.cursor.execute("UPDATE blobs SET mtime=now() WHERE path=%s;", (self.path,))
            super().close()
            self.connection.commit()
            self.cursor.close()
            self.connection.close()


    def __init__(self, database, user, password, host):
        """Class constructor.  It creates the table “blobs” in the database if
        it doesn't exist yet.

        :param database: name of the database
        :param user: PostgreSQL user name
        :param password: PostgreSQL password
        :param host: PostgreSQL hostname

        :type database: str
        :type user: str
        :type password: str
        :type host: str
        """
        self.database, self.user, self.password, self.host = database, user, password, host
        with psycopg2.connect(database=self.database, user=self.user, password=self.password, host=self.host) \
             as connection, connection.cursor() as cursor:
            try:
                cursor.execute("CREATE TABLE blobs (path varchar(255), large_object_id oid NOT NULL, "
                               "mtime timestamp with time zone NOT NULL, "
                               "PRIMARY KEY (path), UNIQUE (large_object_id));")
            except psycopg2.ProgrammingError:
                connection.reset()

    @staticmethod
    def get_oid(cursor, path):
        """Returns the OID of the given ``path``, or ``None`` if the path does not
        exist in the database.

        :param cursor: PostgreSQL database cursor
        :param path: path to a file in the blob database

        :type cursor: psycopg2.extensions.cursor
        :type path: str

        :return:
          the OID of the given ``path``, or ``None`` if the path does not exist
          in the database

        :rtype: int or ``NoneType``
        """
        cursor.execute("SELECT large_object_id FROM blobs WHERE path=%s;", (path,))
        result = cursor.fetchone()
        return result and result[0]

    @contextmanager
    def existing_large_object(self, path):
        """Context manager for getting *existing* blobs.  If a blob with the given
        ``path`` doesn't exist, an exception is raised.  Otherwise, it returns
        the OID of the blob and a database cursor.

        :param path: path to an existing file in the blob database

        :type path: str

        :raises FileNotFoundError: if no file with that path exists
        """
        with psycopg2.connect(database=self.database, user=self.user, password=self.password, host=self.host) \
             as connection, connection.cursor() as cursor:
            oid = self.get_oid(cursor, path)
            if oid is None:
                raise FileNotFoundError("No such blob: {}".format(repr(path)))
            large_object = connection.lobject(oid, "rb")
            try:
                yield large_object, cursor
            finally:
                if not large_object.closed:
                    large_object.close()

    def getmtime(self, path):
        with self.existing_large_object(path) as (large_object, cursor):
            cursor.execute("SELECT mtime FROM blobs WHERE large_object_id=%s;", (large_object.oid,))
            return cursor.fetchone()[0]

    def unlink(self, path):
        with self.existing_large_object(path) as (large_object, cursor):
            cursor.execute("DELETE FROM blobs WHERE large_object_id=%s;", (large_object.oid,))
            large_object.unlink()

    def open(self, path, mode="r"):
        mode += "b"
        connection = psycopg2.connect(database=self.database, user=self.user, password=self.password, host=self.host)
        cursor = connection.cursor()
        oid = self.get_oid(cursor, path)
        if oid is None:
            large_object = connection.lobject(mode=mode, lobject_factory=self.BlobFile)
            cursor.execute("INSERT INTO blobs VALUES (%s, %s, now());", (path, large_object.oid))
        else:
            large_object = connection.lobject(oid, mode, lobject_factory=self.BlobFile)
            large_object.truncate()
        large_object.init_additional_attributes(path, connection, cursor)
        return large_object

    def export(self, path):
        with self.existing_large_object(path) as (large_object, cursor):
            result = os.path.join(settings.CACHE_ROOT, str(uuid.uuid4()))
            mkdirs(result)
            large_object.export(result)
            return result
