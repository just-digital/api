#!/usr/bin/env python
# encoding: utf-8

# standard library imports
import datetime
from optparse import make_option
import os
import sys
import urllib
import unicodedata

# django imports
from django.core.management.base import BaseCommand

# openscriptures imports
from apps.core.models import Language, License, Server
from apps.texts.models import Token, Work, Structure, WorkServer
from apps.core import osis

class OpenScripturesImport():
    """Class to facilitate the import of data into OpenScriptures models.

    OpenScripturesImport handles the creation of various OpenScriptures data model objects
    (works, tokens, structures) and provides the necessary functions to process the data."""

    def __init__(self):
        self.work1 = None
        self.tokenCount = 0
        self.bookTokens = []
        self.structs = {}
        self.structCount = 0
        self.book_codes = None        
        self.current_book = None
        self.current_chapter = None
        self.current_verse = None
        # For the paragraph token object, not the struct
        self.current_paragraph = None

    def create_whitespace_token(self):
        ws_token = Token(
            data     = " ",
            type     = Token.WHITESPACE,
            work     = self.work1,
            position = self.tokenCount,
            )
        self.tokenCount += 1
        ws_token.save()
        self.bookTokens.append(ws_token)

    def create_book_struct(self):
        self.structs[Structure.BOOK] = Structure(
            work = self.work1,
            type = Structure.BOOK,
            osis_id = self.current_book,
            position = self.structCount,
            numerical_start = self.book_codes.index(self.current_book),
            )
        self.structCount += 1
        print self.current_book
        
    def create_title_struct(self):
        self.structs[Structure.TITLE] = Structure(
            work = self.work1,
            type = Structure.TITLE,
            position = self.structCount,
            )
        self.structCount += 1
     
    def create_chapter_struct(self):       
        self.structs[Structure.CHAPTER] = Structure(
            work = self.work1,
            type = Structure.CHAPTER,
            position = self.structCount,
            osis_id = self.current_book + "." + self.current_chapter,
            numerical_start = self.current_chapter,
        )
        self.structCount += 1     
     
    def create_chapter_struct(self):       
        self.structs[Structure.CHAPTER] = Structure(
            work = self.work1,
            type = Structure.CHAPTER,
            position = self.structCount,
            osis_id = self.current_book + "." + self.current_chapter,
            numerical_start = self.current_chapter,
        )
        print self.structs[Structure.CHAPTER].osis_id
        self.structCount += 1

    def create_verse_struct(self):
        self.structs[Structure.VERSE] = Structure(
            work = self.work1,
            type = Structure.VERSE,
            position = self.structCount,
            osis_id = self.current_book + "." + self.current_chapter + "." + self.current_verse,
            numerical_start = self.current_verse,
        )
        print self.structs[Structure.VERSE].osis_id
        self.structCount += 1

    def create_paragraph(self):
        current_paragraph = None
        if len(self.bookTokens) > 0 and self.structs.has_key(Structure.PARAGRAPH):
            current_paragraph = Token(
                data     = u"\u2029", #¶ "\n\n"
                type     = Token.WHITESPACE, #i.e. PARAGRAPH
                work     = self.work1,
                position = self.tokenCount,
            )
            self.tokenCount += 1
            current_paragraph.save()
            self.structs[Structure.PARAGRAPH].end_marker = current_paragraph
            self.close_structure(Structure.PARAGRAPH)            
            self.bookTokens.append(current_paragraph)

        assert(not self.structs.has_key(Structure.PARAGRAPH))
        print("¶")
        self.structs[Structure.PARAGRAPH] = Structure(
            work = self.work1,
            type = Structure.PARAGRAPH,
            position = self.structCount,
        )
        if current_paragraph:
            self.structs[Structure.PARAGRAPH].start_marker = current_paragraph
        self.structCount += 1

    def create_token(self, token_data):
        token_work1 = Token(
            data     = token_data,
            type     = Token.WORD,
            work     = self.work1,
            position = self.tokenCount,
        )
        self.tokenCount += 1
        token_work1.save()
        self.bookTokens.append(token_work1)

    def create_punct_token(self, punct_data):
        punc_token = Token(
            data     = punct_data,
            type     = Token.PUNCTUATION,
            work     = self.work1,
            position = self.tokenCount,
        )
        self.tokenCount += 1
        punc_token.save()
        self.bookTokens.append(punc_token)

    def link_start_tokens(self):
        """
        Links structure.start_token to the most recent token.

        Structure objects require a start_token. However, that token is
        not typically present when the structure is created. Find each 
        open Structure which lacks a start_token and link it to the most
        recently created token. This should be run after tokens are created.
        """
        
        # Only attmpt a link if there is a token. Only a concern for first paragraph token in book
        if len(self.bookTokens) > 0:
            for struct in self.structs.values():
                if struct.start_token is None:
                    struct.start_token = self.bookTokens[-1]

    def delete_work(self, work):
        "Deletes a work without a greedy cascade"
     
        if work.variants_for_work is not None:
            delete_work(work.variants_for_work)
    
        # Clear all links to unified text
        Token.objects.filter(work = work).delete() #Does this need to be two linces?
    
        # Delete all variant works
        Work.objects.filter(variants_for_work = work).delete()
    
        # Delete work
        #Work.objects.filter(id=workID).update(unified_token=None)        
        work.delete()
        return True


    def normalize_token(self, data):
        "Normalize to Unicode NFC, strip out all diacritics, apostrophies, and make lower-case."
        # credit: http://stackoverflow.com/questions/517923/what-is-the-best-way-to-remove-accents-in-a-python-unicode-string
        data = unicodedata.normalize('NFC', ''.join((c for c in unicodedata.normalize('NFD', data) if unicodedata.category(c) != 'Mn')).lower())
        data = data.replace(r'\s+', ' ')
        #data = re.sub(ur"['’]", '', data)
        data = data.replace(u"'", '')
        data = data.replace(u"’", '')
        return data

    def download_resource(self, source_url):
        "Download the file in the provided URL if it does not already exist in the working directory."
        if(not os.path.exists(os.path.basename(source_url))):
            if(not os.path.exists(os.path.basename(source_url))):
                print "Downloading " + source_url
                urllib.urlretrieve(source_url, os.path.basename(source_url))

    def abort_if_imported(self, slug, force=False):
        "Shortcut see if the provided work ID already exists in the system; if so, then abort unless --force command line argument is supplied"
        if len(Work.objects.filter(osis_slug=slug)) > 0 and not force:
            print " (already imported; pass --force option to delete existing work and reimport)"
            exit()

    def get_book_code_args(self):
        book_codes = []
        for arg in sys.argv:
            if arg in osis.BIBLE_BOOK_CODES:
                book_codes.append(arg)
        return book_codes
    
    def close_structure(self, type):
        if self.structs.has_key(type):
            # Ensure the structure has a start_token
            assert(self.structs[type].start_token is not None)
            if self.structs[type].end_token is None:
            # Exclude whitespace tokens from the end of verses and chapters
                if self.bookTokens[-1].data == " " and (type == Structure.CHAPTER or type == Structure.VERSE):
                    self.structs[type].end_token = self.bookTokens[-2]
                else:
                    self.structs[type].end_token = self.bookTokens[-1]
            self.structs[type].save()
            del self.structs[type]

# TODO
# - Kethiv/Qere
# - Brackets
