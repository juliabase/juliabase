#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib, urllib2, cookielib, pickle, time, logging
import smtplib
from email.MIMEText import MIMEText

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename='remote_monitor.log',
                    filemode='a')

opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookielib.CookieJar()))
opener.addheaders = [("User-agent", "Chantal-Remote/0.1")]

def test_connection():
    response = opener.open("http://bob.ipv.kfa-juelich.de/chantal/login_remote_client",
                           urllib.urlencode({"username": "bronger", "password": "*******"}, doseq=True))
    is_pickled = response.info()["Content-Type"].startswith("text/x-python-pickle")
    if not is_pickled:
        raise Exception("Login response was not pickled.")
    elif not pickle.load(response):
        raise Exception("Login response was not True.")
    response = opener.open("http://bob.ipv.kfa-juelich.de/chantal/logout_remote_client")
    is_pickled = response.info()["Content-Type"].startswith("text/x-python-pickle")
    if not is_pickled:
        raise Exception("Logout response was not pickled.")
    elif not pickle.load(response):
        raise Exception("Logout response was not True.")

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
