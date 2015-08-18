#!/usr/bin/env python
# -*- coding: utf-8 -*-

from django.db import models
from samples.models.common import PhysicalProcess



class SputterCleaning(PhysicalProcess):

    gas = models.CharField("Gas/Ionenart", max_length=30)

