.. -*- mode: rst; coding: utf-8; ispell-local-dictionary: "british" -*-

Chantal programming guide
=================================

.. toctree::
   :maxdepth: 2


General considerations
===========================

Chantal source code modules should not exceed 1000 lines of code.  You should
stick to `PEP 8`_ and the `Django coding guidelines`_.

Chantal makes one exception from PEP 8: I allow lines with 125 columns instead
of only 80.

All variables and source code comments should be in English.

.. _`PEP 8`: http://www.python.org/dev/peps/pep-0008/
.. _`Django coding guidelines`: http://docs.djangoproject.com/en/dev/internals/contributing/?from=olddocs#coding-style

.. note::

   I skip all docstrings in the code examples in this document because
   otherwise, the examples would be too bloated.  However, write rich
   Docstrings for all non-trivial functions and methods.  Write them in `ReST
   format`_.  Sometimes, you can copy-and-paste the docstring with slight
   modifications.

.. _`ReST format`: http://epydoc.sourceforge.net/manual-othermarkup.html

Internationalisation is a very important point in Chantal.  All strings exposed
to the user should be marked as translatable by putting them in ``_(u"...")``
unless you have very good reason not to do so (e.g. for some proper names).
Note that in code which is executed at module load time (e.g. model and form
fields), ``_`` should stand for ``ugettext_lazy``, whereas within functions and
methods which are executed on each request, it should be ``ugettext``.


Writing a deposition module
=================================

I will show how to write a module for a deposition system by creating an
example module step-by-step.  In this case, I show how I write the module for
the small (old) cluster tool in the IEF-5.


Overview
------------

The following steps are necessary for creating a deposition module:

1. Create models in ``samples/models_depositions.py``.

2. Create links in ``urls.py``.

3. Create a view module in ``samples/views/``.  This is called *the* deposition
   module.

4. Fill the view module with an “edit” and a “show” function.

5. Create an “edit” and a “show” template in ``templates/``.

6. Create support for the new deposition system in the Remote Client.

7. Import legacy data.


Creating the database models
-----------------------------------

A “database model” or simply a “model” is a class in the Python code which
represents a table in the database.  A deposition system typically needs two
models: One for the deposition data and one for the layer data.  The layer data
will carry much more fields than the deposition, and it will contain a pointer
to the deposition it belongs to.  This way, deposition and layers are kept
together.  This pointer is represented by a “foreign key” field.

In case of the cluster tool, things are slightly more complicated because the
layers are not of one kind.  Instead, we can have a PECVD layer or a hotwire
layer.  Both have very different data.  Normally though, all layers share the
very same attributes.  This is much simpler.

Anyway.  In order to cope with the multiple layer types, I have to introduce a
common base class for the two layer types.  This is not an abstract class in
Django terminology but a concrete one because I need a single reverse foreign
key from the deposition instance to the set of layers, and therefore, an
intermediate database table is needed.

Thus, we have the following model structure::

    Deposition  ---->  SmallClusterToolDeposition

    Layer  -->  SmallClusterToolLayer  --+-->  SmallClusterToolHotwireLayer
                                         |
                                         `-->  SmallClusterToolPECVDLayer

The deposition model
.........................

Basically, one can copy-and-paste the deposition model class for another
deposition and thoroughly apply the necessary modifications to it.

Its ``Meta`` class should be::

    class Meta:
        verbose_name = _(u"small cluster tool deposition")
        verbose_name_plural = _(u"small cluster tool depositions")
        _ = lambda x: x
        permissions = (("add_edit_small_cluster_tool_deposition",
                       _("Can create and edit small cluster tool depositions")),)

It is very important that it defines those permissions because it is derived
from ``Process`` (albeit indirectly).  Note that the first string must match
the pattern ``add_edit_process_name_with_underscores``.

Then, we need two methods to get URLs for a depositions::

    @models.permalink
    def get_absolute_url(self):
        return ("samples.views.small_cluster_tool_deposition.show",
                [urlquote(self.number, safe="")])

    @classmethod
    def get_add_link(cls):
        _ = ugettext
        return django.core.urlresolvers.reverse("add_small_cluster_tool_deposition")

The view function ``"samples.views.small_cluster_tool_deposition.show"`` as
well as the symbolic name for a view function
``"add_small_cluster_tool_deposition"`` must exist in ``urls.py``, see below.

In order to enable users to duplicate and edit existing depositions, you should
also add the following method::

    def get_additional_template_context(self, process_context):
        layers = []
        for layer in self.layers.all():
            try:
                layer = layer.smallclustertoolhotwirelayer
                layer.type = "hotwire"
            except SmallClusterToolHotwireLayer.DoesNotExist:
                layer = layer.smallclustertoolpecvdlayer
                layer.type = "PECVD"
            layers.append(layer)
        result = {"layers": layers}
        if permissions.has_permission_to_add_edit_physical_process(
                process_context.user, self):
            result.update({"edit_url": django.core.urlresolvers.reverse(
                                   "edit_small_cluster_tool_deposition",
                                   kwargs={"deposition_number": self.number}),
                           "duplicate_url": "%s?copy_from=%s" % (
                        django.core.urlresolvers.reverse("add_small_cluster_tool_deposition"),
                        urlquote_plus(self.number))})
        return result

This is a somewhat peculiar method.  It is used when the HTML for a process (in
this case a deposition) is created.  Its return value is a dictionary which is
combined with the dictionary sent to the “show-process” template.  This way,
additional program logic can be used to generate the HTML.  In case of
depositions, an “edit” and “duplicate” button are added, depending on the
user's permissions.

However, in the special case of a cluster tool deposition, I also place the
layers into this template context.  The reason is that this way, I can inject a
``type`` attribute into the layers which is useful when rendering it by the
template code.

Finally, with

::

    default_location_of_deposited_samples[SmallClusterToolDeposition] = \
            _(u"large-area deposition lab")
    admin.site.register(SmallClusterToolDeposition)

I declare that the default sample location for samples deposited in the small
cluster tool is the “large-area deposition lab”, and I register the model with
Django's admin interface so that it can be seen and modified there.


The layer base model
....................

This section describes something which is special to the cluster tools.  The
problem is that cluster tools have heterogeneous layers, e.g. hotwire and PECVD
layers in one deposition run.  Therefore, we need a common base class for
layers in order to have one single connection point between depositions and
their layers.

It looks like this::

    class SmallClusterToolLayer(Layer):
	deposition = models.ForeignKey(SmallClusterToolDeposition, related_name="layers",
                                       verbose_name=_(u"deposition"))

	class Meta(Layer.Meta):
	    unique_together = ("deposition", "number")
	    verbose_name = _(u"small cluster tool layer")
	    verbose_name_plural = _(u"small cluster tool layers")

By the way, this ``unique_together`` is necessary for all concrete models
directly derived from ``Layer``, as is the ``deposition field``.  The reason is
that ``Layer`` itself is an abstract class and can't contain these things.


The hotwire layer model
.......................

I'll now show the addition of the Layer model.  Since we have two, I only show
the *hotwire* layer.  The PECVD is not much different.

First, for some models, you need so-called “choices” tuples.  For hotwire
layers, this is only one, namely for the wire material::

    small_cluster_tool_wire_material_choices = (
	("Rhenium", _("Rhenium")),
	("Tantal", _("Tantalum")),
	("Tungsten", _("Tungsten")),
    )

Put these “choices” tuples right before the respective model class.  See the
Django documentation for more about this.  However, I'd like to point out that
very often you have to make the second item translatable by putting it in
``_(...)``.

Now for the fields::

    class SmallClusterToolHotwireLayer(SmallClusterToolLayer):
	pressure = models.CharField(_(u"deposition pressure"), max_length=15,
                                    help_text=_(u"with unit"), blank=True)
	time = models.CharField(_(u"deposition time"), max_length=9,
                                help_text=_(u"format HH:MM:SS"), blank=True)
	substrate_electrode_distance = \
	    models.DecimalField(_(u"substrate–electrode distance"),
                                null=True, blank=True, max_digits=4,
				decimal_places=1, help_text=_(u"in mm"))
	comments = models.TextField(_(u"comments"), blank=True)
        ...

As you can see, every field starts with its name, marked as translatable.
Optional text fields just have a ``blank=True`` in their parameter list.

The rest is standard.

::

	class Meta(SmallClusterToolLayer.Meta):
	    verbose_name = _(u"small cluster tool hotwire layer")
	    verbose_name_plural = _(u"small cluster tool hotwire layers")

    admin.site.register(SmallClusterToolHotwireLayer)

Adds the singular/plural name of this model to the model (also for
internationalisation), and register the model on the admin pages.

And that's it.  The models are done now.


Creating the URLs
---------------------

The next work is done in ``urls.py``.  This step is fairly simple.  You just
have to copy-n-paste the URLs from an apparatus which is sufficiently closely
retated to yours and substitute the names.  For the small cluster tool, we
get::

    url(r"^small_cluster_tool_depositions/add/$",
        "samples.views.small_cluster_tool_deposition.edit",
	{"deposition_number": None}, "add_small_cluster_tool_deposition"),
    url(r"^small_cluster_tool_depositions/(?P<deposition_number>.+)/edit/$",
	"samples.views.small_cluster_tool_deposition.edit", 
        name="edit_small_cluster_tool_deposition"),
    (r"^small_cluster_tool_depositions/(?P<deposition_number>.+)",
     "samples.views.small_cluster_tool_deposition.show"),

I took this from the 6-chamber deposition and wrote the new names into it.  If
you also want to proved a lay notebook, you have to append::

    url(r"^small_cluster_tool_depositions/lab_notebook/(?P<year_and_month>.*)/export/",
	"samples.views.lab_notebook.export", {"process_name": "SmallClusterToolDeposition"},
	"export_lab_notebook_SmallClusterToolDeposition"),
    url(r"^small_cluster_tool_depositions/lab_notebook/(?P<year_and_month>.*)",
	"samples.views.lab_notebook.show", {"process_name": "SmallClusterToolDeposition"},
	"lab_notebook_SmallClusterToolDeposition"),


Creating the views
---------------------

Take another view module as a guide for the new one.  In the case of the small
cluster tool deposition system, I take the 6-chamber deposition as a guide.

Try to keep the imports at the top of the file minimal.  It's best to start
with an empty imports list and add them as needed.


The forms
........

In contrast to non-cluster-tool modules, I need to add a custom
``AddMyLayerForm`` class because adding a new layer is different from other
deposition systems since you have to give the *type* of the new layer.  Thus::

    new_layer_choices = (
	("hotwire", _(u"hotwire")),
	("PECVD", _(u"PECVD")),
	("none", _(u"none")),
	)

    class AddLayersForm(forms.Form):
	_ = ugettext_lazy
	layer_to_be_added = forms.ChoiceField(
                label=_(u"Layer to be added"), required=False, widget=forms.RadioSelect,
		choices=new_layer_choices)
	my_layer_to_be_added = forms.ChoiceField(
                label=_(u"Nickname of My Layer to be added"), required=False)

        ...

This is not more than a modified version of the class of the same name from
``form_utils.py``.

The deposition form can largely be copied from the 6-chamber deposition.  In
principle, this is also true for the two layer models, however, the attributes
and validation conditions must be carefully adapted of course.  Moreover, I add
an extra, hidden ``TextInput`` field called ``layer_type`` which saves the
layer type when creating the HTML form, so that it can be re-constructed when
scanning POST data::

    class HotwireLayerForm(forms.ModelForm):
	layer_type = forms.CharField(widget=forms.HiddenInput, initial=u"hotwire")
	...

Then, I need a ``ChangeLayerForm`` which contains the controls for duplicating
or removing a layer::

    class ChangeLayerForm(forms.Form):
	_ = ugettext_lazy
	duplicate_this_layer = forms.BooleanField(label=_(u"duplicate this layer"), required=False)
	remove_this_layer = forms.BooleanField(label=_(u"remove this layer"), required=False)
	move_this_layer = forms.ChoiceField(label=_(u"move this layer"), required=False,
					    choices=(("", _(9*u"-")), ("up", _(u"up")), ("down", _(u"down"))))

	def clean(self):
	    _ = ugettext
	    operations = 0
	    if self.cleaned_data["duplicate_this_layer"]:
		operations += 1
	    if self.cleaned_data["remove_this_layer"]:
		operations += 1
	    if self.cleaned_data.get("move_this_layer"):
		operations += 1
	    if operations > 1:
		raise ValidationError(_(u"You can't duplicate, move, or remove a layer at the same time."))
	    return self.cleaned_data


The FormSet
...............

Now we're ready to create the ``FormSet`` class which is basically a container
for methods that are used to manage the forms.  In order to avoid being forced
to pass all the forms and form lists to all of these routines, they are not
functions but methods, and the forms and form lists are instance variables of
the ``FormSet``.

By and large, also the ``FormSet`` can be copied from another deposition system
and carefully adopted.  In the case of the small cluster tool, most
modifications are due to the prlymorphic layers.

The first peculiarity is a dummy ``LayerForm`` class which is only to detect
the layer type when constructing forms from POST data, using the above
mentioned ``layer_type``::

    class LayerForm(forms.ModelForm):
        layer_type = forms.CharField()

I cannot explain all modification that are necessary but exemplarily, have a
look at the auxiliary routine ``build_layer_and_channel_forms``::

    def build_layer_and_channel_forms(deposition):
	self.layer_forms = []
	for index, layer in enumerate(deposition.layers.all()):
	    if hasattr(layer, "smallclustertoolhotwirelayer"):
		self.layer_forms.append(HotwireLayerForm(prefix=str(index),
                                        instance=layer.smallclustertoolhotwirelayer))
	    else:
		self.layer_forms.append(PECVDLayerForm(prefix=str(index),
                                        instance=layer.smallclustertoolpecvdlayer))

Here, you can see how I distinguish between the two layer types.

Furthermore, it's important that I don't let the user enter a layer number.
The ordering of the layers is simply determined by their ordering in the
webpage's form set.  I add the layer number in the ``save_to_database`` method.


The view functions
......................

You need an ``edit`` and a ``show`` view function.  They are really
straightforward.  Just copy them from another deposition module and modify them
slightly.  (Actually, this code duplication is a candidate for a common base
function but I'd like to implement more deposition systems just to be sure.)


Creating the templates
---------------------------

You need two templates per process, one that is called
``edit_process_name.html`` and the other that is called
``show_process_name.html``.  Copy them from the process which is most closely
related to the one you're editing and apply the necessary modifications.

Remember that the contents of the dictionary returned by
``get_additional_template_context`` contains a ``layers`` list in which each
layer also bears a ``type`` attribute, which can be used to render some parts
of the layers depending on whether they are hotwire or PECVD layers.  For
non-cluster-tool depositions however, you can use ``process.layers.all()`` in
the template code instead.

Read the docstrings in ``samples_extras.py`` for getting used to the filters
and tags special to Chantal.


Glossary
===========

.. glossary::

   process
      Anything that contains information about a sample.  This can be a process
      in the literal meaning of the word, i.e. a deposition, an etching, a
      clean room process etc.  It can also be a measurement or a result.
      However, even the substrate, sample split, and sample death are
      considered processes in chantal.

      It may have been better to call this “history item” or just “item”
      instead of “process”.  The name “process” is due to merely historical
      reasons, but there we go.

   measurement
      A special kind of *process* which contains a single measurement.  It
      belongs to the class of *physical processes*.

   physical process
      A deposition or a measurement process.  Its speciality is that only
      people with the right permission for a certain physical process are
      allowed to add and edit physical processes.

   result
      A result – or result process, as it is sometimes called in the source
      code – is a special process which contains only a remark, a picture, or a
      table with result values.

