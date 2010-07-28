#
# This file is part of Chantal, the samples database.
#
# Copyright (C) 2010 Forschungszentrum Jülich, Germany,
#                    Marvin Goblet <m.goblet@fz-juelich.de>,
#                    Torsten Bronger <t.bronger@fz-juelich.de>
#
# You must not use, install, pass on, offer, sell, analyse, modify, or
# distribute this software without explicit permission of the copyright holder.
# If you have received a copy of this software without the explicit permission
# of the copyright holder, you must destroy it immediately and completely.

.PHONY: src-doc-sf src-doc tests pylint src-doc-svn

src-doc:
	export DJANGO_SETTINGS_MODULE=settings ; export PYTHONPATH=/home/bronger/src/chantal/current/chantal ; epydoc --config=epydoc.cfg
	rsync --rsh=ssh -avuz epydoc/* bob:~/chantal-src/
