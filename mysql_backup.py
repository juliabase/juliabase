#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime, os.path, subprocess, pickle, logging

logging.basicConfig(level=logging.DEBUG,
                    format="%(asctime)s %(levelname)-8s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                    filename="/home/bronger/backups/mysql/mysql_backup.log",
                    filemode="a")

pickle_filename = "/home/bronger/backups/dump_rotation.pickle"

class DumpRotation(object):
    def __init__(self, backup_dir="/home/bronger/backups/mysql/"):
        self.backup_dir = backup_dir
        self.queue_hourly = []
        self.queue_daily = []
        self.queue_weekly = []
        self.queue_monthly = []
        self.queue_yearly = []
        self.index_hourly = self.index_daily = self.index_weekly = self.index_monthly = self.index_yearly = 0
    def create_backup(self):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M")
        filename = os.path.join(self.backup_dir, "mysql_dump_%s.sql.gz" % timestamp)
        outfile = open(filename, "wb")
        mysqldump = subprocess.Popen(["mysqldump", "--user=root", "--password=Sonne", "--compact"], stdout=subprocess.PIPE)
        gzip = subprocess.Popen(["gzip"], stdin=mysqldump.stdout, stdout=outfile)
        return_code_gzip = gzip.wait()
        outfile.close()
        return_code_mysqldump = mysqldump.wait()
        if return_code_mysqldump != 0:
            logging.error("mysqldump returned with exit code %d." % return_code_mysqldump)
        if return_code_gzip != 0:
            logging.error("gzip returned with exit code %d." % return_code_gzip)
        if return_code_mysqldump != 0 or return_code_gzip != 0:
            try:
                os.remove(filename)
            except OSError:
                pass
        else:
            self.rotate(filename)
            logging.info("Database dump was successfully created at \"%s\"." % filename)
    def rotate(self, filename):
        def process_queue(queue, next_queue, index, index_max):
            if len(queue) >= index_max:
                if index >= index_max:
                    next_queue.insert(0, queue[-1])
                    index = 0
                else:
                    os.remove(queue[-1])
                    index += 1
                del queue[-1]
            return index

        self.queue_hourly.insert(0, filename)
        self.index_hourly = process_queue(self.queue_hourly, self.queue_daily, self.index_hourly, 24)
        self.index_daily = process_queue(self.queue_daily, self.queue_weekly, self.index_daily, 7)
        self.index_weekly = process_queue(self.queue_weekly, self.queue_monthly, self.index_weekly, 4)
        self.index_monthly = process_queue(self.queue_monthly, self.queue_yearly, self.index_yearly, 12)

try:
    dump_rotation = pickle.load(open(pickle_filename, "rb"))
except IOError:
    dump_rotation = DumpRotation()

dump_rotation.create_backup()

pickle.dump(dump_rotation, open(pickle_filename, "wb"))
