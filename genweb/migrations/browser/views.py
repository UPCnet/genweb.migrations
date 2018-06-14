from copy import deepcopy
from five import grok
from plone import api
from Products.CMFPlone.interfaces import IPloneSiteRoot
from collective.transmogrifier.transmogrifier import configuration_registry
from collective.transmogrifier.transmogrifier import Transmogrifier

from unidecode import unidecode
from plone.app.contenttypes.behaviors.richtext import IRichText
import transaction

from Products.CMFCore.utils  import  getToolByName
from plone.app.textfield.value import RichTextValue

from Products.CMFPlone.utils import safe_unicode
from Acquisition import aq_inner, aq_parent
from zope.interface import Interface


TEMPLATE = """[transmogrifier]
include = genweb.migrations.common

[catalogsource]
blueprint = genweb.migrations.catalogsource
remote-url = %(remote-url)s
remote-username = %(remote-username)s
remote-password = %(remote-password)s
remote-root = %(remote-root)s
catalog-path = %(remote-root)s/portal_catalog
catalog-query = %(catalog-query)s
remote-skip-paths = %(remote-skip-paths)s
"""

class LotusMigration(grok.View):
    grok.name("lotus_migration")
    grok.context(IPloneSiteRoot)
    grok.require('cmf.ManagePortal')

    def render(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('genweb.migrations.lotus')

class LotusView(grok.View):
    grok.name("lotus_view")
    grok.context(Interface)
    grok.require('cmf.ManagePortal')
    grok.template('lotus_migration')

    def update(self):
        portal = api.portal.get()
        context = self.context
        catalog = getToolByName(context, 'portal_catalog')
        folder_path = '/'.join(context.getPhysicalPath())
        results = catalog(path={'query': folder_path},portal_type='Folder')
        for brain in results:
            items = len(catalog(path={"query": brain.getPath(), "depth": 1},portal_type='Folder'))
            if items == 0:
                pages = catalog(path={"query": brain.getPath(), "depth": 1},portal_type='Document')
                objs = [b.getObject() for b in pages ]
                for o in objs:
                    parent = o.aq_parent
                    parent.setDefaultPage(o.getId())
                    parent.setModificationDate(o.creation_date)
                    parent.reindexObject(idxs=['modified'])
                    o.setModificationDate(o.creation_date)
                    o.reindexObject(idxs=['modified'])
                    self.update_parents(parent,folder_path)
            else:
                results = catalog(path={'query': brain.getPath(), "depth": 1},portal_type='Document')
                res_objs = [b.getObject() for b in results ]
                for ob in res_objs:
                    ob.setModificationDate(ob.creation_date)
                    ob.reindexObject(idxs=['modified'])
        transaction.commit()


    def update_parents(self,obj,path):
        parent = obj.aq_inner.aq_parent
        if '/'.join(obj.getPhysicalPath()) == path:
            pass
        else:
            parent.setModificationDate(obj.creation_date)
            parent.reindexObject(idxs=['modified'])
            self.update_parents(parent,path)

class ChangeTagView(grok.View):
    grok.name("change_tag")
    grok.context(Interface)
    grok.require('cmf.ManagePortal')
    grok.template('lotus_migration')

    def update(self):
        portal = api.portal.get()
        context = self.context
        catalog = getToolByName(context, 'portal_catalog')
        folder_path = '/'.join(context.getPhysicalPath())
        results = catalog(path={'query': folder_path},portal_type='Folder')
        for brain in results:
                pages = catalog(path={"query": brain.getPath(), "depth": 1},portal_type='Document')
                objs = [b.getObject() for b in pages ]
                #import ipdb; ipdb.set_trace()
                for o in objs:
                    body = o.text.raw
                    body = body.replace('<b>','<strong>')
                    body = body.replace('</b>','</strong>')
                    o.text = IRichText['text'].fromUnicode(body)
                    o.reindexObject(idxs=['text'])
                    transaction.commit()

class MigrationDashboard(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('migration_dashboard')

    def update(self):
        self.form_values = {'remote-skip-paths': '/templates', 'catalog-query': "{'path': {'query': '/espaitic/espaitic/informacio'}, 'Language': 'ca'}", 'remote-password': 'admin', 'remote-url': 'http://sylarc.upc.edu:11008', 'remote-username': 'admin', 'remote-root': '/espaitic/espaitic'}
        if self.request.method == 'POST':
            config = deepcopy(self.request.form)
            self.write_config(config)
            self.form_values = self.request.form
            self.execute_migration()

    def write_config(self, config):
        config['remote-skip-paths'] = ' '.join(config['remote-skip-paths'].split())
        dashboard = configuration_registry.getConfiguration('genweb.migrations.dashboard')
        filename = dashboard['configuration']
        config_file = open(filename, 'w')
        config_file.write(TEMPLATE % config)
        config_file.close()

    def execute_migration(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('genweb.migrations.dashboard')
