import base64
import urllib
import urllib2
import simplejson
from zope.interface import classProvides, implements
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from collective.jsonmigrator import logger

import requests


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
        remote_username = self.get_option('remote-username', 'admin')
        remote_token = self.get_option('remote-token', '')

        catalog_path = self.get_option('catalog-path', '/Plone/portal_catalog')
        self.site_path_length = len('/'.join(catalog_path.split('/')[:-1]))

        catalog_query = self.get_option('catalog-query', None)
        catalog_query = ' '.join(catalog_query.split())
        catalog_query = base64.b64encode(catalog_query)

        self.remote_skip_paths = self.get_option('remote-skip-paths',
                                                 '').split()

        # Forge request
        self.payload = {'catalog_query': catalog_query}
        self.headers = {'X-Oauth-Username': remote_username,
                   'X-Oauth-Token': remote_token,
                   'X-Oauth-Scope': 'widgetcli',
                   }

        # Make request
        resp = requests.get('{}{}/get_catalog_results'.format(self.remote_url, catalog_path), params=self.payload, headers=self.headers)

        self.item_paths = sorted(simplejson.loads(resp.text))

    def get_option(self, name, default):
        """Get an option from the request if available and fallback to the
        transmogrifier config.
        """
        request = getattr(self.context, 'REQUEST', None)
        if request is not None:
            value = request.form.get('form.widgets.'+name.replace('-', '_'),
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
                if path.startswith(skip_path):
                    skip = True
            if not skip:
                item = self.get_remote_item(path)
                if item:
                    item['_path'] = item['_path'][self.site_path_length:]
                    yield item

    def get_remote_item(self, path):
        item_url = '%s%s/get_item' % (self.remote_url, urllib.quote(path))

        resp = requests.get(item_url, params=self.payload, headers=self.headers)

        if resp.status_code == 200:
            item_json = resp.text
        else:
            logger.error("Failed reading item from %s. %s" % (item_url, resp.status_code))
            return None
        try:
            item = simplejson.loads(item_json)
        except simplejson.JSONDecodeError:
            logger.error("Could not decode item from %s." % item_url)
            return None
        return item
