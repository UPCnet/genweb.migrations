from Acquisition import aq_base
from Products.Five.browser import BrowserView

import base64
import sys
import pprint
import traceback

try:
    import simplejson as json
except:
    import json

from genweb.jsonify.wrapper import Wrapper


def _clean_dict(dct, error):
    new_dict = dct.copy()
    message = str(error)
    for key, value in dct.items():
        if message.startswith(repr(value)):
            del new_dict[key]
            return key, new_dict
    raise ValueError("Could not clean up object")


class GetItem(BrowserView):

    def __call__(self):
        """
        """
        try:
            context_dict = Wrapper(self.context)
        except Exception, e:
            tb = pprint.pformat(traceback.format_tb(sys.exc_info()[2]))
            return 'ERROR: exception wrapping object: %s\n%s' % (str(e), tb)

        passed = False
        while not passed:
            try:
                JSON = json.dumps(context_dict)
                passed = True
            except Exception, error:
                if "serializable" in str(error):
                    key, context_dict = _clean_dict(context_dict, error)
                    pprint.pprint('Not serializable member %s of %s ignored'
                         % (key, repr(self)))
                    passed = False
                else:
                    return ('ERROR: Unknown error serializing object: %s' %
                        str(error))

        self.request.response.setHeader('Content-Type', 'application/json')
        return JSON


class GetChildren(BrowserView):

    def __call__(self):
        """
        """

        children = []
        if getattr(aq_base(self.context), 'objectIds', False):
            children = self.context.objectIds()
            # Btree based folders return an OOBTreeItems
            # object which is not serializable
            # Thus we need to convert it to a list
            if not isinstance(children, list):
                children = [item for item in children]

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(children)


class GetCatalogResults(BrowserView):

    def __call__(self):
        """Returns a list of paths of all items found by the catalog.
           Query parameters can be passed in the request.
        """
        if not hasattr(self.context.aq_base, 'unrestrictedSearchResults'):
            return
        query = self.request.form.get('catalog_query', None)
        if query:
            query = eval(base64.b64decode(query),
                         {"__builtins__": None}, {})
        item_paths = [item.getPath() for item
                      in self.context.unrestrictedSearchResults(**query)]

        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(item_paths)
