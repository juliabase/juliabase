#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
database = xapian.WritableDatabase(database_path, xapian.DB_CREATE_OR_OPEN)
indexer = xapian.TermGenerator()
stemmer = xapian.Stem("english")
indexer.set_stemmer(stemmer)


class LastIndexing(object):
    def __init__(self, timestamp):
        self.document_ids = []
        self.timestamp = timestamp


def get_number_of_pages(pdf_filename):
    output = subprocess.Popen(["pdfinfo", pdf_filename], stdout=subprocess.PIPE).communicate()[0]
    match = re.search(r"^Pages:\s+(\d+)$", output, re.MULTILINE)
    return int(match.group(1))


def clean_directory():
    for filename in glob("*.txt") + glob("*.p?m") + glob("*.tif") + glob("*.pickle"):
        os.remove(filename)


def index_pdf(citation_key, user_hash):
    pdf_identifier = citation_key + (" for user " + user_hash if user_hash else "")
    logger.info(pdf_identifier + " is processed ...")
    print citation_key, user_hash if user_hash else ""
    path = os.path.join(rootdir, citation_key)
    if user_hash:
        path = os.path.join(path, user_hash)
    os.chdir(path)
    try:
        pdf_filename = glob("*.pdf")[0]
    except IndexError:
        logger.warning("No PDF found!")
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
        subprocess.call(["pdfimages", pdf_filename, "page"])
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
