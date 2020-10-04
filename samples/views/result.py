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


"""Views for editing and creating results (aka result processes).
"""
# FixMe: The save_to_database function triggers a signal in institute when a
# new result process is connected to a sample.  If you want to change the
# behavior of this function, keep in mind that you have to check the signal for
# modification purposes.

import os, datetime, subprocess
from io import BytesIO
from functools import partial
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
import django.utils.timezone
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils.translation import ugettext_lazy as _, ugettext, pgettext_lazy
from django.utils.text import capfirst
from django.forms.utils import ValidationError
import django.forms as forms
from jb_common.utils.base import static_response, get_cached_bytes_stream, help_link
import jb_common.utils.base
import jb_common.utils.blobs
from samples import models, permissions
import samples.utils.views as utils


def save_image_file(image_data, result, related_data_form):
    """Saves an uploaded image file stream to its final destination in the blob
    store.  If the given result has already an image connected with it, it is
    removed first.

    :param image_data: the file-like object which contains the uploaded data
        stream
    :param result: The result object for which the image was uploaded.  It is
        not necessary that all its fields are already there.  But it must have
        been written already to the database because the only necessary field
        is the primary key, which I need for the hash digest for generating the
        file names.
    :param related_data_form: A bound form with the image filename that was
        uploaded.  This is only needed for dumping error messages into it if
        something went wrong.

    :type image_data: ``django.core.files.uploadedfile.UploadedFile``
    :type result: `models.Result`
    :type related_data_form: `RelatedDataForm`
    """
    for i, chunk in enumerate(image_data.chunks()):
        if i == 0:
            if chunk.startswith(b"\211PNG\r\n\032\n"):
                new_image_type = "png"
            elif chunk.startswith(b"\xff\xd8\xff"):
                new_image_type = "jpeg"
            elif chunk.startswith(b"%PDF"):
                new_image_type = "pdf"
            else:
                related_data_form.add_error("image_file", ValidationError(
                    _("Invalid file format.  Only PDF, PNG, and JPEG are allowed."), code="invalid"))
                return
            if result.image_type != "none" and new_image_type != result.image_type:
                jb_common.utils.blobs.storage.unlink(result.get_image_locations()["image_file"])
            result.image_type = new_image_type
            image_path = result.get_image_locations()["image_file"]
            destination = jb_common.utils.blobs.storage.open(image_path, "w")
        destination.write(chunk)
    destination.close()
    result.save()


class ResultForm(utils.ProcessForm):
    """Model form for a result process.  Note that I exclude many fields
    because they are not used in results or explicitly set.
    """
    class Meta:
        model = models.Result
        exclude = ("image_type", "quantities_and_values")

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["comments"].required = True
        self.fields["title"].widget.attrs["size"] = 40


class RelatedDataForm(forms.Form):
    """Form for samples, sample series, and the image connected with this
    result process.  Since all these things are not part of the result process
    model itself, they are in a form of its own.
    """
    samples = utils.MultipleSamplesField(label=capfirst(_("samples")), required=False)
    sample_series = forms.ModelMultipleChoiceField(label=capfirst(pgettext_lazy("plural", "sample series")), queryset=None,
                                                   required=False)
    image_file = forms.FileField(label=capfirst(_("image file")), required=False)

    def __init__(self, user, query_string_dict, old_result, data=None, files=None, **kwargs):
        """I have to initialise a couple of things here in
        a non-trivial way.

        The most complicated thing is to find all sample series electable for
        the result.  Note that the current query will probably find too many
        electable sample series, but unallowed series will be rejected by
        `clean` anyway.
        """
        super().__init__(data, files, **kwargs)
        self.old_relationships = set(old_result.samples.all()) | set(old_result.sample_series.all()) if old_result else set()
        self.user = user
        now = django.utils.timezone.now() + datetime.timedelta(seconds=5)
        three_months_ago = now - datetime.timedelta(days=90)
        samples = user.my_samples.all()
        important_samples = set()
        if old_result:
            important_samples.update(old_result.samples.all())
            self.fields["sample_series"].queryset = \
                models.SampleSeries.objects.filter(
                Q(samples__watchers=user) | (Q(currently_responsible_person=user) &
                                              Q(timestamp__range=(three_months_ago, now)))
                | Q(pk__in=old_result.sample_series.values_list("pk", flat=True))).distinct()
            self.fields["samples"].initial = list(old_result.samples.values_list("pk", flat=True))
            self.fields["sample_series"].initial = list(old_result.sample_series.values_list("pk", flat=True))
        else:
            if "sample" in query_string_dict:
                preset_sample = get_object_or_404(models.Sample, name=query_string_dict["sample"])
                self.fields["samples"].initial = [preset_sample.pk]
                important_samples.add(preset_sample)
            self.fields["sample_series"].queryset = \
                models.SampleSeries.objects.filter(Q(samples__watchers=user) |
                                                   (Q(currently_responsible_person=user) &
                                                     Q(timestamp__range=(three_months_ago, now)))
                                                   | Q(name=query_string_dict.get("sample_series", ""))).distinct()
            if "sample_series" in query_string_dict:
                self.fields["sample_series"].initial = \
                    [get_object_or_404(models.SampleSeries, name=query_string_dict["sample_series"])]
        self.fields["samples"].set_samples(user, samples, important_samples)
        self.fields["samples"].widget.attrs.update({"size": "17", "style": "vertical-align: top"})

    def clean(self):
        """Global clean method for the related data.  I check whether at least
        one sample or sample series was selected, and whether the user is
        allowed to add results to the selected objects.
        """
        cleaned_data = super().clean()
        samples = cleaned_data.get("samples")
        sample_series = cleaned_data.get("sample_series")
        if samples is not None and sample_series is not None:
            for sample_or_series in set(list(samples) + list(sample_series)) - self.old_relationships:
                if not permissions.has_permission_to_add_result_process(self.user, sample_or_series):
                    self.add_error(None, ValidationError(
                        _("You don't have the permission to add the result to all selected samples/series."),
                        code="forbidden"))
            if not samples and not sample_series:
                self.add_error(None, ValidationError(_("You must select at least one samples/series."), code="required"))
        return cleaned_data


class DimensionsForm(forms.Form):
    """Model form for the number of quantities and values per quantity in the
    result values table.  In other words, it is the number or columns
    (``number_of_quantities``) and the number or rows (``number_of_values``) in
    this table.

    This form class is also used for the hidden ``previous_dimensions_form``.
    It contains the values set *before* the user made his input.  Thus, one can
    decide easily whether the user has changed something, plus one can easily
    read-in the table value given by the user.  (The table had the previous
    dimensions after all.)
    """
    number_of_quantities = forms.IntegerField(label=_("Number of quantities"), min_value=0, max_value=100)
    number_of_values = forms.IntegerField(label=_("Number of values"), min_value=0, max_value=100)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["number_of_quantities"].widget.attrs.update({"size": 1, "style": "text-align: center"})
        self.fields["number_of_values"].widget.attrs.update({"size": 1, "style": "text-align: center"})

    def clean(self):
        """If one of the two dimensions is set to zero, the other is set to
        zero, too.
        """
        cleaned_data = super().clean()
        if "number_of_quantities" in cleaned_data and "number_of_values" in cleaned_data:
            if cleaned_data["number_of_quantities"] == 0 or cleaned_data["number_of_values"] == 0:
                cleaned_data["number_of_quantities"] = cleaned_data["number_of_values"] = 0
        return cleaned_data


class QuantityForm(forms.Form):
    """Form for one quantity field (i.e., one heading in the result values table).
    All HTML entities in it are immediately converted to their Unicode pendant
    (i.e., the conversion is not delayed until display, as with Markdown
    content).  Furthermore, all whitespace is normalised.
    """
    quantity = forms.CharField(label=_("Quantity name"), max_length=50)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].widget.attrs.update({"size": 10, "style": "font-weight: bold; text-align: center"})

    def clean_quantity(self):
        quantity = " ".join(self.cleaned_data["quantity"].split())
        return jb_common.utils.base.substitute_html_entities(quantity)


class ValueForm(forms.Form):
    """Form for one value entry in the result values table.  Note that this is a
    pure string field and not a number field, so you may enter whatever you
    like here.  Whitespace is not normalised, and no other conversion takes
    place.
    """
    value = forms.CharField(label=_("Value"), max_length=50, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["value"].widget.attrs.update({"size": 10})


class FormSet:
    """Class for holding all forms of the result views, and for all methods
    working on these forms.  The main advantage of putting all this into a big
    class is to avoid long parameter and return tuples because one can use
    instance attributes instead.

    :ivar result: the result to be edited.  If it is ``None``, we create a new
      one.  This is very important because testing ``result`` is the only way
      to distinguish between editing or creating.

    :ivar result_form: the form with the result process

    :ivar related_data_form: the form with all samples and sample series the
      result should be connected with

    :ivar dimensions_form: the form with the number of columns and rows in the
      result values table

    :ivar previous_dimonesions_form: the form with the number of columns and
      rows from the previous view, in order to see whether they were changed

    :ivar quantity_forms: The (mostly) bound forms of quantities (the column
      heads in the table).  Those that are newly added are unbound.  (In case
      of a GET method, all are unbound of course.)

    :ivar value_form_lists: The (mostly) bound forms of result values in the
      table.  Those that are newly added are unbound.  The outer list are the
      rows, the inner the cells in each row.  (In case of a GET method, all are
      unbound of course.)

    :ivar edit_description_form: the bound form with the edit description if
      we're editing an existing result, and ``None`` otherwise

    :type result: `samples.models.Result` or NoneType
    :type result_form: `ResultForm`
    :type related_data_form: `RelatedDataForm`
    :type dimensions_form: `DimensionsForm`
    :type previous_dimensions_form: `DimensionsForm`
    :type quantity_forms: list of `QuantityForm`
    :type value_form_lists: list of list of `ValueForm`
    :type edit_description_form: `samples.utils.views.EditDescriptionForm`
        or NoneType
    """

    def __init__(self, request, process_id):
        """Class constructor.

        :param request: the current HTTP Request object
        :param process_id: the ID of the result to be edited; ``None`` if we
            create a new one

        :type request: HttpRequest
        :type process_id: str or NoneType
        """
        self.result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id)) if process_id else None
        self.user = request.user
        self.query_string_dict = request.GET if not self.result else None

    def from_database(self):
        """Generate all forms from the database.  This is called when the HTTP
        GET method was sent with the request.
        """
        self.result_form = ResultForm(self.user, instance=self.result)
        self.related_data_form = RelatedDataForm(self.user, self.query_string_dict, self.result)
        self.edit_description_form = utils.EditDescriptionForm() if self.result else None
        if self.result:
            quantities, values = self.result.quantities_and_values
        else:
            quantities, values = [], []
        self.dimensions_form = DimensionsForm(initial={"number_of_quantities": len(quantities),
                                                       "number_of_values": len(values)})
        self.quantity_forms = [QuantityForm(initial={"quantity": quantity}, prefix=str(i))
                               for i, quantity in enumerate(quantities)]
        self.value_form_lists = []
        for j, value_list in enumerate(values):
            self.value_form_lists.append([ValueForm(initial={"value": value}, prefix="{0}_{1}".format(i, j))
                                          for i, value in enumerate(value_list)])

    def from_post_data(self, post_data, post_files):
        """Generate all forms from the database.  This is called when the HTTP
        POST method was sent with the request.

        :param post_data:  The post data submitted via HTTP.  It is the result
            of ``request.POST``.
        :param post_files: The file data submitted via HTTP.  It is the result
            of ``request.FILES``.

        :type post_data: QueryDict
        :type post_files: django.utils.datastructures.MultiValueDict
        """
        self.result_form = ResultForm(self.user, post_data, instance=self.result)
        self.related_data_form = RelatedDataForm(self.user, self.query_string_dict, self.result, post_data, post_files)
        self.dimensions_form = DimensionsForm(post_data)
        self.previous_dimensions_form = DimensionsForm(post_data, prefix="previous")
        if self.previous_dimensions_form.is_valid():
            found_number_of_quantities = self.previous_dimensions_form.cleaned_data["number_of_quantities"]
            found_number_of_values = self.previous_dimensions_form.cleaned_data["number_of_values"]
        else:
            found_number_of_quantities, found_number_of_values = 0, 0
        if self.dimensions_form.is_valid():
            number_of_quantities = self.dimensions_form.cleaned_data["number_of_quantities"]
            number_of_values = self.dimensions_form.cleaned_data["number_of_values"]
            found_number_of_quantities = min(found_number_of_quantities, number_of_quantities)
            found_number_of_values = min(found_number_of_values, number_of_values)
        else:
            number_of_quantities, number_of_values = found_number_of_quantities, found_number_of_values
        self.quantity_forms = []
        for i in range(number_of_quantities):
            self.quantity_forms.append(
                QuantityForm(post_data, prefix=str(i)) if i < found_number_of_quantities else QuantityForm(prefix=str(i)))
        self.value_form_lists = []
        for j in range(number_of_values):
            values = []
            for i in range(number_of_quantities):
                if i < found_number_of_quantities and j < found_number_of_values:
                    values.append(ValueForm(post_data, prefix="{0}_{1}".format(i, j)))
                else:
                    values.append(ValueForm(prefix="{0}_{1}".format(i, j)))
            self.value_form_lists.append(values)
        self.edit_description_form = utils.EditDescriptionForm(post_data) if self.result else None

    def _is_all_valid(self):
        """Test whether all bound forms are valid.  This routine guarantees that
        all ``is_valid()`` methods are called, even if the first tested form is
        already invalid.

        :return:
          whether all forms are valid

        :rtype: bool
        """
        all_valid = self.result_form.is_valid()
        all_valid = self.related_data_form.is_valid() and all_valid
        all_valid = self.dimensions_form.is_valid() and all_valid
        all_valid = self.previous_dimensions_form.is_valid() and all_valid
        all_valid = all([form.is_valid() for form in self.quantity_forms]) and all_valid
        all_valid = all([all([form.is_valid() for form in form_list]) for form_list in self.value_form_lists]) and all_valid
        if self.edit_description_form:
            all_valid = self.edit_description_form.is_valid() and all_valid
        return all_valid

    def _is_referentially_valid(self):
        """Test whether all forms are consistent with each other and with the
        database.  In particular, I test here whether the “important” checkbox
        in marked if the user has added new samples or sample series to the
        result.  I also assure that no two quantities in the result table
        (i.e., the column headings) are the same.

        :return:
          whether all forms are consistent with each other and the database

        :rtype: bool
        """
        referentially_valid = True
        if self.result and self.related_data_form.is_valid() and self.edit_description_form.is_valid():
            old_related_objects = set(self.result.samples.all()) | set(self.result.sample_series.all())
            new_related_objects = set(self.related_data_form.cleaned_data["samples"]) | \
                set(self.related_data_form.cleaned_data["sample_series"])
            if new_related_objects - old_related_objects and not self.edit_description_form.cleaned_data["important"]:
                self.edit_description_form.add_error("important", ValidationError(
                    _("Adding samples or sample series must be marked as important."), code="required"))
                referentially_valid = False
        quantities = set()
        for quantity_form in self.quantity_forms:
            if quantity_form.is_valid():
                quantity = quantity_form.cleaned_data["quantity"]
                if quantity in quantities:
                    quantity_form.add_error("quantity", ValidationError(_("This quantity is already used in this table."),
                                                                        code="invalid"))
                    referentially_valid = False
                else:
                    quantities.add(quantity)
        return referentially_valid

    def _is_structure_changed(self):
        """Check whether the structure was changed by the user, i.e. whether
        the table dimensions were changed.  (In this case, the view has to be
        re-displayed instead of being written to the database.)

        :return:
          whether the dimensions of the result values table were changed

        :rtype: bool
        """
        if self.dimensions_form.is_valid() and self.previous_dimensions_form.is_valid():
            return self.dimensions_form.cleaned_data["number_of_quantities"] != \
                self.previous_dimensions_form.cleaned_data["number_of_quantities"] or \
                self.dimensions_form.cleaned_data["number_of_values"] != \
                self.previous_dimensions_form.cleaned_data["number_of_values"]
        else:
            # In case of doubt, assume that the structure was changed.
            # Actually, this should never happen unless the browser is broken.
            return True

    def compose_quantities_and_values(self):
        """Composes the DB field ``quantities_and_values`` from the form data.  See the
        ``quantities_and_values`` attribute of `samples.models.Result` for
        further information.

        :return:
          the value for ``quantities_and_values``, ready to be saved to the
          database

        :rtype: tuple[list[str], list[list[str]]]
        """
        result = [form.cleaned_data["quantity"] for form in self.quantity_forms], \
            [[form.cleaned_data["value"] for form in form_list] for form_list in self.value_form_lists]
        return result

    def save_to_database(self, post_files):
        """Save the forms to the database.  One peculiarity here is that I
        still check validity on this routine, namely whether the uploaded image
        data is correct.  If it is not, the error is written to the
        ``result_form`` and the result of this routine is ``None``.  I also
        check all other types of validity, and whether the structure was
        changed (i.e., the dimensions of the result values table were changed).

        :param post_files: The file data submitted via HTTP.  It is the result
            of ``request.FILES``.

        :type post_files: django.utils.datastructures.MultiValueDict

        :return:
          the created or updated result instance, or ``None`` if the data
          couldn't yet be written to the database, but the view has to be
          re-displayed

        :rtype: `models.Result` or NoneType
        """
        all_valid = self._is_all_valid()
        referentially_valid = self._is_referentially_valid()
        structure_changed = self._is_structure_changed()
        if all_valid and referentially_valid and not structure_changed:
            # FixMe: Maybe upload file first, and make a successful upload the
            # forth precondition for this branch?
            if self.result:
                result = self.result_form.save()
            else:
                result = self.result_form.save(commit=False)
            result.quantities_and_values = self.compose_quantities_and_values()
            result.save()
            if not self.result:
                self.result_form.save_m2m()
            if self.related_data_form.cleaned_data["image_file"]:
                save_image_file(post_files["image_file"], result, self.related_data_form)
            if self.related_data_form.is_valid():
                result.samples.set(self.related_data_form.cleaned_data["samples"])
                result.sample_series.set(self.related_data_form.cleaned_data["sample_series"])
                return result

    def update_previous_dimensions_form(self):
        """Set the form with the previous dimensions to the currently set
        dimensions.
        """
        self.previous_dimensions_form = DimensionsForm(
            initial={"number_of_quantities": len(self.quantity_forms), "number_of_values": len(self.value_form_lists)},
                     prefix="previous")

    def get_context_dict(self):
        """Retrieve the context dictionary to be passed to the template.  This
        context dictionary contains all forms in an easy-to-use format for the
        template code.

        :return:
          context dictionary

        :rtype: dict mapping str to various types
        """
        return {"result": self.result_form, "related_data": self.related_data_form,
                "edit_description": self.edit_description_form, "dimensions": self.dimensions_form,
                "previous_dimensions": self.previous_dimensions_form, "quantities": self.quantity_forms,
                "value_lists": self.value_form_lists}


@help_link("demo.html#result-process")
@login_required
def edit(request, process_id):
    """View for editing existing results, and for creating new ones.

    :param request: the current HTTP Request object
    :param process_id: the ID of the result process; ``None`` if we're creating
        a new one

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    form_set = FormSet(request, process_id)
    if form_set.result:
        permissions.assert_can_edit_result_process(request.user, form_set.result)
    if request.method == "POST":
        form_set.from_post_data(request.POST, request.FILES)
        result = form_set.save_to_database(request.FILES)
        if result:
            utils.Reporter(request.user).report_result_process(
                result, form_set.edit_description_form.cleaned_data if form_set.edit_description_form else None)
            return utils.successful_response(request, json_response=result.pk)
    else:
        form_set.from_database()
    form_set.update_previous_dimensions_form()
    title = _("Edit result") if form_set.result else _("New result")
    context_dict = {"title": title}
    context_dict.update(form_set.get_context_dict())
    return render(request, "samples/edit_result.html", context_dict)


@login_required
def show(request, process_id):
    """Shows a particular result process.  The main purpose of this view is to
    be able to visit a result directly from a feed entry about a new/edited
    result.

    :param request: the current HTTP Request object
    :param process_id: the database ID of the result to show

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_result_process(request.user, result)
    if jb_common.utils.base.is_json_requested(request):
        return jb_common.utils.base.respond_in_json(result.get_data())
    template_context = {"title": _("Result “{title}”").format(title=result.title), "result": result,
                        "samples": result.samples.all(), "sample_series": result.sample_series.all()}
    template_context.update(utils.digest_process(result, request.user))
    return render(request, "samples/show_single_result.html", template_context)


@login_required
def show_image(request, process_id):
    """Shows a particular result image.  Although its response is an image
    rather than an HTML file, it is served by Django in order to enforce user
    permissions.

    :param request: the current HTTP Request object
    :param process_id: the database ID of the result to show

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object with the image

    :rtype: HttpResponse
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_result_process(request.user, result)
    image_locations = result.get_image_locations()
    return static_response(jb_common.utils.blobs.storage.open(image_locations["image_file"]),
                           image_locations["sluggified_filename"])


def generate_thumbnail(result, image_filename):
    image_file = jb_common.utils.blobs.storage.export(image_filename)
    content = subprocess.check_output(["convert", image_file + ("[0]" if result.image_type == "pdf" else ""),
                                       "-resize", "{0}x{0}".format(settings.THUMBNAIL_WIDTH), "png:-"])
    os.unlink(image_file)
    return BytesIO(content)


@login_required
def show_thumbnail(request, process_id):
    """Shows the thumnail of a particular result image.  Although its response
    is an image rather than an HTML file, it is served by Django in order to
    enforce user permissions.

    :param request: the current HTTP Request object
    :param process_id: the database ID of the result to show

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object with the thumbnail image

    :rtype: HttpResponse
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_result_process(request.user, result)
    image_locations = result.get_image_locations()
    image_filename = image_locations["image_file"]
    thumbnail_file = image_locations["thumbnail_file"]
    stream = get_cached_bytes_stream(thumbnail_file, partial(generate_thumbnail, result, image_filename),
                                     [image_filename])
    return static_response(stream, content_type="image/png")


@login_required
def export(request, process_id):
    """View for exporting result process data in CSV or JSON format.  Thus,
    the return value is not an HTML response.

    :param request: the current HTTP Request object
    :param process_id: the database ID of the result to show

    :type request: HttpRequest
    :type process_id: str

    :return:
      the HTTP response object

    :rtype: HttpResponse
    """
    result = get_object_or_404(models.Result, pk=utils.convert_id_to_int(process_id))
    permissions.assert_can_view_result_process(request.user, result)
    data = result.get_data_for_table_export()
    # Translators: In a table
    result = utils.table_export(request, data, _("row"))
    if isinstance(result, tuple):
        column_groups_form, columns_form, table, switch_row_forms, old_data_form = result
    elif isinstance(result, HttpResponse):
        return result
    title = _("Table export for “{name}”").format(name=data.descriptive_name)
    return render(request, "samples/table_export.html", {"title": title, "column_groups": column_groups_form,
                                                         "columns": columns_form,
                                                         "rows": list(zip(table, switch_row_forms)) if table else None,
                                                         "old_data": old_data_form,
                                                         "backlink": request.GET.get("next", "")})


_ = ugettext
