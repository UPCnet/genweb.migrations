# -*- coding: utf-8 -*-
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.utils import resolvePackageReferenceOrFile
from zope.interface import classProvides
from zope.interface import implements
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility
from plone.i18n.normalizer.interfaces import IURLNormalizer

import os
import json as simplejson
import urllib

DATAFIELD = '_datafield_'

VALIDATIONKEY = 'genweb.migrations.logger'
ERROREDKEY = 'genweb.migrations.errors'
COUNTKEY = 'genweb.migrations.count'


class JSONSourceSection(object):
    """
    A source section wich gets items from a json file specified using 'path'
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        # next is for communication with 'logger' section
        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])
        self.errored = self.anno.setdefault(ERROREDKEY, [])
        self.item_count = self.anno.setdefault(COUNTKEY, {})

        jsonsource = resolvePackageReferenceOrFile(options['path'])
        if (
            jsonsource is None or
            not os.path.isfile(jsonsource) or
            not jsonsource.endswith('.json')
        ):
            raise Exception('File (' + str(jsonsource) + ') is not a valid json file.')

        with open(jsonsource) as f:
            self.items = simplejson.loads(f.read())
            self.item_count['total'] = len(self.items)
            self.item_count['remaining'] = len(self.items)

        self.datafield_prefix = options.get('datafield-prefix', DATAFIELD)
        self.normalizer = getUtility(IURLNormalizer)

    def normalize(self, item):
        def normalize_url(url):
            return '/'.join([
                self.normalizer.normalize(part)
                for part in urllib.unquote(url).decode('utf-8').split('/')
            ])

        for attr in ['_path', '_id', 'id', '_translationOf']:
            if attr in item:
                item[attr] = normalize_url(item[attr].encode('utf-8'))

        if '_translations' in item:
            for lang in item['_translations']:
                item['_translations'][lang] = normalize_url(item['_translations'][lang].encode('utf-8'))

        if '_properties' in item:
            del item['_properties']

        return item

    def __iter__(self):
        for item in self.previous:
            yield item

        for item in self.items:
            if '_path' in item:
                self.storage.append(item['_path'])
            else:
                self.storage.append(item)
            yield self.normalize(item)
