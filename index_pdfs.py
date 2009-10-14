#!/usr/bin/env python
# -*- coding: utf-8 -*-

u"""Stand-alone program to update Xapian's index.  Its synopsis is::

    index_pdfs.py <pdfs-root> [<citation-key> [<user-hash>]]

``<pdfs-root>`` is the directory which includes all subdirs with PDFs for the
given RefDB database.  ``<citation-key>`` is the citation key of the newly
added PDF.  If it was a private PDF upload, you must also give the
``<user-hash>`` of the uploading user (don't mix this up with the user ID or
his RefDB username).

If no citation key is given, all subdirs of ``<pdfs-root>`` are scanned and all
new PDFs are indexed.

If the citation key is the dash "-", Xapian's index database and all pickle
files in the PDF directories are deleted.  This effectively resets the
indexing.

The last path component of ``<pdfs-root>`` is taken as the Xapian index
database name in the directory ``/var/lib/django_refdb_indices``.  It must be
allowed to write to this directory.

This program calls several external programs: convert, tesseract, pdftotext,
pdfimages, and pdfinfo.

It writes a log to ``/tmp/index_pdfs.log``.

Normally, this program is started by the web server immediately after a new PDF
was uploaded.  However, it should also run as an (infrequent) cron job in order
to update everything that was skipped for some reason (for example, because of
a lock file).
"""

from __future__ import division

import subprocess, sys, os, os.path, re, datetime, codecs, pickle, shutil, logging
from glob import glob
import xapian


logging.basicConfig(level=logging.INFO, filename="/tmp/index_pdfs.log", filemode="a",
                    datefmt='%a, %d %b %Y %H:%M:%S', format="%(asctime)s %(name)s %(levelname)-8s %(message)s")
logger = logging.getLogger()


rootdir = os.path.abspath(sys.argv[1])
citation_key = sys.argv[2] if len(sys.argv) > 2 else None
user_hash = sys.argv[3] if len(sys.argv) > 3 else None

database_path = os.path.join("/var/lib/django_refdb_indices", os.path.basename(rootdir))
try:
    database = xapian.WritableDatabase(database_path, xapian.DB_CREATE_OR_OPEN)
except xapian.DatabaseLockError:
    logger.warning("Could not get lock file, giving up.")
    sys.exit()
indexer = xapian.TermGenerator()
stemmer = xapian.Stem("english")
indexer.set_stemmer(stemmer)


class LastIndexing(object):
    u"""Class for information of the last indexing of a particular PDF.  This
    class is pickled to a file in the same directory inw hich the PDF resides.
    This way, ``index_pdfs.py`` can see whether is must re-index the PDF
    because it's newer than the `timestamp`.

    :ivar document_ids: all Xapian document IDs of the pages of the PDF

    :ivar timestamp: the time of modification of the PDF when it was last
      indexed

    :type document_ids: list of int
    :type timestamp: int
    """
    def __init__(self, timestamp):
        u"""Class constructor.

        :Parameters:
          - `timestamp`: The time of modification of the PDF which is currently
            indexed.  It is the result of ``os.stat``'s ``st_mtime``.

        :type timestamp: int
        """
        self.document_ids = []
        self.timestamp = timestamp


def get_number_of_pages(pdf_filename):
    u"""Returns the number of pages in a PDF.

    :Parameters:
      - `pdf_filename`: PDF file to be analysed

    :type pdf_filename: str

    :Return:
      the number of pages in this PDF

    :rtype: int
    """
    output = subprocess.Popen(["pdfinfo", pdf_filename], stdout=subprocess.PIPE).communicate()[0]
    match = re.search(r"^Pages:\s+(\d+)$", output, re.MULTILINE)
    return int(match.group(1))


def clean_directory():
    u"""Removes all auxillary files from the current directory which were
    created by index_pdfs.py.  This includes the pickle file.
    """
    # FixMe: Actually, this routine doesn't remove all files created by this
    # program but rather removed all file with certain file extensions.  This
    # routine should be replaces with more fine-grained file deletion in
    # `index_pdf`.
    for filename in glob("*.txt") + glob("*.p?m") + glob("*.tif") + glob("*.pickle"):
        os.remove(filename)


def index_pdf(citation_key, user_hash):
    u"""Index one PDF with Xapian.  The PDF is identified by the citation key
    of the reference it belongs to.

    Here is how Xapian is used for indexing: Every page in the PDF becomes one
    document in Xapian's notation.  Its associated data (set_data/get_data) is
    the text content of the page.  Up to three so-called “values” are set:
    Value 0 is the citation key, value 1 is the page number (note that this is
    the dull PDF page number rather than a “document page number”), and value 2
    is the user hash (which may not be set).  The user hash allows for a
    ``MatchDecider`` to filter out all PDFs from the matches which belong to
    other users.

    :Parameters:
      - `citation_key`: the citation key of the reference
      - `user_hash`: the user hash of the user if it is a private PDF; ``None``
        if otherwise

    :type citation_key: str
    :type user_hash: str
    """
    pdf_identifier = citation_key + (" for user " + user_hash if user_hash else "")
    logger.info(pdf_identifier + " is processed ...")
    path = os.path.join(rootdir, citation_key)
    if user_hash:
        path = os.path.join(path, user_hash)
    os.chdir(path)
    try:
        pdf_filename = glob("*.pdf")[0]
    except IndexError:
        logger.warning("No PDF found!")
        return
    pdf_timestamp = os.stat(pdf_filename).st_mtime
    try:
        last_indexing = pickle.load(open("last_indexing.pickle", "rb"))
    except IOError:
        pass
    else:
        if last_indexing.timestamp == pdf_timestamp:
            logger.info("Indexing up to date, no further indexing done.")
            return
        for document_id in last_indexing.document_ids:
            try:
                database.delete_document(document_id)
            except xapian.DocNotFoundError, e:
                logger.error("Xapian: " + str(e))
    last_indexing = LastIndexing(pdf_timestamp)
    number_of_pages = get_number_of_pages(pdf_filename)
    total_text_length = 0
    for page_number in range(1, number_of_pages + 1):
        page_filename = "page-%d.txt" % page_number
        logger.info("Calling pdftotext for page %d" % page_number)
        subprocess.call(["pdftotext", "-f" , str(page_number), "-l", str(page_number), "-enc", "UTF-8",
                         pdf_filename, page_filename])
        total_text_length += os.stat(page_filename).st_size
    logger.info("Characters per page: %g" % (total_text_length / number_of_pages))
    is_scanned = total_text_length / number_of_pages < 100
    if is_scanned:
        logger.info(citation_key + " was scanned.  Firing up Tesseract ...")
        # FixMe: pdfimages should be called with the -f and -l arguments like
        # pdftotext above.  There should be defined behaviour if more than one
        # image is generated per page.  This way, one could also get rid of the
        # "if is_scanned" clause below.
        subprocess.call(["pdfimages", pdf_filename, "page"])
        # FixMe: The tesseract processes should be started parallely in order
        # to make use of multi-processor systems.
        for filename in glob("page-*.p?m"):
            tif_filename = filename[:-4] + ".tif"
            subprocess.call(["convert", filename, tif_filename])
            subprocess.call(["tesseract", tif_filename, filename[:-4], "-l", "eng"], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    logger.info("Indexing ...")
    for filename in glob("page-*.txt"):
        text = codecs.open(filename, encoding="utf-8").read()
        page_number = int(filename[5:-4])
        if is_scanned:
            page_number += 1
        document = xapian.Document()
        document.set_data(text)
        document.add_value(0, citation_key)
        document.add_value(1, str(page_number))
        if user_hash:
            document.add_value(2, user_hash)
        indexer.set_document(document)
        indexer.index_text(text)
        document_id = database.add_document(document)
        last_indexing.document_ids.append(document_id)
    clean_directory()
    pickle.dump(last_indexing, open("last_indexing.pickle", "wb"))
    logger.info(pdf_identifier + " done.")


logger.info("Start with parameters: " + " ".join(sys.argv[1:]))
if citation_key == "-":
    for path in glob(os.path.join(rootdir, "*")):
        if os.path.isdir(path):
            os.chdir(path)
            clean_directory()
            for user_path in glob(os.path.join(path, "*")):
                if os.path.isdir(user_path):
                    os.chdir(user_path)
                    clean_directory()
    shutil.rmtree(database_path)
elif citation_key:
    index_pdf(citation_key, user_hash)
else:
    for path in glob(os.path.join(rootdir, "*")):
        if os.path.isdir(path):
            citation_key = os.path.basename(path)
            index_pdf(citation_key, user_hash=None)
            for user_path in glob(os.path.join(path, "*")):
                if os.path.isdir(user_path):
                    user_hash = os.path.basename(user_path)
                    index_pdf(citation_key, user_hash)
logger.info("Finished")
