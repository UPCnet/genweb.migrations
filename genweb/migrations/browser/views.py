from copy import deepcopy
from five import grok
from plone import api
from Products.CMFPlone.interfaces import IPloneSiteRoot
from collective.transmogrifier.transmogrifier import configuration_registry
from collective.transmogrifier.transmogrifier import Transmogrifier


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
