from copy import deepcopy
from five import grok
from plone import api
from Products.CMFPlone.interfaces import IPloneSiteRoot
from collective.transmogrifier.transmogrifier import configuration_registry
from collective.transmogrifier.transmogrifier import Transmogrifier
import requests
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
from datetime import datetime,time
import unicodedata
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from zope.interface import classProvides, implements
from transportAdapter import SslTransportAdapter
requests.packages.urllib3.disable_warnings()



class LotusSourceSection(object):
    classProvides(ISectionBlueprint)
    implements(ISection)

    def __init__(self, transmogrifier, name, options, previous):
        from datetime import datetime
        self.previous = previous
        self.options = options
        self.name = name
        self.context = transmogrifier.context
        session = requests.session()
        session.mount('https://', SslTransportAdapter())
        session.verify = False
        enc = sys.getfilesystemencoding()
        USER = options['notes-user']
        PASS = options['notes-pass']
        NAME_URL = self.get_option('name-url')
        NAME_BD = self.get_option('name-bd')
        PATH = self.get_option('bd-path')
        regex_type = self.get_option('regex-type')
        URL = self.get_option('server-url')
        TRAVERSE_PATH = 'upc/'+ NAME_URL +'.nsf/'
        LOGIN_URL = URL  + 'names.nsf?Login'
        PATH1 = '(JerarquiaExportacio)'
        BASE_URL =  URL + PATH 
        MAIN_URL = URL + TRAVERSE_PATH + PATH1 + '?ReadViewEntries&PreFormat&Start=1&Navigate=16&Count=1000000064&SkipNavigate=32783&EndView=1'
        params = {
                    'RedirectTo': URL + 'names.nsf',
                    'Servidor': URL + 'names.nsf',
                    'Username': '%s' % USER,
                    'Password': '%s' % PASS,
                 }

        extra_cookies = {
            'HabCookie': '1',
            'Desti': URL+TRAVERSE_PATH+PATH1,
            'NomUsuari': '%s' % USER,
        }
        session.cookies.update(extra_cookies)
        response = session.post(LOGIN_URL, params, allow_redirects=True)
        cookie = {'Cookie': 'HabCookie=1; Desti=' + URL  + PATH + '; RetornTancar=1; NomUsuari=' + USER + ' LtpaToken=' + session.cookies['LtpaToken']}
        response = session.get(MAIN_URL, headers=cookie)
        
        self.context.plone_log('Iniciando migracion..............')
        root = ElementTree.fromstring(response.content)
        portal = api.portal.get()
        ca= portal['ca']
        biblio = createContentInContainer(ca, 'Folder', NAME_BD , title=NAME_BD, description=u'Biblioteca de importaciones')
        biblio.reindexObject()
        attached = createContentInContainer(biblio, 'Folder', 'annexes' , title='Annexes', description=u'Biblioteca de importaciones')
        attached.exclude_from_nav = True
        attached.reindexObject()
        for count,elem in enumerate(root):
            self.context.plone_log(str(count))
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
                    if counter == 8:
                        autor = e.text,
                    if counter == 10:
                        data_creacio = e.text
                    if counter == 12:
                        data_modif = e.text
            parent=biblio
            #keywords=[]
            if(path == None or path.startswith('/')):
                title_sub = self.generateUnusedId(subject)
                #keywords = [subject]
                child_name= unicodedata.normalize('NFKD', unicode(title_sub)).encode('ascii',errors='ignore')
                parentfolder = self.create_child(parent,'pendiente','Pendiente',autor,data_creacio,data_modif)
                parent = self.create_child(parentfolder,child_name,subject,autor,data_creacio,data_modif)
            else:
                base_path,ide_obj= os.path.split(path)
                #keywords = base_path.split("/")
                for elem in base_path.split("/"):
                    if len(elem) >1:
                        child_name = unicodedata.normalize('NFKD', unicode(elem)).encode('ascii',errors='ignore')
                        parent = self.create_child(parent,child_name,elem,autor,data_creacio,data_modif)
            response2 = session.get(URL + TRAVERSE_PATH + PATH + ide +'?OpenDocument&ExpandSection=1,10,11,1.1,1.1.2,12,1.2,13,1.3,14,1.4,15,1.5,16,1.6,17,1.7,18,1.8,19,1.9,2,20,21,2.1,2.1.1,2.1.2,22,2.2,23,2.3,24,2.4,25,2.5,26,2.6,27,2.7,28,2.8,29,2.9,3,30,31,3.1,32,3.2,33,3.3,34,3.4,35,4,4.1,4.3,4.4,4.5,5,6,7,8,9', headers=cookie)
            htmlContent = response2.content.decode('iso-8859-1').encode('utf-8')
            #Cambiar dependiendo de la vista del documento, primero vista sencilla, segundo vista con cabecera grande
            if regex_type =='1':
                tinyContent =   re.search(r'^(.*?)(<script.*/script>)(.*<form.*?>)(.*?<table.*?/table>)(.*?)(<center.*?<hr.*?)<a\s*href="\/upc\/'+NAME_URL +'\.nsf\/\(\$All\)\?OpenView">.*$', htmlContent, re.DOTALL | re.MULTILINE).groups()[4]
            else:
                tinyContent = re.search(r'^(.*?)(.*<form.*?>)(.*?<table.*?<table)(.*?/table>)(.*?<table.*?/table>)?(.*?/table>)(.*?)<hr.*$', htmlContent, re.DOTALL | re.MULTILINE).groups()[6]
            title_subj = self.generateUnusedId(subject)
            objectNote = createContentInContainer(parent, 'Document', title_subj,title=title_subj)
            imatgeSrc = re.findall(r'<img[^>]+src=\"([^\"]+)\"', tinyContent)
            imatgeSrc = [a for a in imatgeSrc if '/upc' in a]
            numimage = 1

            for obj in imatgeSrc:
                try:
                    imatge = session.get(URL + obj, headers=cookie)
                    name_image=unicode('Image' + ide +str(numimage))
                    replacedName = '/'.join((attached.absolute_url() + '/image'+ide.lower() + str(numimage)).split('/')[5:])
                    
                    imatge_file = NamedBlobImage(
                        data = imatge.content,
                        contentType = 'image/gif',
                        filename =  name_image
                        )
                    imageObject = createContentInContainer(attached,'Image', title= name_image,image=imatge_file)
                    tinyContent = tinyContent.replace(obj, replacedName)
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
                    # fake the same filename in folder object...
                    contents = objectNote.contentIds()
                    fich = obj.split('/')[-1]
                    extension = fich.split('.')[-1].lower()
                    nom_fich = '.'.join(fich.split('.')[:-1])
                    file_name = nom_fich.decode('iso-8859-1').encode('utf-8')
                    normalizedName = getToolByName(self.context, 'plone_utils').normalizeString(file_name)
                    normalizedName = self.calculaNom(contents, normalizedName)
                    attch_name=unicode(normalizedName+'.'+extension)
                    file_obj = api.content.create(                          
                                    attached, 'File', 
                                    id = attch_name,                             
                                    title = attch_name, 
                                    safe_id = True
                                    )
                    replacedObjName = attached.absolute_url() +'/'+ normalizedName+'.'+extension
                    
                    # OpenOffice files internally are saved as ZIP files, we must force metadata...
                    
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
                    tinyContent = tinyContent.replace(obj, replacedObjName)
                    file_obj.exclude_from_nav = True
                    file_obj.creation_date = datetime.strptime(data_creacio, '%m/%d/%Y %I:%M:%S %p')
                    file_obj.creators = autor
                    file_obj.reindexObject()
                    file_obj.modification_date = datetime.strptime(data_modif, '%m/%d/%Y %I:%M:%S %p')
                except:
                    pass
            # remove section links...
            removeSections = re.findall(r'(<a[^>]+target="_self">.*?</a>)', tinyContent)
            for obj in removeSections:
                tinyContent = tinyContent.replace(obj, "")
            # Create modified HTML content with new image/file paths
            objectNote.text= RichTextValue(tinyContent,'text/html', 'text/x-html-safe', 'utf-8')
            #parent.setDefaultPage(objectNote.id)
            objectNote.creation_date = datetime.strptime(data_creacio, '%m/%d/%Y %I:%M:%S %p')
            objectNote.title = subject
            #objectNote.subject = keywords
            objectNote.creators = autor
            objectNote.reindexObject()
            objectNote.modification_date = datetime.strptime(data_modif, '%m/%d/%Y %I:%M:%S %p')
        self.context.plone_log('Archivos migrados: '+str(count))
        self.context.plone_log('Finalizando migracion...................')

    def create_child(self, parent_folder,path_name,folder_name,autor,data_creacio,data_modif):
        normalizedd =  getToolByName(self.context, 'plone_utils').normalizeString(path_name)
        try:
            obj_created = parent_folder[normalizedd]
        except:
            obj_created = False
        
        if not obj_created:
            obj_created = createContentInContainer(parent_folder, 'Folder', normalizedd, title=normalizedd)
            obj_created.creation_date = datetime.strptime(data_creacio, '%m/%d/%Y %I:%M:%S %p')
            obj_created.title = folder_name
            obj_created.creators = autor
            obj_created.reindexObject()
            obj_created.modification_date = datetime.strptime(data_modif, '%m/%d/%Y %I:%M:%S %p')  
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

    def get_option(self, name):
        """Get an option from the request if available and fallback to the
        transmogrifier config.
        """
        value = self.options.get(name)
        if isinstance(value, unicode):
            value = value.encode('utf8')
        return value

    def __iter__(self):
        for item in self.previous:
            yield item
        
        
         
