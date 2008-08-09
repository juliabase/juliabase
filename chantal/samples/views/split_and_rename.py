#!/usr/bin/env python
# -*- coding: utf-8 -*-

@login_required
def split_and_rename(request, sample_name):
    lookup_result = utils.lookup_sample(sample_name)
    if lookup_result:
        return lookup_result
