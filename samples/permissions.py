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


"""Central permission checking.  This module consists of three parts: First,
the exception that is raised if a certain permission condition is not met.
Secondly, the assertion functions that test for certain permissions.  And
thirdly, top-level code that generates a ``has_permission_to_...`` function for
every ``assert_can_...`` function.

The idea is the following.  For example, there is a function called
``assert_can_fully_view_sample``.  If the user can't view the sample, a
``PermissionError`` is raised.  Sometimes however, you just want to check it
without having to catch an exception.  Then, you use
``has_permission_to_fully_view_sample``.  The parameters are the same but
instead of raising an exception, it returns ``True`` or ``False``.

The ``assert_can_...`` function are typically used at the beginning of views
where permissions need to be checked and every failure means an error.  By
contrast, the ``has_permission_to_...`` functions are used where a missing
permission just means that e.g. a link is not generated (for example, in the
``get_context_for_user`` methods in the models).
"""

import hashlib, re
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType
import django.urls
from django.utils.translation import ugettext_lazy as _, ugettext
from django.contrib.auth.models import User, Permission
from django.conf import settings
import jb_common.utils.base as utils
import jb_common.models
import samples.models
from samples.utils.sample_name_formats import sample_name_format, get_renamable_name_formats


_permission_name_regex = re.compile("(?P<prefix>Can (?:add|edit every|view every|edit permissions for) )'(?P<class_name>.+)'",
                                    re.UNICODE)

def translate_permission(permission_codename):
    """Translates a permission description to the user's language.  Note that in
    order to uniquely identify a permission, the model is needed, too.  This is
    not the case here.  Instead, we assume that if the codename is the same,
    the translation will be so, too.

    :param permission_codename: the codename of the permission, *with* the
        ``"all_label."`` prefix; only the naked codename is used for lookup,
        though

    :type permission_codename: str

    :return:
      The name (aka short description) of the permission, translated to the
      current langauge.  It starts with a capital letter but doesn't end in a
      full stop.

    :rtype: str
    """
    permission_codename = permission_codename.partition(".")[2]
    try:
        name = Permission.objects.filter(codename=permission_codename)[0].name
    except IndexError:
        return _("[not available]")
    else:
        match = _permission_name_regex.match(name)
        if match:
            class_name_pattern = "{class_name}"
            return _(match.group("prefix") + class_name_pattern).format(class_name=_(match.group("class_name")))
        else:
            return _(name)


def get_user_permissions(user):
    """Determines the permissions of a user.  It iterates through all
    permissions and looks whether the user has them or not, and returns its
    findings.

    :param user: the user for which the permissions should be determined

    :type user: django.contrib.auth.models.User

    :return:
      A list with all permissions the user has got, a list with all permissions
      that the user doesn't have got.  Both lists contain translated
      descriptions.

    :rtype: list of str, list of str
    """
    has = []
    has_not = []
    for permission in Permission.objects.all():
        if not issubclass(permission.content_type.model_class(), samples.models.PhysicalProcess):
            full_permission_name = permission.content_type.app_label + "." + permission.codename
            if user.has_perm(full_permission_name):
                has.append(translate_permission(full_permission_name))
            else:
                has_not.append(translate_permission(full_permission_name))
    return has, has_not


def get_user_hash(user):
    """Generates a secret hash that is connected with a user.  It is meant as
    some sort of URL-based login for fetching feeds.  If the user accesses his
    feed via his aggregator, he is possibly not logged-in.  Because the
    aggregator cannot login by itself, the URL must be made unguessable.  This
    is done by appending the secret hash.

    Technically, it is the first 10 characters of a salted SHA-1 hash of the
    user's name.

    :param user: the current user

    :type user: django.contrib.auth.models.User

    :return:
      The user's secret hash

    :rtype: str
    """
    user_hash = hashlib.sha1()
    user_hash.update(settings.SECRET_KEY.encode())
    user_hash.update(user.username.encode())
    return user_hash.hexdigest()[:10]


def get_editable_sample_series(user):
    """Return a query set with all sample series that the user can edit.  So
    far, it is only used in `split_and_rename.GlobalDataForm`.

    :param user: the user which has too few permissions

    :type user: django.contrib.auth.models.User

    :return:
      a query set with all sample series that the user can edit

    :rtype: QuerySet
    """
    return samples.models.SampleSeries.objects.filter(currently_responsible_person=user)


all_addable_physical_process_models = None
def get_all_addable_physical_process_models():
    """Get all physical process classes (depositions, measurements; no sample
    splits) that one can add or edit.  Never call this routine from top-level
    module code because it may cause cyclic imports.

    :return:
      Dictionary mapping all physical processes one can to add.  Every process
      class is mapped to a dictionary with three keys, namely ``"url"`` with
      the url to the “add” view for the process, ``"label"`` with the name of
      the process (starting lowercase), and ``"type"`` with the process'
      class name.

    :rtype: dict mapping class to dict mapping str to str
    """
    global all_addable_physical_process_models
    if all_addable_physical_process_models is None:
        all_addable_physical_process_models = {}
        for process_class in utils.get_all_models().values():
            if issubclass(process_class, samples.models.PhysicalProcess):
                url = process_class.get_add_link()
                if url:
                    all_addable_physical_process_models[process_class] = {
                        "url": url, "label": process_class._meta.verbose_name,
                        "label_plural": process_class._meta.verbose_name_plural, "type": process_class.__name__}
    return all_addable_physical_process_models


def get_allowed_physical_processes(user):
    """Get a list with all physical process classes (depositions, measurements;
    no sample splits) that the user is allowed to add or edit.  This routine is
    typically used where a list of all processes that the user is allowed to
    *add* is to be build, on the main menu page and the “add process to sample”
    page.

    :param user: the user whose allowed physical processes should be collected

    :type user: django.contrib.auth.models.User

    :return:
      List of all physical processes the user is allowed to add to the
      database.  Every process is represented by a dictionary with three keys,
      namely ``"url"`` with the url to the “add” view for the process,
      ``"label"`` with the name of the process (starting lowercase), and
      ``"type"`` with the process' class name.

    :rtype: list of dict mapping str to str
    """
    allowed_physical_processes = []
    for physical_process_class, add_data in get_all_addable_physical_process_models().items():
        if has_permission_to_add_physical_process(user, physical_process_class):
            allowed_physical_processes.append(add_data.copy())
    allowed_physical_processes.sort(key=lambda process: process["label"].lower())
    return allowed_physical_processes


def get_lab_notebooks(user):
    """Get a list of all lab notebooks the user can see.

    :param user: the user whose allowed lab notebooks should be collected

    :type user: django.contrib.auth.models.User

    :return:
      List of all lab notebooks the user is allowed to see.  Every lab book is
      represented by a dictionary with two keys, namely ``"url"`` with the url
      to the lab book, and ``"label"`` with the name of the process (starting
      lowercase).

    :rtype: list of dict mapping str to str
    """
    lab_notebooks = []
    for process_class, process in get_all_addable_physical_process_models().items():
        try:
            url = django.urls.reverse(
                process_class._meta.app_label + ":lab_notebook_" + utils.camel_case_to_underscores(process["type"]),
                kwargs={"year_and_month": ""}, current_app=process_class._meta.app_label)
        except django.urls.NoReverseMatch:
            pass
        else:
            if has_permission_to_view_lab_notebook(user, process_class):
                lab_notebooks.append({"label": process["label_plural"], "url": url})
    lab_notebooks.sort(key=lambda process: process["label"].lower())
    return lab_notebooks


_topic_manager_permission = None
def get_topic_manager_permission():
    """Returns the permission object for topic managers.  This caches the database
    access which is needed to get this permissions object.

    :return:
      The permission to edit all topics which you are member of

    :rtype: django.contrib.auth.models.Permission
    """
    global _topic_manager_permission
    if not _topic_manager_permission:
        _topic_manager_permission = Permission.objects.get(
            codename="edit_their_topics", content_type=ContentType.objects.get_for_model(jb_common.models.Topic))
    return _topic_manager_permission


def can_edit_any_topics(user):
    """Returns whether the user can edit any topics.  It is used to decide whether
    or not a link to the “choose topic for edit” page should be shown.

    :param user: the user whose topic permissions should be checked

    :type user: django.contrib.auth.models.User

    :return:
      whether the user can edit at least one topic

    :rtype: bool
    """
    return any(has_permission_to_edit_topic(user, topic) for topic in jb_common.models.Topic.objects.all())


def can_edit_any_external_contacts(user):
    """Returns whether the user can edit any external operators.  It is used to
    decide whether or not a link to the “choose external operator for edit”
    page should be shown.

    :param user: the user whose external operator permissions should be checked

    :type user: django.contrib.auth.models.User

    :return:
      whether the user can edit at least one external operator

    :rtype: bool
    """
    return user.external_contacts.exists() or (samples.models.ExternalOperator.objects.exists() and user.is_superuser)


def get_all_adders(process_class):
    """Returns all operators for a given process class.  “Operators” means
    people who are allowed to add new processes of this class.  Note that if
    there is not “add_...” permission for the process class, i.e. everyone can
    add such processes, this routine returns none.  This may sound strange but
    it is very helpful in most cases.

    :param process_class: the process class for which the operators should be
        found

    :type process_class: ``type`` (class ``samples.models.Process``)

    :return:
      all active users that are allowed to add processes for this class; if the
      process class is not resticted to certain users, this function returns an
      empty query set

    :rtype: QuerySet
    """
    permission_codename = "add_{0}".format(process_class.__name__.lower())
    try:
        add_permission = Permission.objects.get(codename=permission_codename,
                                                content_type=ContentType.objects.get_for_model(process_class))
    except Permission.DoesNotExist:
        return User.objects.none()
    else:
        return User.objects.filter(is_active=True, is_superuser=False). \
            filter(Q(groups__permissions=add_permission) | Q(user_permissions=add_permission)).distinct()


class PermissionError(Exception):
    """Common class for all permission exceptions.  We have our own exception class
    and don't use Django's `PermissionDenied` because we need additional
    context variables.

    :ivar description: The full description of the problem, possible remedy
      inclusive.  It should be a complete sentence, which addresses the user
      directly.  It should start with a capital letter and end with a full
      stop.  For example, it may be “You are not allowed to view sample 01B-410
      because you're not … Note that a head of an institute groups may add you
      to new topics.”.

    :type description: str
    """

    def __init__(self, user, description, new_topic_would_help=False):
        """Class constructor.

        :param user: the user which has too few permissions
        :param description: a sentence describing the denied action and what
            could be done about it
        :param new_topic_would_help: if ``True``, adding the user to a certain
            topic would grant him the permission for the action

        :type user: django.contrib.auth.models.User
        :type description: str
        :type new_topic_would_help: bool
        """
        super().__init__(_("Permission denied: ") + description)
        self.user, self.description, self.new_topic_would_help = user, description, new_topic_would_help


class NoDepartment:
    """Singleton class used to define an unset department attribute, so that an
    unset department is never equal to another unset department.
    """
    _instance = None
    def __new__(cls, *args, **kwargs):
        if cls._instance is not None:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance
    def __eq__(self, other):
        return False
    def __ne__(self, other):
        return True
    def __bool__(self):
        return False


def assert_can_fully_view_sample(user, sample):
    """Tests whether the user can view the sample fully, i.e. without needing
    a clearance.

    :param user: the user whose permission should be checked
    :param sample: the sample to be shown

    :type user: django.contrib.auth.models.User
    :type sample: `samples.models.Sample`

    :raises PermissionError: if the user is not allowed to fully view the
        sample.
    """
    currently_responsible_person = sample.currently_responsible_person
    sample_department = currently_responsible_person.jb_user_details.department or NoDepartment()
    user_department = user.jb_user_details.department or NoDepartment()
    if not sample.topic and sample_department != user_department and not user.is_superuser:
        description = _("You are not allowed to view the sample since the sample doesn't belong to your department.")
        raise PermissionError(user, description, new_topic_would_help=True)
    if sample.topic and user not in sample.topic.members.all() and currently_responsible_person != user and \
            not user.is_superuser:
        if sample_department != user_department:
            description = _("You are not allowed to view the sample since you are not in the sample's topic, nor belongs the "
                            "sample to your department.")
            raise PermissionError(user, description, new_topic_would_help=True)
        elif sample.topic.confidential:
            description = _("You are not allowed to view the sample since you are not in the sample's topic, nor are you "
                            "its currently responsible person ({name})."). \
                            format(name=utils.get_really_full_name(currently_responsible_person))
            raise PermissionError(user, description, new_topic_would_help=True)
        elif not user.has_perm("samples.view_every_sample"):
            description = _("You are not allowed to view the sample since you are not in the sample's topic, nor are you "
                            "its currently responsible person ({name}), nor can you view all samples."). \
                            format(name=utils.get_really_full_name(currently_responsible_person))
            raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_rename_sample(user, sample):
    """Tests whether the user can rename the given sample.

    :param user: the user whose permission should be checked
    :param sample: the sample to be renamed

    :type user: django.contrib.auth.models.User
    :type sample: `samples.models.Sample`

    :raises PermissionError: if the user is not allowed to rename the
        sample.
    """
    currently_responsible_person = sample.currently_responsible_person
    sample_department = currently_responsible_person.jb_user_details.department or NoDepartment()
    user_department = user.jb_user_details.department or NoDepartment()
    if (not user.has_perm("samples.rename_samples" or sample_department != user_department)
        and not sample_name_format(sample.name) in get_renamable_name_formats()) \
        and not user.is_superuser:
        description = _("You are not allowed to rename the sample.")
        raise PermissionError(user, description)


def assert_can_delete_sample(user, sample):
    """Tests whether the user can delete a sample.  A sample can be deleted if:

    - You can edit this sample.
    - You can edit all processes of this sample.
    - You can delete all processes of this sample which only have this sample.

    “Processes of this sample” does not include processes of parents.  It does,
    however, include all sample splits, and thus the samples generated by them.

    :param user: the user whose permission should be checked
    :param sample: the sample to be deleted

    :type user: django.contrib.auth.models.User
    :type sample: `samples.models.Sample`

    :return:
      the objects that are deleted

    :rtype: set of ``Model``

    :raises PermissionError: if the user is not allowed to delete the sample
    """
    return sample.delete(dry_run=True, user=user)


def get_sample_clearance(user, sample):
    """Returns the clearance a user needs to visit a sample, if he needs one
    at all.

    :param user: the user whose permission should be checked
    :param sample: the sample to be shown

    :type user: django.contrib.auth.models.User
    :type sample: `samples.models.Sample`

    :return:
      the clearance for the user and sample, or ``None`` if the user doesn't
      need a clearance to visit the sample

    :rtype: `samples.models.Clearance` or NoneType

    :raises PermissionError: if the user is not allowed to view the
        sample.
    """
    from samples.utils.views import enforce_clearance
    clearance = None
    try:
        assert_can_fully_view_sample(user, sample)
    except PermissionError as error:
        try:
            tasks = samples.models.Task.objects.filter(samples=sample)
        except samples.models.Task.DoesNotExist:
            pass
        else:
            for task in tasks:
                process_class = task.process_class.model_class()
                if has_permission_to_add_physical_process(user, process_class):
                    enforce_clearance(task.customer, samples.models.clearance_sets.get(process_class, ()), user, sample)
        try:
            clearance = samples.models.Clearance.objects.get(user=user, sample=sample)
        except samples.models.Clearance.DoesNotExist:
            raise error
    return clearance


def assert_can_add_physical_process(user, process_class):
    """Tests whether the user can create a new physical process
    (i.e. deposition, measurement, etching process, clean room work etc).

    :param user: the user whose permission should be checked
    :param process_class: the type of physical process that the user asks
        permission for

    :type user: django.contrib.auth.models.User
    :type process_class: ``class`` (derived from `samples.models.Process`)

    :raises PermissionError: if the user is not allowed to add a process.
    """
    codename = "add_{0}".format(process_class.__name__.lower())
    if Permission.objects.filter(codename=codename, content_type=ContentType.objects.get_for_model(process_class)).exists():
        permission = "{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename)
        if not user.has_perm(permission):
            description = _("You are not allowed to add {process_plural_name} because you don't have the "
                            "permission “{permission}”.").format(
                process_plural_name=process_class._meta.verbose_name_plural, permission=translate_permission(permission))
            raise PermissionError(user, description)


def assert_can_edit_physical_process(user, process):
    """Tests whether the user can edit a physical process (i.e. deposition,
    measurement, etching process, clean room work etc).  For this, he must be
    the operator of this process, *and* he must be allowed to add new processes
    of this kind.  Alternatively, he must have the “edit all” permission for
    the process class.

    :param user: the user whose permission should be checked
    :param process: The process to edit.  This neend't be the actual instance.

    :type user: django.contrib.auth.models.User
    :type process: `samples.models.Process`

    :raises PermissionError: if the user is not allowed to edit the
        process.
    """
    process_class = process.content_type.model_class()
    codename = "change_{0}".format(process_class.__name__.lower())
    has_edit_all_permission = \
        user.has_perm("{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename))
    codename = "add_{0}".format(process_class.__name__.lower())
    if Permission.objects.filter(codename=codename, content_type=ContentType.objects.get_for_model(process_class)).exists():
        has_add_permission = \
            user.has_perm("{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename))
    else:
        has_add_permission = True
    if (not has_add_permission or process.operator != user) and not (has_add_permission and not process.finished) and \
            not has_edit_all_permission and not user.is_superuser:
        description = _("You are not allowed to edit the process “{process}” because you are not the operator "
                        "of this process.").format(process=process)
        raise PermissionError(user, description)


def assert_can_delete_physical_process(user, process):
    """Tests whether the user can delete a physical process (i.e. deposition,
    measurement, etching process, clean room work etc).  For this, the
    following conditions must be met:

    - ``process.is_deletable(user)`` must yield ``True``.
    - You can edit the process.
    - The process is not older than one hour.

    :param user: the user whose permission should be checked
    :param process: The process to delete.  This must be the actual instance.

    :type user: django.contrib.auth.models.User
    :type process: `samples.models.Process`

    :return:
      the objects that are deleted

    :rtype: set of ``Model``

    :raises PermissionError: if the user is not allowed to delete the process.
    """
    return process.delete(dry_run=True, user=user)


def assert_can_add_edit_physical_process(user, process, process_class=None):
    """Tests whether the user can create or edit a physical process
    (i.e. deposition, measurement, etching process, clean room work etc).  This
    is a convenience function which combines `assert_can_add_physical_process`
    and `assert_can_edit_physical_process`.  It is used in the combined
    add/edit views of physical processes.

    :param user: the user whose permission should be checked
    :param process: The concrete process to edit.  If ``None``, a new process is
        about to be created.
    :param process_class: the type of physical process that the user asks
        permission for

    :type user: django.contrib.auth.models.User
    :type process: `samples.models.Process`
    :type process_class: ``class`` (derived from `samples.models.Process`) or
      NoneType

    :raises PermissionError: if the user is not allowed to create or edit
        the process.
    """
    if process:
        assert process_class == process.actual_instance.__class__
        assert_can_edit_physical_process(user, process)
    else:
        assert_can_add_physical_process(user, process_class)


def assert_can_view_lab_notebook(user, process_class):
    """Tests whether the user can view the lab notebook for a physical process
    class (i.e. deposition, measurement, etching process, clean room work etc).

    :param user: the user whose permission should be checked
    :param process_class: the type of physical process that the user asks
        permission for

    :type user: django.contrib.auth.models.User
    :type process_class: ``class`` (derived from `samples.models.Process`)

    :raises PermissionError: if the user is not allowed to view the lab
        notebook for this process class.
    """
    codename = "view_every_{0}".format(process_class.__name__.lower())
    permission_name_to_view_all = "{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename)
    if Permission.objects.filter(codename=codename, content_type=ContentType.objects.get_for_model(process_class)).exists():
        has_view_all_permission = user.has_perm(permission_name_to_view_all)
    else:
        has_view_all_permission = user.is_superuser
    if not has_view_all_permission:
        description = _("You are not allowed to view lab notebooks for {process_plural_name} because you don't have the "
                        "permission “{permission}”.").format(
            process_plural_name=process_class._meta.verbose_name_plural,
            permission=translate_permission(permission_name_to_view_all))
        raise PermissionError(user, description)


def assert_can_view_physical_process(user, process):
    """Tests whether the user can view a physical process (i.e. deposition,
    measurement, etching process, clean room work etc).  You can view a process
    if you can view all such processes, if you are the operator of this
    process, if you have a clearance for this process, or if you can see at
    least one of the processed samples.

    :param user: the user whose permission should be checked
    :param process: The concrete process to view.  It it not necessary that it
        is the actual instance, i.e. it may also be a
        :py:class:`~samples.models.Process` instance.

    :type user: django.contrib.auth.models.User
    :type process: `samples.models.Process`

    :raises PermissionError: if the user is not allowed to view the
        process.
    """
    process_class = process.content_type.model_class()
    codename = "view_every_{0}".format(process_class.__name__.lower())
    permission_name_to_view_all = "{app_label}.{codename}".format(app_label=process_class._meta.app_label, codename=codename)
    if Permission.objects.filter(codename=codename, content_type=ContentType.objects.get_for_model(process_class)).exists():
        has_view_all_permission = user.has_perm(permission_name_to_view_all)
    else:
        has_view_all_permission = user.is_superuser
    if not has_view_all_permission and process.operator != user and \
            not any(has_permission_to_fully_view_sample(user, sample) for sample in process.samples.all()) and \
            not samples.models.Clearance.objects.filter(user=user, processes=process).exists():
        description = _("You are not allowed to view the process “{process}” because neither you have the "
                        "permission “{permission}”, nor you are allowed to view one of the processed samples, "
                        "nor are you the operator, nor is there a clearance for you for this process.").format(
            process=process, permission=translate_permission(permission_name_to_view_all))
        raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_edit_result_process(user, result_process):
    """Tests whether the user can edit a result process.

    :param user: the user whose permission should be checked
    :param result_process: The result process to edit.

    :type user: django.contrib.auth.models.User
    :type result_process: `samples.models.Result`

    :raises PermissionError: if the user is not allowed to edit the result
        process.
    """
    if result_process.operator != user and not user.is_superuser:
        description = _("You are not allowed to edit the result “{result}” because you didn't create this result.").format(
            result=result_process)
        raise PermissionError(user, description)


def assert_can_view_result_process(user, result_process):
    """Tests whether the user can view a result process.

    :param user: the user whose permission should be checked
    :param result_process: The result process to edit.

    :type user: django.contrib.auth.models.User
    :type result_process: `samples.models.Result`

    :raises PermissionError: if the user is not allowed to view the result
        process.
    """
    if result_process.operator != user and \
            all(not has_permission_to_fully_view_sample(user, sample) for sample in result_process.samples.all()) and \
            all(not has_permission_to_view_sample_series(user, sample_series)
                for sample_series in result_process.sample_series.all()) and \
                not samples.models.Clearance.objects.filter(user=user, processes=result_process).exists():
        description = _("You are not allowed to view the result “{result}” because neither did you create this result, "
                        "nor are you allowed to view its connected samples or sample series, nor is there a "
                        "clearance for you for this result.").format(result=result_process)
        raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_add_result_process(user, sample_or_series):
    """Tests whether the user can add a result process.

    :param user: the user whose permission should be checked
    :param sample_or_series: the sample (series) the user wants to add a result
        to

    :type user: django.contrib.auth.models.User
    :type sample_or_series: `samples.models.Sample` or
        `samples.models.SampleSeries`

    :raises PermissionError: if the user is not allowed to add the result
        process to the sample or series
    """
    if sample_or_series.currently_responsible_person != user and sample_or_series.topic and \
             user not in sample_or_series.topic.members.all() and not user.is_superuser:
        if isinstance(sample_or_series, samples.models.Sample):
            description = _("You are not allowed to add the result to {sample_or_series} because neither are you the "
                            "currently responsible person for this sample, nor are you a member of its topic.").format(
                sample_or_series=sample_or_series)
        else:
            description = _("You are not allowed to add the result to {sample_or_series} because neither are you the "
                            "currently responsible person for this sample series, nor are you a member of its "
                            "topic.").format(sample_or_series=sample_or_series)
        raise PermissionError(user, description)


def assert_can_edit_sample(user, sample):
    """Tests whether the user can edit, split, and kill a sample.

    :param user: the user whose permission should be checked
    :param sample: the sample to be changed

    :type user: django.contrib.auth.models.User
    :type sample: `samples.models.Sample`

    :raises PermissionError: if the user is not allowed to edit the sample
    """
    currently_responsible_person = sample.currently_responsible_person
    sample_department = currently_responsible_person.jb_user_details.department or NoDepartment()
    user_department = user.jb_user_details.department or NoDepartment()
    if not sample.topic and sample_department != user_department and not user.is_superuser:
        description = _("You are not allowed to edit the sample since the sample doesn't belong to your department.")
        raise PermissionError(user, description, new_topic_would_help=True)
    topic_manager_permission = get_topic_manager_permission()
    if sample.topic and currently_responsible_person != user and not user.is_superuser and not \
        (user in sample.topic.members.all() and topic_manager_permission in user.user_permissions.all()):
        description = _("You are not allowed to edit the sample “{name}” (including splitting, declaring dead, and deleting) "
                        "because you are not the currently responsible person for this sample.").format(name=sample)
        raise PermissionError(user, description)


def assert_can_edit_sample_series(user, sample_series):
    """Tests whether the user can edit a sample series, including adding or
    removing samples.

    :param user: the user whose permission should be checked
    :param sample_series: the sample series to be changed

    :type user: django.contrib.auth.models.User
    :type sample_series: `samples.models.SampleSeries`

    :raises PermissionError: if the user is not allowed to edit the sample
        series
    """
    if sample_series.currently_responsible_person != user and not user.is_superuser:
        description = _("You are not allowed to edit the sample series “{name}” because "
                        "you are not the currently responsible person for this sample series.").format(name=sample_series)
        raise PermissionError(user, description)


def assert_can_view_sample_series(user, sample_series):
    """Tests whether the user can view a sample series.

    :param user: the user whose permission should be checked
    :param sample_series: the sample series to be shown

    :type user: django.contrib.auth.models.User
    :type sample_series: `samples.models.SampleSeries`

    :raises PermissionError: if the user is not allowed to view the sample
        series
    """
    if sample_series.currently_responsible_person != user and  user not in sample_series.topic.members.all()and \
            not user.is_superuser:
        description = _("You are not allowed to view the sample series “{name}” because neither are "
                        "you the currently responsible person for it, nor are you in its topic.").format(name=sample_series)
        raise PermissionError(user, description, new_topic_would_help=True)


def assert_can_add_external_operator(user):
    """Tests whether the user can add an external operator.

    :param user: the user whose permission should be checked

    :type user: django.contrib.auth.models.User

    :raises PermissionError: if the user is not allowed to add an external
        operator.
    """
    permission = "samples.add_externaloperator"
    if not user.has_perm(permission):
        description = _("You are not allowed to add an external operator because you don't have the permission “{name}”.") \
            .format(name=translate_permission(permission))
        raise PermissionError(user, description)


def assert_can_edit_external_operator(user, external_operator):
    """Tests whether the user can edit an external operator.

    :param user: the user whose permission should be checked
    :param external_operator: the external operator to be edited

    :type user: django.contrib.auth.models.User
    :type external_operator: `samples.models.ExternalOperator`

    :raises PermissionError: if the user is not allowed to edit an
        external operator.
    """
    if user not in external_operator.contact_persons.all() and not user.is_superuser:
        description = _("You are not allowed to edit this external operator because you aren't their "
                        "current contact person.")
        raise PermissionError(user, description)


def assert_can_view_external_operator(user, external_operator):
    """Tests whether the user can view an external operator.

    :param user: the user whose permission should be checked
    :param external_operator: the external operator to be shown

    :type user: django.contrib.auth.models.User
    :type external_operator: `samples.models.ExternalOperator`

    :raises PermissionError: if the user is not allowed to view an
        external operator.
    """
    if user not in external_operator.contact_persons.all() and not user.is_superuser:
        if external_operator.confidential:
            description = _("You are not allowed to view this external operator because you are not their "
                            "current contact person.")
            raise PermissionError(user, description)
        elif not user.has_perm("samples.view_every_externaloperator"):
            description = _("You are not allowed to view this external operator because neither are you their "
                            "current contact person, nor can you view all external operators.")
            raise PermissionError(user, description)


def assert_can_edit_topic(user, topic=None):
    """Tests whether the user can change topic memberships of other users,
    set the topic's restriction status, and add new topics.  This typically
    is a priviledge of heads of institute groups.

    :param user: the user whose permission should be checked
    :param topic: the topic whose members are about to be edited; ``None``
        if we create a new one

    :type user: django.contrib.auth.models.User
    :type topic: `jb_common.models.Topic` or NoneType

    :raises PermissionError: if the user is not allowed to edit topics,
        or to add new topics.
    """
    if not topic:
        if not user.has_perm("jb_common.add_topic"):
            description = _("You are not allowed to add topics because you don't have the permission “{name}”.") \
                .format(name=translate_permission("jb_common.add_topic"))
            raise PermissionError(user, description)
    else:
        if user in topic.members.all():
            if not user.has_perm("jb_common.change_topic") and \
                    topic.manager != user:
                description = _("You are not allowed to change this topic because you don't have the permission "
                                "“{0}” or “{1}”.").format(translate_permission("jb_common.change_topic"),
                                                           translate_permission("jb_common.edit_their_topics"))
                raise PermissionError(user, description)
        else:
            if not user.has_perm("jb_common.change_topic"):
                description = _("You are not allowed to change this topic because "
                                "you don't have the permission “{name}”.").format(
                    name=translate_permission("jb_common.change_topic"))
                raise PermissionError(user, description)
            elif topic.confidential and not user.is_superuser:
                description = _("You are not allowed to change this topic because it is confidential "
                                "and you are not in this topic.")
                raise PermissionError(user, description)


def assert_can_edit_users_topics(user):
    """Tests whether the user can change topic memberships of other users,
    set the topic's restriction status, and add new sub topics where the
    user is member off. This is a priviledge of topic managers.

    :param user: the user whose permission should be checked

    :type user: django.contrib.auth.models.User

    :raises PermissionError: if the user is not allowed to edit his/ her
        topics, or to add new sub topics.
    """
    if not (user.has_perm("jb_common.add_topic") or user.has_perm("jb_common.edit_their_topics")) and \
        not user.has_perm("jb_common.change_topic"):
        description = _("You are not allowed to change your topics because you don't have the permission "
                        "“{0}” or “{1}”.").format(translate_permission("jb_common.change_topic"),
                                                  translate_permission("jb_common.edit_their_topics"))
        raise PermissionError(user, description)


def assert_can_view_feed(hash_value, user):
    """Tests whether the requester that gave a certain ``hash_value`` can view
    the news feed of a certain ``user``.  Basically, this tests whether the
    requester *is* the user because only he can know the hash value.

    Note that additionally, I have to test here whether the feed's user is
    still active because you needn't be logged-in to access a feed, and I don't
    use any ``has_perm`` method call here (which would yield ``False`` for
    inactive users).

    :param hash_value: the hash value given by the requester
    :param user: the user whose news feed is requested

    :type hash_value: str
    :type user: django.contrib.auth.models.User

    :raises PermissionError: if the requester is not allowed to view the
        user's news feed.  It's ``user`` parameter is always ``None`` because
        we don't know the user who is currently accessing JuliaBase.
    """
    if not user.is_superuser:
        if hash_value != get_user_hash(user):
            description = _("You gave an invalid hash parameter in the query string.  "
                            "Note that you can't access the news feed of another user.")
            raise PermissionError(None, description)
        if not user.is_active:
            description = _("You can't access the feed of an inactive user.")
            raise PermissionError(None, description)


# Now, I inject the ``has_permission_to_...`` functions into this module for
# for every ``assert_can_...`` function found here.

def generate_permission_function(assert_func):
    def has_permission(*args, **kwargs):
        try:
            assert_func(*args, **kwargs)
        except PermissionError:
            return False
        else:
            return True
    return has_permission


import copy, inspect
_globals = copy.copy(globals())
all_assertion_functions = [func for func in _globals.values()
                           if inspect.isfunction(func) and func.__name__.startswith("assert_can_")]
for func in all_assertion_functions:
    new_name = "has_permission_to_" + func.__name__[len("assert_can_"):]
    globals()[new_name] = generate_permission_function(func)


_ = ugettext
