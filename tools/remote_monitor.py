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


from __future__ import unicode_literals
import urllib, urllib2, cookielib, time, logging, os.path
import smtplib
from email.MIMEText import MIMEText

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("~/chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='/windows/hobie/chantal_monitoring/remote_monitor.log',
                    filemode='a')

opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
opener.addheaders = [("User-agent", "Chantal-Remote/0.1")]

def test_connection():
    response = opener.open("https://chantal.ipv.kfa-juelich.de/login_remote_client",
                           urllib.urlencode({"username": credentials["monitor_login"],
                                             "password": credentials["monitor_password"]}, doseq=True))
    is_json = response.info()["Content-Type"].startswith("application/json")
    if not is_json:
        raise Exception("Login response was not JSON.")
    elif response.read() != "true":
        raise Exception("""Login response was not "true".""")
    response = opener.open("http://chantal.ipv.kfa-juelich.de/logout_remote_client")
    is_json = response.info()["Content-Type"].startswith("application/json")
    if not is_json:
        raise Exception("Logout response was not JSON.")
    elif response.read() != "true":
        raise Exception("""Logout response was not "true".""")

def send_error_email(error_message):
    s = smtplib.SMTP("mailrelay.fz-juelich.de")
    message = MIMEText(
        "Der automatische Chantal-Monitor meldet folgenden Fehler:\n{0}".format(error_message).encode("utf-8"),
        _charset = "utf-8")
    message["Subject"] = "Chantal-Monitor Fehlerbericht"
    message["From"] = "t.bronger@fz-juelich.de"
    message["To"] = "chantal-admins@googlegroups.com"
    s.sendmail("t.bronger@fz-juelich.de", ["chantal-admins@googlegroups.com"], message.as_string())
    s.quit()

while True:
    try:
        test_connection()
    except Exception as e:
        message = unicode(type(e)) + ": " + unicode(e)
        logging.error(message)
        try:
            send_error_email(message)
        except Exception as e:
            logging.critical("Error email could not be sent: " + unicode(e))
    else:
        logging.info("Remote host was successfully tested.")
    time.sleep(60)
