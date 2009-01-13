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

