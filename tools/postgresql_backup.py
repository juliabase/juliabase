#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.


"""This program creates backup dumps of the PostgreSQL database.  It should be
called hourly as a cron job.  It will write the backups in gzip format in the
directory ``/home/chantal/backups/postgresql/``.

The program contains a rotation scheme: Only the last 24 backups are kept, then
one of each day of the past week, then one of each week of the last four weeks,
and the same for months.
"""

from __future__ import unicode_literals
import datetime, os, os.path, subprocess, pickle, logging, socket
import ConfigParser


credentials = ConfigParser.SafeConfigParser()
credentials.read("/var/www/chantal.auth")
credentials = dict(credentials.items("DEFAULT"))


pickle_filename = "/home/chantal/backups/postgresql/dump_rotation.pickle"
try:
    os.makedirs(os.path.dirname(pickle_filename))
except OSError:
    pass


logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(levelname)-8s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    filename="/home/chantal/backups/postgresql/postgresql_backup.log",
                    filemode="a")


class DumpRotation(object):

    def __init__(self, database_name, backup_dir="/home/chantal/backups/postgresql/"):
        self.database_name, self.backup_dir = database_name, backup_dir
        if not self.backup_dir.endswith("/"):
            self.backup_dir += "/"
        self.queue_hourly = []
        self.queue_daily = []
        self.queue_weekly = []
        self.queue_monthly = []
        self.queue_yearly = []
        self.index_hourly = self.index_daily = self.index_weekly = self.index_monthly = 0

    def create_backup(self):
        """Create a new backup dump and also do the rotation.  In other words,
        this implicitly calls `rotate`.
        """
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = os.path.join(self.backup_dir, "postgresql_dump_{0}_{1}.sql.gz".format(self.database_name, timestamp))
        outfile = open(filename, "wb")
        postgresql_dump = subprocess.Popen(["pg_dump", "--username=" + credentials["postgresql_user"],
                                            "--host=192.168.26.132", self.database_name],
                                           stdout=subprocess.PIPE, env={"PGPASSWORD": credentials["postgresql_password"]})
        gzip = subprocess.Popen(["gzip"], stdin=postgresql_dump.stdout, stdout=outfile)
        return_code_gzip = gzip.wait()
        outfile.close()
        return_code_postgresql_dump = postgresql_dump.wait()
        if return_code_postgresql_dump != 0:
            logging.error("Database dump failed; postgresql_dump returned with exit code {0}."
                          .format(return_code_postgresql_dump))
        if return_code_gzip != 0:
            logging.error("Database dump failed; gzip returned with exit code {0}.".format(return_code_gzip))
        if return_code_postgresql_dump != 0 or return_code_gzip != 0:
            try:
                os.remove(filename)
            except OSError:
                pass
        else:
            self.rotate(filename)
            logging.info("""Database dump was successfully created at "{0}".""".format(filename))

    def rotate(self, filename):
        """Does the backup rotation.  It adds a new file to the repository (it must
        exist already) and removes files that are too old from both the
        repository and from the backup directory.

        (With “repository” I mean the queue-like datastructure in memory, not
        the physical files on the hard disk.)

        :Parameters:
          - `filename`: full path to the backup file to add

        :type filename: str
        """
        def process_queue(queue, next_queue, index, index_max, index_threshold=None):
            if index_threshold is None:
                index_threshold = index_max
            assert index_max % index_threshold == 0 and index_threshold <= index_max  # Otherwise, files get lost
            if len(queue) > index_threshold:
                if index == 0:
                    next_queue.insert(0, queue[index_threshold])
                    index = index_threshold
                else:
                    if len(queue) > index_max:
                        os.remove(queue[-1])
                index -= 1
                if len(queue) > index_max:
                    del queue[-1]
            return index

        self.queue_hourly.insert(0, filename)
        self.index_hourly = process_queue(self.queue_hourly, self.queue_daily, self.index_hourly, 72, 24)
        self.index_daily = process_queue(self.queue_daily, self.queue_weekly, self.index_daily, 7)
        self.index_weekly = process_queue(self.queue_weekly, self.queue_monthly, self.index_weekly, 4)
        self.index_monthly = process_queue(self.queue_monthly, self.queue_yearly, self.index_monthly, 12)

    def print_queues(self):
        """Just for debugging."""
        def print_queue(name, queue):
            print name + ":"
            for i in queue:
                print "  ", i
        print_queue("Hourly queue", self.queue_hourly)
        print_queue("Daily queue", self.queue_daily)
        print_queue("Weekly queue", self.queue_weekly)
        print_queue("Monthly queue", self.queue_monthly)
        print_queue("Yearly queue", self.queue_yearly)


def copy_to_sonne():
    """Synchronises the local backup directory with the “sonne” server.  Note
    that this also implies that outdated (and therefore removed) backup files
    are removed from sonne, too.
    """
    result_code = subprocess.call(["rsync", "--modify-window=2", "-a", "--delete", "/home/chantal/backups/postgresql/",
                                   "/mnt/sonne/datenbank/chantal/backups/"])
    if result_code == 0:
        logging.info("Database backups were successfully copied to sonne.")
    else:
        logging.error("Copying of database tables to sonne failed.")


try:
    dump_rotations = pickle.load(open(pickle_filename, "rb"))
except IOError:
    dump_rotations = set(DumpRotation(database_name) for database_name in ["chantal", "trac"])
for dump_rotation in dump_rotations:
    dump_rotation.create_backup()
pickle_file = open(pickle_filename, "wb")
pickle.dump(dump_rotations, pickle_file)
pickle_file.close()
copy_to_sonne()

# FixMe: The following lines are only necessary because we don't have a shared
# cluster file system.
logging.shutdown()
other_node = "mandy" if socket.gethostname() == "olga" else "olga"
backup_dir = "/home/chantal/backups/postgresql/"
subprocess.check_call(["ssh", other_node, "mkdir -p " + backup_dir])
subprocess.check_call(["rsync", "-a", "--delete", backup_dir, other_node + ":" + backup_dir])
