#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, urllib2, cookielib, time, logging, os.path
import smtplib
from email.MIMEText import MIMEText

import ConfigParser
credentials = ConfigParser.SafeConfigParser()
credentials.read(os.path.expanduser("chantal.auth"))
credentials = dict(credentials.items("DEFAULT"))

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='remote_monitor.log',
                    filemode='a')

opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
opener.addheaders = [("User-agent", "Chantal-Remote/0.1")]

def test_connection():
    response = opener.open("http://bob.ipv.kfa-juelich.de/chantal/login_remote_client",
                           urllib.urlencode({"username": credentials["monitor_login"],
                                             "password": credentials["monitor_password"]}, doseq=True))
    is_json = response.info()["Content-Type"].startswith("application/json")
    if not is_json:
        raise Exception("Login response was not JSON.")
    elif response.read() != "true":
        raise Exception("""Login response was not "true".""")
    response = opener.open("http://bob.ipv.kfa-juelich.de/chantal/logout_remote_client")
    is_json = response.info()["Content-Type"].startswith("application/json")
    if not is_json:
        raise Exception("Logout response was not JSON.")
    elif response.read() != "true":
        raise Exception("""Logout response was not "true".""")

def send_error_email(error_message):
    s = smtplib.SMTP("mailrelay.fz-juelich.de")
    message = MIMEText((u"Der automatische Chantal-Monitor meldet folgenden Fehler:\n%s" %
                        error_message).encode("utf-8"), _charset = "utf-8")
    message["Subject"] = "Chantal-Monitor Fehlerbericht"
    message["From"] = "t.bronger@fz-juelich.de"
    message["To"] = "bronger@physik.rwth-aachen.de"
    s.sendmail("t.bronger@fz-juelich.de", ["bronger@physik.rwth-aachen.de"], message.as_string())
    s.quit()

while True:
    try:
        test_connection()
    except Exception, e:
        logging.error(unicode(e))
        try:
            send_error_email(unicode(e))
        except Exception, e:
            logging.critical("Error email could not be sent: " + unicode(e))
    else:
        logging.info("Remote host was successfully tested.")
    time.sleep(60)
