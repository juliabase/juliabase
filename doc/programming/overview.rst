About this document
===================================

This document explains Chantal for the programmer.  It is a technical overview
of the whole architecture.  Moreover, it is a guide for adapting Chantal to a
new institute, research department, or scientific group.

If you want to read this manual, you should be familiar with several
technologies:

1.  *Python*.  You should have advanced experience in this language.  This
    includes the standard library; you should at least know what it can do and
    how to find information about it.

2.  *Django*.  You must have mastered the tutorial of the Django web framework.

3.  *HTML*.  Basic knowledge should be enough.


Architecture
====================

Since Chantal is based on the Django Web framework, it consists of several
Django apps.  The core app is called “chantal_common”.  It provides
functionality which is essential for all Chantal components.  On top of that,
the app “samples” contains all features of a samples database.  However, it
does not contain institute-specific code in order to remain generic and
flexible.  This institute-specific code resides in an app of its own and must
be created by a skilled programmer.


Adding a new process
==============================

So you want to add a new measurement device or manufacturing process (step) to
your Chantal installation.  You do so by adding new models, views, URLs, and
possibly tests to your own Django app “chantal_acme”.


Adding a new process model
========================================

It's probably best to start with the new database model because it will
determine the rest of the work.

Add the following code to ``models.py``::

    methode_choices=((u"profilers&edge", _(u"profilers + edge")),
		     (u"ellipsometer", _(u"ellipsometer")),
		     (u"calculated", _(u"calculated from deposition parameters")),
		     (u"estimate", _(u"estimate")),
		     (u"other", _(u"other")))

    class ThicknessMeasurement(PhysicalProcess):
        thickness = models.DecimalField(_(u"layer thickness"), max_digits=6,
                                        decimal_places=2, help_text=_(u"in nm"))
        method = models.CharField(_(u"measurement method"), max_length=30, 
                                  choices=methode_choices, default="profilers&edge")
