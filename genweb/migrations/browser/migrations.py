from five import grok
from plone import api
from Products.CMFPlone.interfaces import IPloneSiteRoot

from collective.transmogrifier.transmogrifier import Transmogrifier
from zope.interface import alsoProvides
import pkg_resources

try:
    pkg_resources.get_distribution('plone4.csrffixes')
except pkg_resources.DistributionNotFound:
    CSRF = False
else:
    from plone.protect.interfaces import IDisableCSRFProtection
    CSRF = True


class PloneorgMigrationMain(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('ploneorg_migration_main')

    def render(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('plone.org.main')


class intranetUPCnet(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('intranet_migration')

    def render(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('intranetupcnet')
        return 'Done'


class MigrationTest(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('migration_test')

    def render(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('genweb.migrations.test')


class ExportDXTest(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('export_dx_test')

    def render(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('genweb.migrations.dxexport.test')


class ImportJSON(grok.View):
    grok.context(IPloneSiteRoot)
    grok.name('import_json')

    def render(self):
        portal = api.portal.get()
        transmogrifier = Transmogrifier(portal)
        transmogrifier('genweb.migrations.jsonimport')
        if CSRF:
            alsoProvides(self.request, IDisableCSRFProtection)
