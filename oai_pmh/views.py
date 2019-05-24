#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# This file is part of JuliaBase, see http://www.juliabase.org.
# Copyright © 2008–2017 Forschungszentrum Jülich GmbH, Jülich, Germany
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime
from functools import lru_cache
from xml.etree import ElementTree
from xml.etree.ElementTree import SubElement
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.timezone import make_aware, utc
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.http import HttpResponse, Http404
from jb_common.utils.base import get_all_models
from samples.models import Process


class HttpPmhResponse(HttpResponse):
    def __init__(self, tree):
        super().__init__(ElementTree.tostring(tree, encoding="utf8", method="xml"), content_type="application/xml")


def timestamp_isoformat(timestamp):
    timestamp = timestamp.isoformat(timespec="seconds")
    assert timestamp.endswith("+00:00")
    timestamp = timestamp[:-6]
    return timestamp


@lru_cache()
def get_all_processes():
    all_processes = {}
    for model in get_all_models().values():
        if issubclass(model, Process):
            permission_codename = "edit_permissions_for_{0}".format(model.__name__.lower())
            content_type = ContentType.objects.get_for_model(model)
            try:
                Permission.objects.get(codename=permission_codename, content_type=content_type)
            except Permission.DoesNotExist:
                continue
            else:
                all_processes[model.__name__] = model
    return all_processes


def create_response_tree(request):
    tree = ElementTree.Element("OAI-PMH", {"xmlns": "http://www.openarchives.org/OAI/2.0/",
                                           "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                           "xsi:schemaLocation": "http://www.openarchives.org/OAI/2.0/ "
                                           "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"})
    timestamp = timestamp_isoformat(timezone.now())
    SubElement(tree, "responseDate").text = timestamp
    request_element = SubElement(tree, "request")
    request_element.text = request.build_absolute_uri(request.path)
    for key, value in request.GET.items():
        request_element.attrib[key] = value
    return tree


def get_record(request):
    tree = create_response_tree(request)
    response_element = ElementTree.Element("GetRecord")
    header = SubElement(response_element, "header")
    SubElement(header, "identifier").text = "1"
    SubElement(header, "datestamp").text = timezone.now().date().isoformat()
    SubElement(header, "setSpec").text = "all"
    dublin_core = SubElement(SubElement(response_element, "metadata"), "oai_dc:dc",
                             {"xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
                              "xmlns:dc": "http://purl.org/dc/elements/1.1/",
                              "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                              "xsi:schemaLocation": "http://www.openarchives.org/OAI/2.0/oai_dc/ "
                              "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"})
    SubElement(dublin_core, "dc:title").text = "Toller Titel"
    tree.append(response_element)
    return HttpPmhResponse(tree)


def identify(request):
    tree = create_response_tree(request)
    response_element = ElementTree.Element("Identify")
    SubElement(response_element, "repositoryName").text = "JuliaBase"
    SubElement(response_element, "baseURL").text = request.build_absolute_uri(request.path)
    SubElement(response_element, "protocolVersion").text = "2.0"
    timestamp = cache.get("oai-pmh:first-timestamp")
    if not timestamp:
        first_process = Process.objects.first()
        timestamp = first_process.timestamp if first_process else datetime.datetime(1900, 0, 0)
        cache.set("oai-pmh:first-timestamp", timestamp, 3600)
    SubElement(response_element, "earliestDatestamp").text = timestamp_isoformat(timestamp)
    SubElement(response_element, "deletedRecord").text = "no"
    SubElement(response_element, "granularity").text = "YYYY-MM-DDThh:mm:ssZ"
    SubElement(response_element, "adminEmail").text = settings.ADMINS[0][1]
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_identifiers(request):
    def process_model(response_element, model, from_, until):
        query = model.objects.values_list("pk", "timestamp")
        if from_:
            query = query.filter(timestamp__gte=from_)
        if until:
            query = query.filter(timestamp__lte=until)
        for id_, timestamp in query.iterator():
            header = SubElement(response_element, "header")
            SubElement(header, "identifier").text = model.__name__ + ":" + str(id_)
            SubElement(header, "datestamp").text = timestamp.date().strftime("%Y-%m-%d")
            SubElement(header, "setSpec").text = "all"
            SubElement(header, "setSpec").text = model.__name__
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListIdentifiers")
    assert request.GET["metadataPrefix"] == "oai_dc"
    from_ = request.GET.get("from")
    if from_:
        assert from_[-1] == "Z"
        from_ = make_aware(datetime.datetime.strptime(from_[:-1], "%Y-%m-%dT%H:%M:%S"), utc)
    until = request.GET.get("until")
    if until:
        assert until[-1] == "Z"
        until = make_aware(datetime.datetime.strptime(until[:-1], "%Y-%m-%dT%H:%M:%S"), utc)
    set_spec = request.GET.get("set", "all")
    if set_spec == "all":
        for model in get_all_processes().values():
            process_model(response_element, model, from_, until)
    else:
        process_model(response_element, get_all_processes()[set_spec], from_, until)
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_metadata_formats(request):
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListMetadataFormats")
    oai_dc = SubElement(response_element, "metadataFormat")
    SubElement(oai_dc, "metadataPrefix").text = "oai_dc"
    SubElement(oai_dc, "schema").text = "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
    SubElement(oai_dc, "metadataNamespace").text = "http://www.openarchives.org/OAI/2.0/oai_dc/"
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_records(request):
    def process_model(response_element, model, from_, until):
        query = model.objects.all()
        if from_:
            query = query.filter(timestamp__gte=from_)
        if until:
            query = query.filter(timestamp__lte=until)
        for process in query.iterator():
            record = SubElement(response_element, "record")
            header = SubElement(record, "header")
            SubElement(header, "identifier").text = model.__name__ + ":" + str(process.pk)
            SubElement(header, "datestamp").text = process.timestamp.date().strftime("%Y-%m-%d")
            SubElement(header, "setSpec").text = "all"
            SubElement(header, "setSpec").text = model.__name__
            metadata = SubElement(record, "metadata")
            oai_dc = SubElement(metadata, "oai_dc:dc", {"xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
                                                        "xmlns:dc": "http://purl.org/dc/elements/1.1/",
                                                        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                                        "xsi:schemaLocation": "http://www.openarchives.org/OAI/2.0/ "
                                                        "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"})
            SubElement(oai_dc, "dc:identifier").text = model.__name__ + ":" + str(process.pk)
            SubElement(oai_dc, "dc:title").text = str(process)
            SubElement(oai_dc, "dc:creator").text = str(process.operator)
            SubElement(oai_dc, "dc:date").text = process.timestamp.date().strftime("%Y-%m-%d")
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListRecords")
    assert request.GET["metadataPrefix"] == "oai_dc"
    from_ = request.GET.get("from")
    if from_:
        assert from_[-1] == "Z"
        from_ = make_aware(datetime.datetime.strptime(from_[:-1], "%Y-%m-%dT%H:%M:%S"), utc)
    until = request.GET.get("until")
    if until:
        assert until[-1] == "Z"
        until = make_aware(datetime.datetime.strptime(until[:-1], "%Y-%m-%dT%H:%M:%S"), utc)
    set_spec = request.GET.get("set", "all")
    if set_spec == "all":
        for model in get_all_processes().values():
            process_model(response_element, model, from_, until)
    else:
        process_model(response_element, get_all_processes()[set_spec], from_, until)
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_sets(request):
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListSets")
    set_element = SubElement(response_element, "set")
    SubElement(set_element, "setSpec").text = "all"
    SubElement(set_element, "setName").text = "all processes of the database"
    for model_name, model in get_all_processes().items():
        set_element = SubElement(response_element, "set")
        SubElement(set_element, "setSpec").text = model_name
        SubElement(set_element, "setName").text = str(model._meta.verbose_name_plural)
    tree.append(response_element)
    return HttpPmhResponse(tree)


views = {"GetRecord": get_record, "Identify": identify, "ListIdentifiers": list_identifiers,
         "ListMetadataFormats": list_metadata_formats, "ListRecords": list_records, "ListSets": list_sets}

def root(request):
    """TBD

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    verb = request.GET.get("verb")
    view_function = views.get(verb)
    if view_function:
        return view_function(request)
    else:
        raise Http404
