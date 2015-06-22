from copy import deepcopy
from five import grok
from plone import api
from Products.CMFPlone.interfaces import IPloneSiteRoot
from collective.transmogrifier.transmogrifier import configuration_registry
from collective.transmogrifier.transmogrifier import Transmogrifier
import requests
import logging
from xml.etree import ElementTree
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import SubElement
import sys, os
from unidecode import unidecode
from plone.dexterity.utils import createContentInContainer
from plone.namedfile.file import NamedBlobImage,NamedBlobFile
import re
import logging
from  Products.CMFCore.utils  import  getToolByName 
from Products.CMFPlone.utils import _createObjectByType
from plone.app.textfield.value import RichTextValue
from Products.CMFPlone.interfaces import IBrowserDefault
from os.path import isfile, join, basename
from urlparse import urlparse
import urllib2
from Products.CMFPlone.utils import safe_unicode


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
NOTES_USER = "desenvolupament.eatenea"
NOTES_PASS = "Notesnotes1"

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

class LotusMigration(grok.View):
    grok.name("lotus_migration")
    grok.context(IPloneSiteRoot)
    grok.template("lotus_migration")
    grok.require('cmf.ManagePortal')

    def update(self):
        from datetime import datetime
        session = requests.session()
        
        enc = sys.getfilesystemencoding()
        name_bd = u'Administracio SAP. Usuaris'
        #name_bd = u"CS3 Manual d-Explotacio"
        #name_bd = u"CS3 - LCFME"
        NAME_URL = 'SAP-Admin-usuaris'
        URL = 'https://mola.upc.edu'
        LOGIN_URL = 'https://mola.upc.edu/names.nsf?Login'
        PATH1 = '(JerarquiaExportacio)'
        #PATH = 'f29e475440da49cbc1257e5b0037c03b' #CS3 -1
        #PATH = '238c362a703f0ac1c1257e5b00393d01/' #CS3
        PATH = '1447c01c19761c97c1257e5b00389867/' #SAP
        BASE_URL = 'https://mola.upc.edu/%s' % PATH
        #TRAVERSE_PATH = '/upc/CS3Explotacio.nsf/'
        #TRAVERSE_PATH = '/upc/LCFME.nsf/'
        TRAVERSE_PATH = '/upc/SAP-Admin-usuaris.nsf/'
        #MAIN_URL = 'https://mola.upc.edu/upc/CS3Explotacio.nsf/%28JerarquiaExportacio%29?ReadViewEntries&PreFormat&Start=1&Navigate=16&Count=1000000064&SkipNavigate=32783&EndView=1'
        MAIN_URL = URL + TRAVERSE_PATH + PATH1 + '?ReadViewEntries&PreFormat&Start=1&Navigate=16&Count=1000000064&SkipNavigate=32783&EndView=1'
        
        logging.basicConfig(format='%(asctime)s %(message)s',
                            datefmt='%m/%d/%Y %I:%M:%S %p',
                            filename='import-ADS.log',
                            level=logging.DEBUG)

        params = {
                    'RedirectTo': 'https://mola.upc.edu/names.nsf',
                    'Servidor': 'https://mola.upc.edu/names.nsf',
                    'Username': '%s' % NOTES_USER,
                    'Password': '%s' % NOTES_PASS,
                 }

        extra_cookies = {
            'HabCookie': '1',
            'Desti': URL+TRAVERSE_PATH+PATH1,
            'NomUsuari': '%s' % NOTES_USER,
            #'LtpaToken': 'AAECAzU1NzU3QUEyNTU3NThGQkFDTj1EZXNlbnZvbHVwYW1lbnQgZUF0ZW5lYS9PPVVQQ6pYxXmiD7LA73OUdhLhNMJ8EIsN'
        }
        
        session.cookies.update(extra_cookies)
        response = session.post(LOGIN_URL, params, allow_redirects=True)
        cookie = {'Cookie': 'HabCookie=1; Desti=' + URL + '/' + PATH + '; RetornTancar=1; NomUsuari=' + NOTES_USER + ' LtpaToken=' + session.cookies['LtpaToken']}
        response = requests.get(MAIN_URL, headers=cookie)
        
        f = open('migrate_lotus.log', 'a')  # log file
        
        root = ElementTree.fromstring(response.content)
        portal = api.portal.get()
        ca= portal['ca']
        biblio = createContentInContainer(ca, 'Folder', name_bd, title=name_bd, description=u'Biblioteca de importaciones')
        biblio.reindexObject()
        for count,elem in enumerate(root):
            attribute = elem.attrib
            position = attribute['position']
            noteid = attribute['noteid']
            ide = attribute['unid']
            for counter,e in enumerate(elem.iter()):
                if e is not elem:
                    if counter==2:
                        path=e.text
                    if counter==4:
                        subject = e.text
            parent=biblio
            if(path ==None):
                child_name= getToolByName(self.context, 'plone_utils').normalizeString(subject)
                parent = self.create_child(parent,child_name,subject)
            else:
                base_path,ide_obj= os.path.split(path)
                for element in base_path.split("/"):
                    if len(element) >1:
                        child_name = getToolByName(self.context, 'plone_utils').normalizeString(element)
                        print 'childid:'+ child_name
                        parent = self.create_child(parent,child_name,element)
                        print parent
            response2 = requests.get(URL + TRAVERSE_PATH + PATH + ide +'?OpenDocument&ExpandSection=1#_Section1', headers=cookie)
            htmlContent = response2.content.decode('iso-8859-1').encode('utf-8')
            tinyContent =  re.search(r'^(.*?)(<script.*/script>)(.*<form.*?>)(.*?<table.*?/table>)(.*?)(.*?)(.*?)<a\s*href="\/upc\/'+NAME_URL +'\.nsf\/\(\$All\)\?OpenView">.*$', htmlContent, re.DOTALL | re.MULTILINE).groups()[6]
            #import ipdb;ipdb.set_trace()
            #autor =re.search(r'^(.*?)(<tr.*?/tr>)(<tr.*?/tr>)(<tr.*?/tr>)(<tr.*?/tr>).*$', obje, re.DOTALL | re.MULTILINE).groups()[1]
            child = getToolByName(self.context, 'plone_utils').normalizeString(subject)
            objectNote = createContentInContainer(parent, 'Document', child,title=subject)

            imatgeSrc = re.findall(r'<img[^>]+src=\"([^\"]+)\"', tinyContent)
            imatgeSrc = [a for a in imatgeSrc if '/upc' in a]
            numimage = 1

            for obj in imatgeSrc:
                try:
                    imatge = session.get(URL + obj, headers=cookie)
                    name_image=unicode('Image' + str(numimage))
                
                    replacedName = '/'.join((objectNote.absolute_url() + '/image' + str(numimage)).split('/')[5:])
                    tinyContent = tinyContent.replace(obj, replacedName)
                
                    imatge_file = NamedBlobImage(
                        data = imatge.content,
                        contentType = 'image/gif',
                        filename =  name_image
                        )
                    imageObject = createContentInContainer(parent,'Image', title= name_image,image=imatge_file)
                    imageObject.exclude_from_nav = True
                    imageObject.reindexObject()
                    numimage = numimage + 1

                except:
                    pass
            # Import Files of the object
            attachSrc = re.findall(r'<a[^>]+href=\"([^\"]+)\"', htmlContent)
            attachSrc = [a for a in attachSrc if '$FILE' in a]
            for obj in attachSrc:
                try:
                    fileNote = session.get(URL + obj, headers=cookie,stream=True)
                    file_name = basename(urlparse(urllib2.unquote(obj)).path).decode('iso-8859-1').encode('utf-8')
                    normalizedName = getToolByName(self.context, 'plone_utils').normalizeString(file_name.split('.')[0])
                    # fake the same filename in folder object...
                    contents = objectNote.contentIds()
                    extension = obj.split('.')[-1:][0]
                    normalizedName = self.calculaNom(contents, normalizedName)
                    attch_name=unicode(normalizedName+'.'+extension)
                    file_obj = api.content.create(                          
                                    parent, 'File', 
                                    id = attch_name,                             
                                    title = attch_name, 
                                    safe_id = True
                                    )
                    tinyContent = tinyContent.replace(obj, normalizedName+'.'+extension)
                    # OpenOffice files internally are saved as ZIP files, we must force metadata...
                    
                    print extension
                    if extension == 'odt':
                        file_format='application/vnd.oasis.opendocument.text'
                    if extension == 'ods':
                        file_format='application/vnd.oasis.opendocument.spreadsheet'
                    if extension == 'odp':
                        file_format='application/vnd.oasis.opendocument.presentation'
                    if extension == 'odg':
                        file_format='application/vnd.oasis.opendocument.graphics'
                    if extension == 'doc':
                        file_format='application/msword'
                    if extension == 'docx':
                        file_format='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    if extension == 'xls':
                        file_format='application/vnd.ms-excel'
                    if extension == 'xlsx':
                        file_format='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    if extension == 'ppt':
                        file_format='application/vnd.ms-powerpoint'
                    if extension == 'pptx':
                        file_format='application/vnd.openxmlformats-officedocument.presentationml.presentation'
                    if extension == 'bmp':
                        file_format='image/bmp'
                    if extension == 'pdf':
                        file_format='application/pdf'
                    if extension == 'exe' or extension =='msi':
                        file_format = 'application/octet-stream'
                    if extension == 'zip':
                        file_format = 'application/zip'
                    if extension == 'txt' or extension =='sh':
                        file_format = 'text/plain'    
                    notes_file = NamedBlobFile(
                        data = fileNote.raw.data,
                        contentType = file_format,
                        filename = attch_name 
                        )
                    file_obj.file= notes_file
                    file_obj.exclude_from_nav = True
                    file_obj.reindexObject()
                except:
                    pass
            # remove section links...
            removeSections = re.findall(r'(<a[^>]+target="_self">.*?</a>)', tinyContent)
            for obj in removeSections:
                tinyContent = tinyContent.replace(obj, "")
            # Create modified HTML content with new image/file paths
            objectNote.text= RichTextValue(tinyContent,'text/html', 'text/x-html-safe', 'utf-8')
            
            parent.setDefaultPage(objectNote.id)
            objectNote.exclude_from_nav = True
            objectNote.reindexObject()
            
        f.close()

    def create_child(self, parent_folder,path_name,folder_name):
       
        try:
            obj_created = parent_folder[path_name]
        except:
            obj_created = False
        
        if not obj_created:
            obj_created = createContentInContainer(parent_folder, 'Folder', folder_name, id=folder_name,title=folder_name)
            obj_created.reindexObject()
        return obj_created 

    def get_path(self, path):
        return "-".join(unidecode(path.replace("'","")).lower().split())

    def calculaNom(self, ids, nom_normalitzat, i=0):
        """
        """
        if i != 0:
            nom = nom_normalitzat + str(i)
        else:
            nom = nom_normalitzat

        if nom not in ids:
            return nom
        else:
            return self.calculaNom(ids, nom_normalitzat, i + 1)

    def generateUnusedId(self, title):
        """
        """
        plone_utils = getToolByName(self.context, 'plone_utils')
        id = plone_utils.normalizeString(title)
        if id in self.context.contentIds():
            number = 2
            while '%s-%i' % (id, number) in self.context.contentIds():
                number += 1
            id = '%s-%i' % (id, number)
        return id

    def createNotesObject(self, type, folder, title):
        """
        """
        id = self.generateUnusedId(title)
        _createObjectByType(type, folder, id)
        obj = folder[id]

        return obj
        
        
         

