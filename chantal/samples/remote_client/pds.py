#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal_remote import *

login("bronger", "*******")

pds_measurement = PDSMeasurement("*100")
pds_measurement.number = 3511
pds_measurement.timestamp = "2008-08-04 10:25:11"
pds_measurement.raw_datafile = "p3500-/pd3511.dat"
pds_measurement.comments = "nur Trans\nQuarz-Linse\n"
pds_measurement.submit()

logout()
