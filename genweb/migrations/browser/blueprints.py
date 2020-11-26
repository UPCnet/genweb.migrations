import base64
import datetime
import logging
import pprint
from copy import deepcopy
from datetime import datetime

import pkg_resources
import pytz

from AccessControl.interfaces import IRoleManager
from Acquisition import aq_base
from collective.transmogrifier.interfaces import ISection, ISectionBlueprint
from collective.transmogrifier.utils import (Matcher, defaultKeys,
                                             defaultMatcher)
from DateTime import DateTime
from genweb.migrations.interfaces import IDeserializer
from plone import api
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.uuid.interfaces import IUUID
from Products.Archetypes.interfaces import IBaseObject
from zope.app.container.contained import notifyContainerModified
from zope.interface import classProvides, implements
from zope.schema import getFieldsInOrder

try:
    pkg_resources.get_distribution('plone.app.multilingual')
except pkg_resources.DistributionNotFound:
    HAS_PAM = False
else:
    from plone.app.multilingual.interfaces import ITranslationManager
    HAS_PAM = True

migration_error = logging.getLogger('migration_error')


class PrettyPrinter(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.pprint = pprint.PrettyPrinter().pprint

    def __iter__(self):
        def undict(source):
            """ Recurse through the structure and convert dictionaries
                into sorted lists
            """
            res = list()
            if type(source) is dict:
                source = sorted(source.items())
            if type(source) in (list, tuple):
                for item in source:
                    res.append(undict(item))
            else:
                res = source
            # convert a tuple into tuple back
            if type(source) is tuple:
                res = tuple(res)
            return res

        for item in self.previous:
            self.pprint(undict(item))
            yield item


class DataFields(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context
        self.datafield_prefix = options.get('datafield-prefix', '_datafield_')
        self.root_path_length = len(self.context.getPhysicalPath())

    def __iter__(self):
        for item in self.previous:
            # not enough info
            if '_path' not in item:
                yield item
                continue

            obj = self.context.unrestrictedTraverse(str(item['_path'].lstrip('/')), None)

            # path doesn't exist
            if obj is None:
                yield item
                continue

            # do nothing if we got a wrong object through acquisition
            path = item['_path']
            if path.startswith('/'):
                path = path[1:]
            if '/'.join(obj.getPhysicalPath()[self.root_path_length:]) != path:
                yield item
                continue

            for key in item.keys():

                if not key.startswith(self.datafield_prefix):
                    continue

                fieldname = key[len(self.datafield_prefix):]

                if IBaseObject.providedBy(obj):

                    field = obj.getField(fieldname)
                    if field is None:
                        continue
                    if item[key].has_key('data'):
                        value = base64.b64decode(item[key]['data'])
                    else:
                        value = ''
                    # XXX: handle other data field implementations
                    old_value = field.get(obj).data
                    if value != old_value:
                        field.set(obj, value)
                        obj.setFilename(item[key]['filename'])
                        obj.setContentType(item[key]['content_type'])
                else:
                    # We have a destination DX type
                    field = None
                    for schemata in iterSchemata(obj):
                        for name, s_field in getFieldsInOrder(schemata):
                            if name == fieldname:
                                field = s_field
                                deserializer = IDeserializer(field)
                                value = deserializer(item[key], None, item)
                                field.set(field.interface(obj), value)
                    if not field:
                        print('Can\'t find a suitable destination field '.format(fieldname))
            yield item


class WorkflowHistory(object):
    """
    """
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context
        self.wftool = api.portal.get_tool(name='portal_workflow')

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'workflowhistory-key' in options:
            workflowhistorykeys = options['workflowhistory-key'].splitlines()
        else:
            workflowhistorykeys = defaultKeys(options['blueprint'], name, 'workflow_history')
        self.workflowhistorykey = Matcher(*workflowhistorykeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            workflowhistorykey = self.workflowhistorykey(*item.keys())[0]

            if not pathkey or not workflowhistorykey or \
               workflowhistorykey not in item:  # not enough info
                yield item; continue

            obj = self.context.unrestrictedTraverse(str(item[pathkey]).lstrip('/'), None)
            if obj is None or not getattr(obj, 'workflow_history', False):
                yield item; continue

            if IBaseObject.providedBy(obj) or IDexterityContent.providedBy(obj):
                item_tmp = deepcopy(item)

                wf_hist_temp = deepcopy(item[workflowhistorykey])

                for workflow in wf_hist_temp:
                    # Normalize workflow
                    if workflow == u'genweb_review':
                        for k, workflow2 in enumerate(item_tmp[workflowhistorykey]['genweb_review']):
                            if 'review_state' in item_tmp[workflowhistorykey]['genweb_review'][k]:
                                if item_tmp[workflowhistorykey]['genweb_review'][k]['review_state'] == u'esborrany':
                                    item_tmp[workflowhistorykey]['genweb_review'][k]['review_state'] = u'visible'

                        item_tmp[workflowhistorykey]['genweb_simple'] = item_tmp[workflowhistorykey]['genweb_review']
                        del item_tmp[workflowhistorykey]['genweb_review']

                # get back datetime stamp and set the workflow history
                for workflow in item_tmp[workflowhistorykey]:
                    for k, workflow2 in enumerate(item_tmp[workflowhistorykey][workflow]):
                        if 'time' in item_tmp[workflowhistorykey][workflow][k]:
                            item_tmp[workflowhistorykey][workflow][k]['time'] = DateTime(item_tmp[workflowhistorykey][workflow][k]['time'])

                obj.workflow_history.data = item_tmp[workflowhistorykey]

                # update security
                workflows = self.wftool.getWorkflowsFor(obj)
                if workflows:
                    workflows[0].updateRoleMappingsFor(obj)

            yield item


class LocalRoles(object):
    """ """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'local-roles-key' in options:
            roleskeys = options['local-roles-key'].splitlines()
        else:
            roleskeys = defaultKeys(options['blueprint'], name, 'local_roles')
        self.roleskey = Matcher(*roleskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            roleskey = self.roleskey(*item.keys())[0]

            if not pathkey or not roleskey or \
               roleskey not in item:    # not enough info
                yield item; continue
            obj = self.context.unrestrictedTraverse(str(item[pathkey]).lstrip('/'), None)
            if obj is None:             # path doesn't exist
                yield item; continue

            if IRoleManager.providedBy(obj):
                for principal, roles in item[roleskey].items():
                    if roles:
                        obj.manage_addLocalRoles(principal, roles)
                        try:
                            obj.reindexObjectSecurity()
                        except:
                            migration_error.error('Failed to reindexObjectSecurity {}'.format(item['_path']))
            yield item


class LeftOvers(object):
    """ """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'properties-key' in options:
            propertieskeys = options['properties-key'].splitlines()
        else:
            propertieskeys = defaultKeys(options['blueprint'], name, 'properties')
        self.propertieskey = Matcher(*propertieskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            propertieskey = self.propertieskey(*item.keys())[0]

            if not pathkey:
                # not enough info
                yield item; continue

            obj = self.context.unrestrictedTraverse(str(item[pathkey]).lstrip('/'), None)

            if obj is None:
                # path doesn't exist
                yield item; continue

            #Event start & end
            if item.get('start', False):
                tz = pytz.timezone('Europe/Madrid')
                date_with_tz = item['start']
                date_str = date_with_tz[:-6]
                dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                obj.start = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=tz)

            if item.get('end', False):
                tz = pytz.timezone('Europe/Madrid')
                date_with_tz = item['end']
                date_str = date_with_tz[:-6]
                dt = datetime.strptime(date_str, '%Y-%m-%dT%H:%M:%S')
                obj.end = datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, tzinfo=tz)


            # Table contents
            if item.get('tableContents', False):
                obj.table_of_contents = item.get('tableContents')

            # Exclude from nav
            if item.get('excludeFromNav', False):
                obj.exclude_from_nav = item.get('excludeFromNav')

            # Open in new window
            if item.get('obrirfinestra', False):
                obj.open_link_in_new_window = item.get('obrirfinestra')

            # Layout and DefaultPage from unicode to str
            if item.get('_layout', False):
                item['_layout'] = str(item['_layout'])
                obj.layout = str(item['_layout'])

            if item.get('_defaultpage', False):
                obj.setDefaultPage(str(item['_defaultpage']))
                obj.default_view = str(item['_defaultpage'])

            # Local roles inherit
            if item.get('_local_roles_block', False):
                if item['_local_roles_block']:
                    obj.__ac_local_roles_block__ = True

            # Tags
            if item.get('subject', False):
                obj.subject = item['subject']

            # Put creation and modification time on its place
            if item.get('creation_date', False):
                if IDexterityContent.providedBy(item):
                    obj.creation_date = datetime.strptime(item.get('creation_date'), '%Y-%m-%d %H:%M')
                else:
                    obj.creation_date = DateTime(item.get('creation_date'))

            if item.get('modification_date', False):
                if IDexterityContent.providedBy(item):
                    obj.modification_date = datetime.strptime(item.get('modification_date'), '%Y-%m-%d %H:%M')
                else:
                    obj.modification_date = DateTime(item.get('modification_date'))

            if item.get('effective', False):
                if IDexterityContent.providedBy(item):
                    obj.effective_date = datetime.strptime(item.get('effective'), '%Y-%m-%d %H:%M')
                else:
                    obj.effective_date = DateTime(item.get('effective'))

            if item.get('expires', False):
                if IDexterityContent.providedBy(item):
                    obj.expiration_date = datetime.strptime(item.get('expires'), '%Y-%m-%d %H:%M')
                else:
                    obj.expiration_date = DateTime(item.get('expires'))


            yield item


class FieldsCorrector(object):
    """ This corrects the differences (mainly in naming) of the incoming fields
        with the expected ones.
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

        if 'properties-key' in options:
            propertieskeys = options['properties-key'].splitlines()
        else:
            propertieskeys = defaultKeys(options['blueprint'], name, 'properties')
        self.propertieskey = Matcher(*propertieskeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            propertieskey = self.propertieskey(*item.keys())[0]

            if not pathkey:
                # not enough info
                yield item; continue

            obj = self.context.unrestrictedTraverse(str(item[pathkey]).lstrip('/'), None)

            if obj is None:
                # path doesn't exist
                yield item; continue

            # Event specific fields
            if item.get('startDate', False):
                item['start'] = item.get('startDate')
            if item.get('endDate', False):
                item['end'] = item.get('endDate')

            # Dublin core
            if item.get('expirationDate', False):
                item['expires'] = item.get('expirationDate')
            if item.get('effectiveDate', False):
                item['effective'] = item.get('effectiveDate')

            # Intranet UPCnet specific
            if item.get('_type', False):
                if item.get('_type') in [u'Document File', u'PDF File', u'Presentation File', u'Spreadsheet File']:
                    item['_type'] = u'File'

            yield item


class PAMLinker(object):
    """ Links provided translations using plone.app.multilingual. It assumes
        that the object to be linked objects are already in place, so this
        section is intended to be run on second pass migration phase.
    """

    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        if 'path-key' in options:
            pathkeys = options['path-key'].splitlines()
        else:
            pathkeys = defaultKeys(options['blueprint'], name, 'path')
        self.pathkey = Matcher(*pathkeys)

    def __iter__(self):
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]

            if HAS_PAM:
                if not pathkey:
                    # not enough info
                    yield item; continue

                obj = self.context.unrestrictedTraverse(str(item[pathkey]).lstrip('/'), None)

                if obj is None:
                    # path doesn't exist
                    yield item; continue

                if item.get('_translations', False):
                    lang_info = []
                    for lang in item['_translations']:
                        target_obj = self.context.unrestrictedTraverse(str('{}{}'.format(lang, item['_translations'][lang])).lstrip('/'), None)
                        if target_obj and (IBaseObject.providedBy(target_obj) or IDexterityContent.providedBy(target_obj)):
                            lang_info.append((target_obj, lang),)
                    try:
                        self.link_translations(lang_info)
                    except IndexError:
                        continue

            yield item

    def link_translations(self, items):
        """
            Links the translations with the declared items with the form:
            [(obj1, lang1), (obj2, lang2), ...] assuming that the first element
            is the 'canonical' (in PAM there is no such thing).
        """
        # Grab the first item object and get its canonical handler
        canonical = ITranslationManager(items[0][0])


        for obj, language in items:
            if not canonical.has_translation(language):
                canonical.register_translation(language, obj)


class OrderSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        self.every = int(options.get('every', 1000))
        self.previous = previous
        self.context = transmogrifier.context
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.poskey = defaultMatcher(options, 'pos-key', name, 'gopip')
        # Position of items without a position value
        self.default_pos = int(options.get('default-pos', 1000000))

    def __iter__(self):
        # Store positions in a mapping containing an id to position mapping for
        # each parent path {parent_path: {item_id: item_pos}}.
        positions_mapping = {}
        for item in self.previous:
            keys = item.keys()
            pathkey = self.pathkey(*keys)[0]
            poskey = self.poskey(*keys)[0]

            if not (pathkey and poskey):
                yield item
                continue

            item_id = item[pathkey].split('/')[-1]
            parent_path = '/'.join(item[pathkey].split('/')[:-1])
            if parent_path not in positions_mapping:
                positions_mapping[parent_path] = {}
            positions_mapping[parent_path][item_id] = item[poskey]

            yield item

        # Set positions on every parent
        for path, positions in positions_mapping.items():
            # Normalize positions
            ordered_keys = sorted(positions.keys(), key=lambda x: positions[x])
            normalized_positions = {}
            for pos, key in enumerate(ordered_keys):
                normalized_positions[key] = pos

            # TODO: After the new collective.transmogrifier release (>1.4), the
            # utils.py provides a traverse method.
            from collective.transmogrifier.utils import traverse
            parent = traverse(self.context, path)
            # parent = self.context.unrestrictedTraverse(path.lstrip('/'))
            if not parent:
                continue
            # Reorder Collage items
            if parent.portal_type == 'Collage' or parent.portal_type == 'CollageColumn' or parent.portal_type == 'CollageRow':
                for key in normalized_positions.keys():
                    parent.moveObjectToPosition(key, normalized_positions[key])

            parent_base = aq_base(parent)
            if hasattr(parent_base, 'getOrdering'):
                ordering = parent.getOrdering()
                # Only DefaultOrdering of p.folder is supported
                if (not hasattr(ordering, '_order')
                    and not hasattr(ordering, '_pos')):
                    continue
                order = ordering._order()
                pos = ordering._pos()
                order.sort(key=lambda x: normalized_positions.get(x,
                           pos.get(x, self.default_pos)))
                for i, id_ in enumerate(order):
                    pos[id_] = i

                notifyContainerModified(parent)
