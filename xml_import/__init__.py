# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.core.files import File
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from lxml import etree
from datetime import datetime
from os import path, makedirs, rename
from shutil import rmtree
import logging
import zipfile

log = logging.getLogger(__name__)
tz = timezone.utc


class ElementWrapper(object):
    xml = None
    data_name = None

    def __init__(self, xml, data_name):
        self.xml = xml
        self.data_name = data_name


class ImportXML(object):
    _data_map_scheme = {
        'XMLTagName.childXMLTagName': {
            '!model': 'app.Model',

            # data_block begin:
            'text': '_model_field',
            'files': {'_XMLAttribute': '_model_field'},
            'attributes': {'_XMLAttribute': '_model_field'},
            'foreign_keys': {'_XMLAttribute': ('_model_field', '_target_XMLTagName')},
            # data_block end

            'children_fields': {
                '_XMLTagName': {
                    # data_block
                }
            },

            # for children models:
            '!children_key_field': '_child_model_field',
        }}
    _data_map_example = {
        'Section': {
            'model': 'catalog.Section',
            'attributes': {'Name': 'title'},
            'children_fields': {
                'Description': {
                    'text': 'description'
                }
            }
        },
        'Product': {
            'model': 'catalog.Product',
            'attributes': {'Name': 'title'},
            'children_key_field': 'product',
        },
        'Product.Photo': {
            'model': 'catalog.Photo',
            'files': {'FilePath': 'file'}
        }
    }

    id_field = 'xml_id'
    """str: поле БД используемое для связи с xml"""
    id_xml_attr = 'Id'
    """str: аттрибут XML используемый для связи с БД"""
    data_map = None
    """dict: схемы данных"""
    key_map = None
    """dict: словари xml_id => site_id"""
    keys_get_lists = None
    """dict: списки xml_id для обновления key_map из БД"""
    keys_del_lists = None
    """dict: списки xml_id для удаления записей из БД"""
    unresolved_keys = None
    """dict: списки site_id для обновления в БД их внешних ключей"""
    create_without_xml_id = None
    """dict: списки записей для создания, которые не имеют своих xml_id"""
    files_lists = None
    """dict: списки записей для сохранения файлов"""
    flush = None
    files_dir = None
    exec_time = None
    raise_unresolved_errors = True

    def __init__(self, flush=False):
        if not hasattr(settings, 'IMPORTXML_DATA_MAP'):
            raise ImproperlyConfigured('отсуствует settings.IMPORTXML_DATA_MAP')
        self.data_map = settings.IMPORTXML_DATA_MAP
        self.key_map = {}
        for data_name, data in self.data_map.items():
            self.key_map[data_name] = {}
        self.keys_get_lists = {}
        self.keys_del_lists = {}
        self.unresolved_keys = {}
        self.create_without_xml_id = {}
        self.files_lists = {}
        self.post_save_models = {}
        self.flush = flush

    def append_keys(self, data_name, keys, key_list=None):
        """Добавляет запись(и) в списки сгруппированные по data_name"""
        if key_list is None:
            key_list = self.keys_get_lists

        if data_name not in key_list:
            key_list[data_name] = []
        if isinstance(keys, list):
            key_list[data_name] += keys
        else:
            key_list[data_name].append(keys)

    def clean_datetime_field(self, value):
        """Конвертирует строку в datetime.datetime"""
        return tz.localize(parse_datetime(value))

    def delete_keys(self):
        """Удаляет записи из БД из очереди ImportXML.keys_del_lists"""
        for data_name, keys in self.keys_del_lists.items():
            model = self.get_model(data_name)
            model.objects.filter(**{'%s__in' % self.id_field: keys}).delete()
            del self.keys_del_lists[data_name]

    def get_data_map(self, data_name):
        """Возвращает объект из ImportXML.data_map либо вызывает исключение"""
        data_map = self.data_map.get(data_name)
        if data_map:
            return data_map
        else:
            # @TODO: log error && raise error
            pass

    def get_model(self, data_name):
        """Возвращает модель по её ключу в ImportXML.data_map"""
        data_map = self.get_data_map(data_name)
        return apps.get_model(*data_map['model'].split('.'))

    def get_xml_id(self, xml):
        """Возвращает xml_id с инстанса etree._Element"""
        return xml.attrib[self.id_xml_attr]

    def localize_keys(self, data):
        """
        Обновляет data, заменяя различные xml_id из foreign_keys на site_id в fields, если объект существует в БД,
        если же нет – добавялет запись в ImportXML.unresolved_keys для последующего получения site_id из БД

        Args:
            data (dict): массив, созданный в ImportXML.process_item
        """
        if 'foreign_keys' in data:
            for model_property, (xml_id, target_data_name) in data['foreign_keys'].items():
                if target_data_name not in self.key_map:
                    raise ImproperlyConfigured('отсуствует %s в ImportXML.data_map' % target_data_name)
                if xml_id == '':
                    data['fields'][model_property] = None
                elif xml_id in self.key_map[target_data_name]:
                    data['fields'][model_property] = self.key_map[target_data_name][xml_id]
                else:
                    self.append_keys(target_data_name, [xml_id])
                    if data['data_name'] not in self.unresolved_keys:
                        self.unresolved_keys[data['data_name']] = {}
                    if target_data_name not in self.unresolved_keys[data['data_name']]:
                        self.unresolved_keys[data['data_name']][target_data_name] = {}
                    if model_property not in self.unresolved_keys[data['data_name']][target_data_name]:
                        self.unresolved_keys[data['data_name']][target_data_name][model_property] = {}
                    if xml_id not in self.unresolved_keys[data['data_name']][target_data_name][model_property]:
                        self.unresolved_keys[data['data_name']][target_data_name][model_property][xml_id] = []
                    # self.unresolved_keys[ContractorLegal][ContractorRegion][region_id][123] = ['1', '2', '3']
                    self.unresolved_keys[data['data_name']][target_data_name][model_property][xml_id].append(data['xml_id'])

    def process_item(self, element, data_list, parent=None):
        """
        Обрабатывает один элемент из xml, создавая словарь item_data, добавляемый в data_list

        Args:
            element (ElementWrapper, etree._Element): либо xml элемент, либо содержащий его ElementWrapper
            data_list (list): список, в который добавляется item_data
            parent (ElementWrapper): родительский элемент, если есть
        """
        if not isinstance(element, ElementWrapper):
            element = ElementWrapper(element, element.tag)

        if 'DoRemove' in element.xml.attrib and element.xml.attrib['DoRemove'] == 'true':
            self.append_keys(element.data_name, self.get_xml_id(element.xml), self.keys_del_lists)
        else:
            data_map = self.get_data_map(element.data_name)
            item_data = {
                'data_name': element.data_name,
                'xml_id': self.get_xml_id(element.xml),
                'fields': {},
                'foreign_keys': {}}
            self.update_item_data(element.xml, data_map, item_data)
            if parent:
                parent_map = self.get_data_map(parent.data_name)
                item_data['foreign_keys'][parent_map['children_key_field']] = (
                    self.get_xml_id(parent.xml), parent.data_name)

            for child in element.xml.getchildren():
                child = ElementWrapper(child, '%s.%s' % (element.data_name, child.tag))
                if 'children_fields' in data_map and child.xml.tag in data_map['children_fields']:
                    self.update_item_data(child.xml, data_map['children_fields'][child.xml.tag], item_data)
                elif child.data_name in self.data_map:
                    self.process_item(child, data_list, element)

            if 'without_id' in data_map:
                self.append_keys(element.data_name, item_data, self.create_without_xml_id)
            else:
                self.append_keys(element.data_name, self.get_xml_id(element.xml))
                model = self.get_model(element.data_name)
                if hasattr(model, 'post_save_callback'):
                    self.append_keys(model, item_data['xml_id'], self.post_save_models)
                data_list.append(item_data)

    def process_file(self, file_path):
        """Создает объект XML из файла и запускает парсер ImportXML.process_xml"""
        with open(file_path, 'r') as f:
            xml = etree.fromstring(f.read())
            with transaction.atomic():
                self.process_xml(xml)

    def process_xml(self, xml):
        """Обрабатывает корневой XML элемент, создавая / изменяя / удаляя записи из БД"""
        self.exec_time = datetime.now()
        data_list = []
        create_items = {}
        update_items = {}

        if ('Flush' in xml.attrib and xml.attrib['Flush'] == 'true') or self.flush:
            for data_name, data in self.data_map.items():
                model = self.get_model(data_name)
                model.objects.all().delete()

        # собирается список данных из xml
        for item in xml.getchildren():
            self.process_item(item, data_list)

        # удаляются записиси из БД
        log.info('delete keys..')
        self.delete_keys()
        self.update_keys()

        # распределяется список данных на создание и обновление
        for item in data_list:
            target = update_items if item['xml_id'] in self.key_map[item['data_name']] else create_items
            if item['data_name'] not in target:
                target[item['data_name']] = []
            target[item['data_name']].append(item)

        # создаются новые записи
        log.info('create items..')
        for data_name, items in create_items.items():
            model = self.get_model(data_name)
            create_list, keys_list = [], []
            for item in items:
                self.localize_keys(item)
                keys_list.append(item['xml_id'])
                item['fields'][self.id_field] = item['xml_id']
                create_list.append(model(**item['fields']))
            self.append_keys(data_name, keys_list)
            log.info('create %s items..' % model.__name__)
            model.objects.bulk_create(create_list)
        self.update_keys()

        # обновление ссылок на только созданные объекты
        log.info('update unresolved keys..')
        for data_name, _data_name in self.unresolved_keys.items():
            model = self.get_model(data_name)
            for target_data_name, _target_data_name in _data_name.items():
                for model_property, _model_property in _target_data_name.items():
                    for xml_id, items_xml_id in _model_property.items():
                        try:
                            field_val = self.key_map[target_data_name][xml_id]
                            model.objects.filter(**{'%s__in' % self.id_field: items_xml_id}).update(
                                **{model_property: field_val})
                        except KeyError as e:
                            if self.raise_unresolved_errors:
                                raise e

        # обновляются существующие записи
        log.info('update items..')
        for data_name, items in update_items.items():
            model = self.get_model(data_name)
            log.info('update %s items..' % model.__name__)
            for item in items:
                self.localize_keys(item)
                model.objects.filter(**{self.id_field: item['xml_id']}).update(**item['fields'])

        # сохраняются файлы
        log.info('saving files..')
        for data_name, files_list in self.files_lists.items():
            model = self.get_model(data_name)
            log.info('saving %s files..' % model.__name__)
            for xml_id, item_files in files_list:
                instance = model.objects.get(**{self.id_field: xml_id})
                for model_property, file_name in item_files.items():
                    getattr(instance, model_property).save(file_name, File(open(path.join(self.files_dir, file_name))))

        log.info('post save callbacks..')
        for model, items in self.post_save_models.items():
            model.post_save_callback(items)

        # создаются объекты без собственных xml_id
        log.info('create items without xml_id..')
        for data_name, items in self.create_without_xml_id.items():
            model = self.get_model(data_name)
            data_map = self.get_data_map(data_name)
            log.info('create %s items..' % model.__name__)
            create_list, delete_list = [], []
            for item in items:
                self.localize_keys(item)
                if 'delete_by_field' in data_map:
                    if item['fields'][data_map['delete_by_field']] not in delete_list:
                        delete_list.append(item['fields'][data_map['delete_by_field']])
                create_list.append(model(**item['fields']))
            if len(delete_list) > 0:
                model.objects.filter(**{'%s__in' % data_map['delete_by_field']: delete_list}).delete()
            model.objects.bulk_create(create_list)

        log.info('exec time is: %s' % (datetime.now() - self.exec_time))

    def update_keys(self):
        """Обновляет ImportXML.key_map записями из очереди ImportXML.keys_get_lists"""
        for data_name, keys in self.keys_get_lists.items():
            model = self.get_model(data_name)
            ids = {unicode(x[self.id_field]): x['id'] for x in model.objects.filter(
                **{'%s__in' % self.id_field: keys}).values('id', self.id_field)}
            self.key_map[data_name].update(ids)
            self.keys_get_lists[data_name] = []

    def update_item_data(self, xml, data_map, data):
        """
        Обновляет data данными из XML элемента

        Args:
            xml (etree._Element): источник данных
            data_map (dict): словарь со схемой данных
            data (dict): результирующий словарь

        """
        if 'attributes' in data_map:
            for xml_key, model_property in data_map['attributes'].items():
                if xml_key in xml.attrib:
                    value = xml.attrib[xml_key]
                    if 'clean_fields' in data_map and model_property in data_map['clean_fields']:
                        func = data_map['clean_fields'][model_property]
                        if isinstance(func, (str, unicode)):
                            func = getattr(self, func)
                        value = func(value)
                    data['fields'][model_property] = value

        if 'text' in data_map and xml.text:
            data['fields'][data_map['text']] = xml.text

        if 'foreign_keys' in data_map:
            for xml_key, (model_property, target_data_name) in data_map['foreign_keys'].items():
                if xml_key in xml.attrib:
                    # заполнить xml foreign_key, который потом заменить на id из бд сайта
                    data['foreign_keys'][model_property] = (xml.attrib[xml_key], target_data_name)

        if 'files' in data_map:
            item_files = {}
            for xml_key, model_property in data_map['files'].items():
                if xml_key in xml.attrib:
                    item_files[model_property] = xml.attrib[xml_key]
            if item_files:
                self.append_keys(data['data_name'], (data['xml_id'], item_files), self.files_lists)


def import_zip(file_path):
    zf = zipfile.ZipFile(file_path, 'r')
    temp_dir = path.join(settings.MEDIA_ROOT, 'import_zip')
    if path.exists(temp_dir):
        rmtree(temp_dir)
    makedirs(temp_dir)
    import_files = []
    for file_name in zf.namelist():
        data = zf.read(file_name)
        temp_path = path.join(temp_dir, file_name)
        new_file = open(temp_path, 'w+')
        new_file.write(data)
        new_file.close()
        if file_name.split('.')[-1] == 'xml':
            import_files.append(temp_path)
    import_instance = ImportXML()
    import_instance.files_dir = temp_dir
    for f in import_files:
        import_instance.process_file(f)
    rmtree(temp_dir)
    cache.clear()
