#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal_remote import *

login("testuser", "*****")

samples = new_samples(number_of_depositions, u"unknown; legacy data")

six_chamber_deposition = SixChamberDeposition(samples)
six_chamber_deposition.timestamp = "2008-09-15 22:29:00"

layer = SixChamberLayer(six_chamber_deposition)
layer.chamber = "#1"

channel1 = SixChamberChannel(layer)
channel1.number = 1
channel1.gas = "SiH4"
channel1.flow_rate = "1"

channel2 = SixChamberChannel(layer)
channel2.number = 2
channel2.gas = "SiH4"
channel2.flow_rate = "2"

channel3 = SixChamberChannel(layer)
channel3.number = 3
channel3.gas = "SiH4"
channel3.flow_rate = "3"

six_chamber_deposition.layers.extend([layer, layer])

six_chamber_deposition.submit()

logout()
