import base64
import urllib
import urllib2
import json as simplejson
import unicodedata
from zope.interface import classProvides, implements
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from collective.jsonmigrator import logger
from zope.annotation.interfaces import IAnnotations
from Products.Collage.utilities import generateNewId


import requests

VALIDATIONKEY = 'genweb.migrations.logger'
ERROREDKEY = 'genweb.migrations.errors'
COUNTKEY = 'genweb.migrations.count'


class CatalogSourceSection(object):
    """A source section which creates items from a remote Plone site by
       querying it's catalog.
       This adaptation uses an oAuth Osiris server for authentication.
    """
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.options = options
        self.context = transmogrifier.context

        self.remote_url = self.get_option('remote-url',
                                          'http://localhost:8080')
        self.remote_username = self.get_option('remote-username', 'admin')
        self.remote_password = self.get_option('remote-password', 'admin')

        catalog_path = self.get_option('catalog-path', '/Plone/portal_catalog')
        self.site_path_length = len('/'.join(catalog_path.split('/')[:-1]))

        catalog_query = self.get_option('catalog-query', None)
        catalog_query = ' '.join(catalog_query.split())
        catalog_query = base64.b64encode(catalog_query)

        self.remote_skip_paths = self.get_option('remote-skip-paths',
                                                 '').split()
        self.remote_root = self.get_option('remote-root', '')

        # next is for communication with 'logger' section
        self.anno = IAnnotations(transmogrifier)
        self.storage = self.anno.setdefault(VALIDATIONKEY, [])
        self.errored = self.anno.setdefault(ERROREDKEY, [])
        self.item_count = self.anno.setdefault(COUNTKEY, {})

        # Forge request
        self.payload = {'catalog_query': catalog_query}

        # Make request
        resp = requests.get('{}{}/get_catalog_results'.format(self.remote_url, catalog_path), params=self.payload, auth=(self.remote_username, self.remote_password))

        self.item_paths = sorted(simplejson.loads(resp.text))
        self.item_count['total'] = len(self.item_paths)
        self.item_count['remaining'] = len(self.item_paths)

    def get_option(self, name, default):
        """Get an option from the request if available and fallback to the
        transmogrifier config.
        """
        request = getattr(self.context, 'REQUEST', None)
        if request is not None:
            value = request.form.get('form.widgets.' + name.replace('-', '_'),
                                     self.options.get(name, default))
        else:
            value = self.options.get(name, default)
        if isinstance(value, unicode):
            value = value.encode('utf8')
        return value

    def __iter__(self):
        for item in self.previous:
            yield item

        for path in self.item_paths:
            skip = False
            for skip_path in self.remote_skip_paths:
                if path.startswith(self.remote_root + skip_path):
                    skip = True

            # Skip old talkback items
            if 'talkback' in path:
                skip = True

            if not skip:
                self.storage.append(path)
                #can't get the item
                try:
                    item = self.get_remote_item(path)
                except:
                    continue

                if item:
                    item['_path'] = item['_path'][self.site_path_length:]
                    item['_auth_info'] = (self.remote_username, self.remote_password)
                    item['_site_path_length'] = self.site_path_length

                    # Update css class to GW4
                    text_content = ptype = item.get('text', '')
                    if text_content != '':
                        text_updated = self.updateCss(text_content)
                        item['text'] = text_updated

                    ptype = item.get('_type', False)
                    ppath = item.get('_path', False)
                    if '/seu-electoral/eleccions-anteriors/eleccions-electroniques/2010/' in ppath:
                        continue

                    # Create filenames without accent
                    if ptype == 'File':
                        filename = unicodedata.normalize('NFKD', item['_datafield_file']['filename']).encode('ascii',errors='ignore')
                        item['_datafield_file']['filename'] = filename

                    if ptype == 'Topic':
                        item['_type'] = 'Collection'
                        item['_classname'] = 'Dexterity Item'

                    # Create correct forms
                    if ptype == 'FormSaveDataAdapter':
                        if len(item['SavedFormInput']) == 0:
                            continue
                        sd = unicodedata.normalize('NFKD', item['SavedFormInput']).encode('ascii',errors='ignore')
                        item['SavedFormInput'] = sd

                    if (ptype == 'FormStringField' or ptype == 'FormSelectionField'
                        or ptype == 'FieldsetFolder' or ptype =='FormTextField'
                        or ptype == 'FormMultiSelectionField'):
                        desc = unicodedata.normalize('NFKD', item['description']).encode('ascii',errors='ignore')
                        item['description'] = desc

                    # Banners create correct attributes
                    if ptype == 'Banner' or ptype == 'Logos_Footer':
                        item['remoteUrl'] = item['URLdesti']
                        item['open_link_in_new_window'] = item['Obrirennovafinestra']

                        if '_datafield_Imatge' in item:
                            imagen = item['_datafield_Imatge']
                            # to take image
                            item['_datafield_image'] = item['_datafield_Imatge']

                    # Collage sub-items fetcher
                    if ptype == 'Collage':
                        collageRows = []
                        collageColumns = []
                        collageObjects = []
                        for key in item.keys():
                            if key.startswith('_rowCollage'):
                                collageRows.append(item[key])
                                del item[key]
                            if key.startswith('_colCollage'):
                                collageColumns.append(item[key])
                                del item[key]
                            if key.startswith('_aliasCollage') or key.startswith('_finalObjectCollage'):
                                collageObjects.append(item[key])
                                del item[key]
                        # Yield the main Collage
                        yield item

                        # Yield the Collage components, in order (because the parent should exist before!)
                        for component in collageRows:
                            component['_path'] = component['_path'][self.site_path_length:]
                            component['_auth_info'] = (self.remote_username, self.remote_password)
                            component['_site_path_length'] = self.site_path_length
                            yield component
                        for component in collageColumns:
                            component['_path'] = component['_path'][self.site_path_length:]
                            component['_auth_info'] = (self.remote_username, self.remote_password)
                            component['_site_path_length'] = self.site_path_length
                            yield component
                        for component in collageObjects:
                            component['_path'] = component['_path'][self.site_path_length:]
                            component['_auth_info'] = (self.remote_username, self.remote_password)
                            component['_site_path_length'] = self.site_path_length
                            yield component

                    else:
                        yield item

    def get_remote_item(self, path):
        item_url = '%s%s/get_item' % (self.remote_url, urllib.quote(path))

        resp = requests.get(item_url, params=self.payload, auth=(self.remote_username, self.remote_password))

        if resp.status_code == 200:
            item_json = resp.text
        else:
            logger.error("Failed reading item from %s. %s" % (path, resp.status_code))
            self.errored.append(path)
            return None
        try:
            item = simplejson.loads(item_json)
        except simplejson.JSONDecodeError:
            logger.error("Could not decode item from %s." % item_url)
            logger.error("Response is %s." % item_json)
            self.errored.append(path)
            return None
        return item

    def updateCss(self,text):
        text = text.replace("colSupContenidor","row")
        text = text.replace("colSupDreta","span4 pull-right")
        text = text.replace("colSupEsq","span8")
        text = text.replace("caixaPortlet","box")
        text = text.replace("llistatDestacat","list list-highlighted")
        text = text.replace("mceItemTable","table table-bordered table-hover")
        text = text.replace("align_left","image-left")
        text = text.replace("align_right","image-right")
        text = text.replace("invisible","")
        return text
