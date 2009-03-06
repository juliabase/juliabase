.PHONY: src-doc-sf src-doc tests pylint src-doc-svn

src-doc:
	export DJANGO_SETTINGS_MODULE=settings ; export PYTHONPATH=/home/bronger/src/chantal/current/chantal ; epydoc --config=epydoc.cfg
	rsync --rsh=ssh -avuz epydoc/* bob:~/chantal-src/
