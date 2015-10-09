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

import os, uuid
from contextlib import contextmanager
import psycopg2


class BlobStorage(object):
    """Abstract base class for blob storage backends.  It lists all methods that
    may be implemented and their signatures.  Currently, core JuliaBase only
    calls the methods `open`, `write`, `close`, and `export`.
    """

    def list(self, path):
        """Lists all files in the directory ``path``.  If ``path`` points to a file, an
        empty list is returned.

        :param path: absolute path to a directory

        :type path: str

        :return:
          all files in the directory, as simple names (rather than absolute
          paths)

        :rtype: list of str
        """
        raise NotImplementedError

    def unlink(self, path):
        """Removes the file at ``path``.  This must not be a directory.

        :param path: absolute path to a file

        :type path: str
        """
        raise NotImplementedError

    def open(self, path, mode="r"):
        """Opens the file at ``path``.  This must be a regular file.

        :param path: absolute path to a file
        :param mode: mode in which the file should be opened; may be ``"r"`` or
          ``"w"``

        :type path: str

        :return:
          handle to the opened file

        :rtype: object
        """
        raise NotImplementedError

    def read(self, file_handle, length=None):
        """Reads from a file.

        :param file_handle: the file handle as returned by `open`.
        :param length: number of bytes to read; if ``None``, read until the end
          of the file.

        :type file_handle: object
        :param length: int

        :return:
          the read data

        :rtype: bytes
        """
        raise NotImplementedError

    def close(self, file_handle):
        """Closes a file.

        :param file_handle: the file handle as returned by `open`.

        :type file_handle: object
        """
        raise NotImplementedError

    def write(self, file_handle, data):
        """Writes to a file.

        :param file_handle: the file handle as returned by `open`.
        :param data: the data to be written

        :type file_handle: object
        :param data: bytes
        """
        raise NotImplementedError

    def export(self, path):
        """Returns a removable path to the file.  This is used when serving
        files.  The Web server gets the result of this method in the
        ``X-Sendfile`` header, serves the file content at this path directly to
        the client, and unlinks the path afterwards.  For obvious reasons, this
        unlinking must not remove the original file.

        Note that the resulting path should be unlinked afterwards (e.g. by the
        Web server, or in ``/tmp`` after a reboot), else, a temporary file is
        staying around.

        :param path: absolute path to a file

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
    """

    def __init__(self, root):
        """Class constructor.

        :param root: root directory of the file system storage of BLOB files

        :type root: str
        """
        self.root = root

    def unlink(self, path):
        os.unlink(os.path.join(self.root, path))

    def open(self, path, mode):
        return open(os.path.join(self.root, path), mode + "b")

    def write(self, file_handle, data):
        file_handle.write(data)

    def close(self, file_handle):
        file_handle.close()

    def export(self, path):
        path = os.path.join(self.root, path)
        filename = str(uuid.uuid4())
        result = os.path.join("/tmp", filename)
        try:
            os.link(path, result)
        except OSError:
            result = os.path.join(os.path.dirname(path), filename)
            os.link(path, result)
        return result


class PostgreSQL(BlobStorage):
    """PostgreSQL large objects backend.  It stores all blobs in a PostgreSQL
    database using PostgreSQL's “large object” facility.  Moreover, it creates
    one table called “blobs” in the database to link the large object IDs
    (OIDs) with the pathname and an mtime timestamp.
    """

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
            large_object = connection.lobject(oid)
            try:
                yield large_object, cursor
            finally:
                if not large_object.closed:
                    large_object.close()

    def unlink(self, path):
        with self.existing_large_object(path) as (large_object, cursor):
            cursor.execute("DELETE FROM blobs WHERE large_object_id=%s;", (large_object.oid,))
            large_object.unlink()

    def open(self, path, mode):
        assert mode == "w"
        connection = psycopg2.connect(database=self.database, user=self.user, password=self.password, host=self.host)
        cursor = connection.cursor()
        oid = self.get_oid(cursor, path)
        if oid is None:
            large_object = connection.lobject(mode="wb")
            cursor.execute("INSERT INTO blobs VALUES (%s, %s, now());", (path, large_object.oid))
        else:
            large_object = connection.lobject(oid, mode="wb")
            large_object.truncate()
        return (path, connection, cursor, large_object)

    def write(self, file_handle, data):
        path, connection, cursor, large_object = file_handle
        large_object.write(data)

    def close(self, file_handle):
        path, connection, cursor, large_object = file_handle
        cursor.execute("UPDATE blobs SET mtime=now() WHERE path=%s;", (path,))
        large_object.close()
        connection.commit()
        cursor.close()
        connection.close()

    def export(self, path):
        with self.existing_large_object(path) as (large_object, cursor):
            large_object.export(os.path.join("/tmp", str(uuid.uuid4())))
