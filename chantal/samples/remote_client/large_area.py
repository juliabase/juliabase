#!/usr/bin/env python
# -*- coding: utf-8 -*-

from chantal_remote import *

login("bronger", "Rigel")

sample = new_samples(1, u"Großflächige-Labor")

deposition = LargeAreaDeposition(sample)
deposition.timestamp = "2008-09-26 18:00:00"

layer = LargeAreaLayer(deposition)
layer.date = "2008-09-26"
layer.layer_type = "p"
layer.station = "1"
layer.sih4 = layer.h2 = layer.sc = layer.power = layer.pressure = \
    layer.temperature = layer.time = layer.electrodes_distrance = 1
layer.hf_frequency = "13.56"
layer.electrode = "NN large PC1"

deposition.submit()
logout()
