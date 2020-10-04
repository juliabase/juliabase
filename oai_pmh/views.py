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

"""Views for the OAI-PMH app.  Here, I implement everything realising the
OAI-PMH protocol.

Todos:

- resumptionToken is not implemented at all.  It may be advisable to implement
  it at least for `ListIdentifiers` and `ListRecords`.
- Besides oai_dc, I need to implement Dataverse’s own OAI_PMH metadata format,
  filling the fields with the same content also used for CSV export.
- Authentication needs to be added by moving the root of the OAI-PMH endpoints
  into a secret subpath like ``https://jb.example.com/krz54kr9182ad/oai-pmh/``.
"""

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


def timestamp_isoformat(timestamp):
    """Convert a timestamp into ISO 8601 format with Zulu time zone.

    :param datetime.datetime timestamp: timestamp to be converted; it must be
      time zone aware and in UTC

    :returns:
      the ISO 8601 timestamp

    :rtype: str
    """
    timestamp = timestamp.isoformat(timespec="seconds")
    assert timestamp.endswith("+00:00")
    timestamp = timestamp[:-6] + "Z"
    return timestamp


def escape_pk(pk):
    """Returns the escaped version of the PK (primary key).  The primary key is
    concetanated with the model name to the identifier, with a colon in
    between.  Thus, to be able to saftly parse this string and extract both
    components, I need to escape all colons in the primary key.

    :param object pk: the primary key

    :returns:
      the escaped version of the PK, guaranteed to be without any no colon

    :rtype: str
    """
    return str(pk).replace("\\", "\\\\").replace(":", "\\-")


def unescape_pk(pk):
    """Unescaped the primary key.  This is the inverse of `escape_pk`.

    :param str pk: the escaped primary key

    :returns:
      the original PK; note that this is always a string, even though it may
      have originally be an int

    :rtype: str
    """
    return pk.replace("\\-", ":").replace("\\\\", "\\")


@lru_cache()
def get_all_processes():
    """Returns all editable processes in this JuliaBase instance.  It is heavily
    inspired from `permissions.get_addable_models`.  The result is cached, so
    you may call this function as often as you like.

    :returns:
      dictionary mapping model class names to model classes

    :rtype: dict[str, Process]
    """
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


class HttpPmhResponse(HttpResponse):
    """HTTP response class for OAI-PMH responses.  It takes an XML tree and
    serialises it appropriately.
    """
    def __init__(self, tree):
        super().__init__(ElementTree.tostring(tree, encoding="utf8", method="xml"), content_type="application/xml")


def create_response_tree(request):
    """Creates an XML tree with fixed OAI-PMH elements.  In particular, it contains
    the ``<responseDate>`` and ``<request>`` elements.

    :param HttpRequest request: the original HTTP request object

    :returns:
      an XML tree ready to be filled with the result of the OAI-PMH request

    :rtype: ElementTree.ElementTree
    """
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


class PmhError(Exception):
    """Exception class of OAI-PMH errors.
    """

    def __init__(self, code, description=""):
        """Class constructor.

        :param str code: error code according to
          <http://www.openarchives.org/OAI/openarchivesprotocol.html#ErrorConditions>.
        :param str description: optional human-readable description of the
          error condition.
        """
        self.code, self.description = code, description

    def response(self, request):
        """Returns a HTTP response object representing the error condition.

        :param HttpRequest request: the original HTTP request object

        :returns:
          HTTP response object representing the error condition

        :rtype: HttpPmhResponse
        """
        tree = create_response_tree(request)
        response_element = ElementTree.Element("error", {"code": self.code})
        response_element.text = self.description
        tree.append(response_element)
        return HttpPmhResponse(tree)


def parse_timestamp(request, query_string_key):
    """Returns the timestamp found in the query string.  Note that the timestamp
    may be optional, so this function may return ``None``.

    :param HttpRequest request: the original HTTP request object
    :param str query_string_key: name of the query string parameter containing
      the timestamp

    :returns:
      the timestamp, or ``None`` of none was given

    :rtype: datetime.datetime or ``NoneType``
    """
    timestamp = request.GET.get(query_string_key)
    if timestamp:
        try:
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise PmhError("badArgument", "The timestamp has an invalid format.")
        timestamp = make_aware(timestamp, utc)
    return timestamp


def build_record(process):
    """Returns the metadata record for the given process, ready to be included into
    an OAI-PMH response.

    :param Process process: the process to build a record for

    :returns:
      the XML fragment with the ``<record>`` element as the top-level element
      representing the data for the given process.

    :rtype: ElementTree.ElementTree
    """
    record = ElementTree.Element("record")
    header = SubElement(record, "header")
    SubElement(header, "identifier").text = process.__class__.__name__ + ":" + escape_pk(process.pk)
    SubElement(header, "datestamp").text = process.timestamp.date().strftime("%Y-%m-%d")
    SubElement(header, "setSpec").text = "all"
    SubElement(header, "setSpec").text = process.__class__.__name__
    metadata = SubElement(record, "metadata")
    oai_dc = SubElement(metadata, "oai_dc:dc", {"xmlns:oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
                                                "xmlns:dc": "http://purl.org/dc/elements/1.1/",
                                                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                                "xsi:schemaLocation": "http://www.openarchives.org/OAI/2.0/ "
                                                "http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd"})
    SubElement(oai_dc, "dc:identifier").text = process.__class__.__name__ + ":" + escape_pk(process.pk)
    SubElement(oai_dc, "dc:title").text = str(process)
    SubElement(oai_dc, "dc:creator").text = str(process.operator)
    SubElement(oai_dc, "dc:date").text = process.timestamp.date().strftime("%Y-%m-%d")
    return record


def get_record(request):
    """Handles the ``GetRecord`` verb of the OAI-PMH protocol.

    :param HttpRequest request: the original HTTP request object

    :returns:
      the HTTP response to the request

    :rtype: HttpPmhResponse
    """
    tree = create_response_tree(request)
    response_element = ElementTree.Element("GetRecord")
    try:
        if request.GET["metadataPrefix"] != "oai_dc":
            raise PmhError("cannotDisseminateFormat", "Only oai_dc is allowed currently")
    except KeyError:
        raise PmhError("badArgument", "metadataPrefix is missing")
    try:
        model_name, colon, pk = request.GET["identifier"].rpartition(":")
    except KeyError:
        raise PmhError("identifier is missing")
    pk = unescape_pk(pk)
    if colon != ":" or model_name not in get_all_processes():
        raise PmhError("identifier is invalid")
    model = get_all_processes()[model_name]
    try:
        process = model.objects.get(pk=pk)
    except model.DoesNotExist:
        raise PmhError("idDoesNotExist")
    response_element.append(build_record(process))
    tree.append(response_element)
    return HttpPmhResponse(tree)


def identify(request):
    """Handles the ``Identify`` verb of the OAI-PMH protocol.

    :param HttpRequest request: the original HTTP request object

    :returns:
      the HTTP response to the request

    :rtype: HttpPmhResponse
    """
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
    """Handles the ``ListIdentifiers`` verb of the OAI-PMH protocol.

    :param HttpRequest request: the original HTTP request object

    :returns:
      the HTTP response to the request

    :rtype: HttpPmhResponse
    """
    def process_model(response_element, model, from_, until):
        query = model.objects.values_list("pk", "timestamp")
        if from_:
            query = query.filter(timestamp__gte=from_)
        if until:
            query = query.filter(timestamp__lte=until)
        if not query.exists():
            raise PmhError("noRecordsMatch")
        for id_, timestamp in query.iterator():
            header = SubElement(response_element, "header")
            SubElement(header, "identifier").text = model.__name__ + ":" + escape_pk(id_)
            SubElement(header, "datestamp").text = timestamp.date().strftime("%Y-%m-%d")
            SubElement(header, "setSpec").text = "all"
            SubElement(header, "setSpec").text = model.__name__
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListIdentifiers")
    try:
        if request.GET["metadataPrefix"] != "oai_dc":
            raise PmhError("cannotDisseminateFormat", "Only oai_dc is allowed currently")
    except KeyError:
        raise PmhError("badArgument", "metadataPrefix is missing")
    from_ = parse_timestamp(request, "from")
    until = parse_timestamp(request, "until")
    set_spec = request.GET.get("set", "all")
    if set_spec == "all":
        for model in get_all_processes().values():
            process_model(response_element, model, from_, until)
    else:
        process_model(response_element, get_all_processes()[set_spec], from_, until)
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_metadata_formats(request):
    """Handles the ``ListMetadataFormats`` verb of the OAI-PMH protocol.

    :param HttpRequest request: the original HTTP request object

    :returns:
      the HTTP response to the request

    :rtype: HttpPmhResponse
    """
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListMetadataFormats")
    oai_dc = SubElement(response_element, "metadataFormat")
    SubElement(oai_dc, "metadataPrefix").text = "oai_dc"
    SubElement(oai_dc, "schema").text = "http://www.openarchives.org/OAI/2.0/oai_dc.xsd"
    SubElement(oai_dc, "metadataNamespace").text = "http://www.openarchives.org/OAI/2.0/oai_dc/"
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_records(request):
    """Handles the ``ListRecords`` verb of the OAI-PMH protocol.

    :param HttpRequest request: the original HTTP request object

    :returns:
      the HTTP response to the request

    :rtype: HttpPmhResponse
    """
    def process_model(response_element, model, from_, until):
        query = model.objects.all()
        if from_:
            query = query.filter(timestamp__gte=from_)
        if until:
            query = query.filter(timestamp__lte=until)
        if not query.exists():
            raise PmhError("noRecordsMatch")
        for process in query.iterator():
            response_element.append(build_record(process))
    tree = create_response_tree(request)
    response_element = ElementTree.Element("ListRecords")
    try:
        if request.GET["metadataPrefix"] != "oai_dc":
            raise PmhError("cannotDisseminateFormat", "Only oai_dc is allowed currently")
    except KeyError:
        raise PmhError("badArgument", "metadataPrefix is missing")
    from_ = parse_timestamp(request, "from")
    until = parse_timestamp(request, "until")
    set_spec = request.GET.get("set", "all")
    if set_spec == "all":
        for model in get_all_processes().values():
            process_model(response_element, model, from_, until)
    else:
        try:
            model = get_all_processes()[set_spec]
        except KeyError:
            raise PmhError("badArgument", "This set name is unknown")
        process_model(response_element, model, from_, until)
    tree.append(response_element)
    return HttpPmhResponse(tree)


def list_sets(request):
    """Handles the ``ListSets`` verb of the OAI-PMH protocol.

    :param HttpRequest request: the original HTTP request object

    :returns:
      the HTTP response to the request

    :rtype: HttpPmhResponse
    """
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
    """Implements the single endpoint of the OAI-PMH server.  Thus, this view is a
    dispatch for the functions above that hangle the OAI-PMH verbs.

    :param request: the current HTTP Request object

    :type request: HttpRequest

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    try:
        try:
            view_function = views[request.GET["verb"]]
        except KeyError:
            raise PmhError("badVerb")
        return view_function(request)
    except PmhError as error:
        return error.response(request)
