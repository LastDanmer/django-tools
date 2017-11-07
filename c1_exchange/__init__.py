# -*- coding: utf-8 -*-
import copy
import logging
import os
from collections import OrderedDict
from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.core.files import File
from django.utils.log import DEFAULT_LOGGING
from lxml import etree
from pytils import translit
from .. import get_dict_from_lxml
from .. import get_tree_from_lxml
from .. import remove_xml_namespace

'''
C1_EXCHANGE_MODULE = 'catalog.c1_exchange'
C1_MODELS_ORDER = 'catalog.Order'
C1_MODELS_PRODUCT = 'catalog.Product'
C1_MODELS_PROPERTY = 'catalog.ProductProperty'
C1_MODELS_PROPERTY_VALUE = 'catalog.ProductPropertyValue'
C1_MODELS_SECTION = 'catalog.Section'
C1_IMAGE_MAIN = 'main_image'
C1_IMAGE_MANAGER = 'images'
C1_IMAGE_POSITION = 'position'
'''
log = logging.getLogger('c1_exchange')


def append_data(source, target):
    for key, val in source.iteritems():
        if isinstance(val, list):
            for item in val:
                xml_item = etree.Element(key)
                append_data(item, xml_item)
                target.append(xml_item)
        elif isinstance(val, (dict, OrderedDict)):
            xml_item = etree.Element(key)
            append_data(val, xml_item)
            target.append(xml_item)
        else:
            xml_item = etree.Element(key)
            xml_item.text = val
            target.append(xml_item)


def append_logger(conf=DEFAULT_LOGGING, base_dir=None):
    conf = copy.deepcopy(conf)
    if 'file_rotation' not in conf['handlers']:
        if not base_dir:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if 'formatters' not in conf:
            conf['formatters'] = {}
        conf['formatters']['1c_exchnage'] = {
            'format': '%(asctime)s %(levelname)s : %(message)s'
        }
        conf['handlers']['file_rotation'] = {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': '1c_exchnage',
            'filename': os.path.join(base_dir, 'log.txt'),
            'maxBytes': 1048576,
            'backupCount': 1
        }
    conf['loggers']['c1_exchange'] = {
        'level': 'INFO',
        'handlers': ['file_rotation', 'console']
    }
    return conf


class C1Exchange(object):
    catalog_only_changes = True
    exec_time = None
    first_image_delete = True
    image_main = None
    image_manager = None
    image_position = None
    model_order = None
    model_product = None
    model_property = None
    model_property_value = None
    model_section = None
    property_values = []
    verbose = False
    xml_sections = {}
    xml_products = {}
    xml_props = {}

    def __init__(self, verbose=False):
        if hasattr(settings, 'C1_MODELS_ORDER'):
            self.model_order = apps.get_model(*getattr(settings, 'C1_MODELS_ORDER').split('.'))

        if hasattr(settings, 'C1_MODELS_PRODUCT'):
            self.model_product = apps.get_model(*getattr(settings, 'C1_MODELS_PRODUCT').split('.'))

        if hasattr(settings, 'C1_MODELS_PROPERTY'):
            self.model_property = apps.get_model(*getattr(settings, 'C1_MODELS_PROPERTY').split('.'))

        if hasattr(settings, 'C1_MODELS_PROPERTY_VALUE'):
            self.model_property_value = apps.get_model(*getattr(settings, 'C1_MODELS_PROPERTY_VALUE').split('.'))

        if hasattr(settings, 'C1_MODELS_SECTION'):
            self.model_section = apps.get_model(*getattr(settings, 'C1_MODELS_SECTION').split('.'))

        if hasattr(settings, 'C1_IMAGE_MAIN'):
            self.image_main = getattr(settings, 'C1_IMAGE_MAIN')

        if hasattr(settings, 'C1_IMAGE_MANAGER'):
            self.image_manager = getattr(settings, 'C1_IMAGE_MANAGER')

        if hasattr(settings, 'C1_IMAGE_POSITION'):
            self.image_position = getattr(settings, 'C1_IMAGE_POSITION')
        self.verbose = verbose

    def import_item_data(self, data_list, xml_list, model, resolve_xml_id=True):
        log.info('import item data for %s' % model.__name__)
        to_insert = []
        updated_count = 0
        for item_data in data_list:
            if not item_data:
                continue
            if resolve_xml_id and 'xml_id' in item_data and item_data['xml_id'] in xml_list:
                updated_count += 1
                model.objects.filter(
                    pk=xml_list[item_data['xml_id']]).update(**item_data)
            else:
                to_insert.append(model(**item_data))
        if updated_count > 0:
            log.info('updated: %i' % updated_count)
        if len(to_insert) > 0:
            model.objects.bulk_create(to_insert)
            log.info('created: %i' % len(to_insert))
            if resolve_xml_id:
                xml_list = {xml: pk for pk, xml in model.objects.values_list('pk', 'xml_id')}
        return xml_list if resolve_xml_id else None

    def import_offers(self, xml_obj):
        if not self.model_product:
            return False
        log.info('import offers')
        if not self.xml_products:
            self.xml_products = {xml: pk for pk, xml in self.model_product.objects.values_list('pk', 'xml_id')}
        for xml_child in xml_obj.getchildren():
            offer_dict = get_dict_from_lxml(xml_child)
            price = False
            if u'Цены' in offer_dict and u'Цена' in offer_dict[u'Цены']:
                price = offer_dict[u'Цены'][u'Цена'][u'ЦенаЗаЕдиницу']
            if price and offer_dict[u'Ид'] in self.xml_products:
                self.model_product.objects.filter(
                    pk=self.xml_products[offer_dict[u'Ид']]).update(price=price)
        log.info('import offers time: %s' % (datetime.now() - self.exec_time))
        self.exec_time = datetime.now()
        return True

    def import_products(self, xml_obj):
        if not self.model_product:
            return False
        log.info('import products')
        data_list = []
        images_dict = {}
        self.xml_products = {xml: pk for pk, xml in self.model_product.objects.values_list('pk', 'xml_id')}
        for xml_child in xml_obj.getchildren():
            product = get_dict_from_lxml(xml_child)
            item_data = {
                'xml_id': product[u'Ид'],
                'slug': translit.slugify(product[u'Наименование']),
                'title': product[u'Наименование']}
            if u'Группы' in product and u'Ид' in product[u'Группы']\
                    and product[u'Группы'][u'Ид'] in self.xml_sections:
                item_data['section_id'] = self.xml_sections[product[u'Группы'][u'Ид']]
            else:
                continue
            if u'Артикул' in product:
                item_data['article'] = product[u'Артикул']
            if u'Описание' in product:
                item_data['description'] = product[u'Описание']
            if u'Картинка' in product:
                images_dict[item_data['xml_id']] = product[u'Картинка']
            data_list.append(self.prepare_product_data(item_data, product))
            if u'ЗначенияСвойств' in product:
                for prop in product[u'ЗначенияСвойств'].itervalues():
                    self.property_values.append((prop, item_data['xml_id']))

        self.xml_products = self.import_item_data(data_list, self.xml_products, self.model_product)
        self.post_import_products(data_list)
        log.info('import products time: %s' % (datetime.now() - self.exec_time))
        self.exec_time = datetime.now()
        self.process_images(images_dict)
        return True

    def import_properties(self, xml_obj):
        if not self.model_property:
            return False
        log.info('import properties')
        data_list = []
        self.xml_props = {xml: pk for pk, xml in self.model_property.objects.values_list('pk', 'xml_id')}
        for xml_child in xml_obj.getchildren():
            prop = get_dict_from_lxml(xml_child)
            item_data = {
                'xml_id': prop[u'Ид'],
                'title': prop[u'Наименование']}
            data_list.append(self.prepare_property_data(item_data, prop))
        self.xml_props = self.import_item_data(data_list, self.xml_props, self.model_property)
        log.info('import properties time: %s' % (datetime.now() - self.exec_time))
        self.exec_time = datetime.now()
        return True

    def import_property_values(self):
        if not self.model_property_value:
            return False
        log.info('import property values')
        data_list = []
        for prop, product_xml_id in self.property_values:
            prop_data = {'value': prop[u'Значение']}

            if u'Ид' in prop and prop[u'Ид'] in self.xml_props:
                prop_data['prop_id'] = self.xml_props[prop[u'Ид']]
            else:
                continue

            if product_xml_id in self.xml_products:
                prop_data['product_id'] = self.xml_products[product_xml_id]
            else:
                continue

            data_list.append(self.prepare_property_value_data(prop_data, prop))
        if self.catalog_only_changes:
            for value_data in data_list:
                opts = {'product_id': value_data['product_id'], 'prop_id': value_data['prop_id']}
                obj = self.model_property_value.objects.filter(**opts).first()
                if not obj:
                    obj = self.model_property_value(**opts)
                obj.value = value_data['value']
                obj.save()
        else:
            self.model_property_value.objects.all().delete()
            self.import_item_data(data_list, [], self.model_property_value, resolve_xml_id=False)
        log.info('import property values time: %s' % (datetime.now() - self.exec_time))
        self.exec_time = datetime.now()
        return True

    def import_sections(self, xml_obj):
        if not self.model_section:
            return False
        log.info('import sections')
        data_list = []
        groups_list = []
        groups_update_parent = {}
        self.xml_sections = {xml: pk for pk, xml in self.model_section.objects.values_list('pk', 'xml_id')}

        for pos, third in enumerate(xml_obj.getchildren(), 1):
            groups_list = get_tree_from_lxml(third, u'Группы', u'Ид', {'_position_': pos}, groups_list)

        for group in groups_list:
            item_data = {
                'xml_id': group[u'Ид'],
                'position': group['_position_'],
                'title': group[u'Наименование'],
                'slug': translit.slugify(group[u'Наименование']),
                'lft': 0,
                'rght': 0,
                'tree_id': 0,
                'level': 0}

            if '_parent_' in group:
                if group['_parent_'] in self.xml_sections:
                    item_data['parent_id'] = self.xml_sections[group['_parent_']]
                else:
                    groups_update_parent[item_data['xml_id']] = group['_parent_']
            data_list.append(self.prepare_section_data(item_data, group))
        self.xml_sections = self.import_item_data(data_list, self.xml_sections, self.model_section)

        for xml_id, parent_xml_id in groups_update_parent.iteritems():
            self.model_section.objects.filter(pk=self.xml_sections[xml_id]).\
                update(parent=self.xml_sections[parent_xml_id])

        self.model_section.objects.rebuild()
        log.info('import sections time: %s' % (datetime.now() - self.exec_time))
        self.exec_time = datetime.now()
        return True

    def post_import_products(self, data_list):
        pass

    def prepare_product_data(self, data, group):
        return data

    def prepare_property_data(self, data, prop):
        return data

    def prepare_property_value_data(self, data, prop):
        return data

    def prepare_section_data(self, data, group):
        return data

    def process_export(self):
        if not self.model_order:
            return False
        log.info('process export')
        xml_root = etree.Element(u'КоммерческаяИнформация')
        xml_root.attrib[u'ВерсияСхемы'] = '2.03'
        xml_root.attrib[u'ДатаФормирования'] = '2007-10-30'
        for order in self.model_order.objects.all():
            xml_document = etree.Element(u'Документ')
            agent_id = unicode(order.user.id) if order.user else u'_%s' % unicode(order.id)
            delivery_address = [
                {u'Тип': u'Город', u'Значение': order.city},
                {u'Тип': u'Улица', u'Значение': order.street},
                {u'Тип': u'Дом', u'Значение': order.house},
            ]
            if order.housing:
                delivery_address.append({u'Тип': u'Корпус', u'Значение': order.housing})
            append_data({
                u'Ид': str(order.id),
                u'Номер': str(order.id),
                u'Дата': order.created_at.strftime('%Y-%m-%d'),
                u'ХозОперация': u'Заказ товара',
                u'Роль': u'Продавец',
                # u'Валюта': u'руб',
                u'Валюта': u'RUB',
                # u'Курс': '1',
                u'Курс': '1.0000',
                u'Сумма': str(order.price),
                u'Контрагенты': {
                    u'Контрагент': {
                        u'Ид': agent_id,
                        u'Наименование': order.email,
                        u'Роль': u'Покупатель',
                        u'ПолноеНаименование': order.email,
                    },
                },
                u'Время': order.created_at.strftime('%H:%I:%S'),
                u'Комментарий': order.comment
            }, xml_document)
            xml_products = etree.Element(u'Товары')
            for product in order.products.all():
                xml_product = etree.Element(u'Товар')
                append_data({
                    u'Ид': product.xml_id,
                    # u'ИдКаталога': product.xml_id,
                    u'Наименование': product.title,
                    u'ЦенаЗаЕдиницу': str(product.price),
                    u'Количество': str(product.count),
                    u'Сумма': str(product.price_total),
                    u'ЗначенияРеквизитов': {
                        u'ЗначениеРеквизита': [
                            {u'Наименование': u'ВидНоменклатуры', u'Значение': u'Товар'},
                            {u'Наименование': u'ТипНоменклатуры', u'Значение': u'Товар'}]}
                }, xml_product)
                xml_product_unit = etree.Element(u'БазоваяЕдиница')
                xml_product_unit.attrib[u'Код'] = '796'
                xml_product_unit.attrib[u'НаименованиеПолное'] = u'Штука'
                xml_product_unit.attrib[u'МеждународноеСокращение'] = 'PCE'
                xml_product_unit.text = u'шт'
                xml_product.append(xml_product_unit)
                xml_products.append(xml_product)
            xml_document.append(xml_products)
            append_data({u'ЗначенияРеквизитов': {u'ЗначениеРеквизита': [
                {u'Наименование': u'Метод оплаты', u'Значение': order.payment},
                # {u'Наименование': u'Заказ оплачен', u'Значение': u'false'},
                # {u'Наименование': u'Доставка разрешена', u'Значение': u'false'},
                # {u'Наименование': u'Отменен', u'Значение': u'false'},
                # {u'Наименование': u'Финальный статус', u'Значение': u'false'},
                {u'Наименование': u'Статус заказа', u'Значение': order.status_verbose},
                # {u'Наименование': u'Дата изменения статуса', u'Значение': },
            ]}}, xml_document)
            xml_root.append(xml_document)

        return etree.tostring(xml_root, encoding='utf-8', pretty_print=True)

    def process_import(self, file_path):
        start_time = datetime.now()
        self.exec_time = start_time
        log.info('process import')

        with open(file_path, 'r') as f:
            xml = etree.fromstring(f.read())
            for first in xml.getchildren():
                if remove_xml_namespace(first.tag) == u'Классификатор':
                    for second in first.getchildren():
                        # sections
                        if remove_xml_namespace(second.tag) == u'Группы':
                            self.import_sections(second)

                        # properties
                        elif remove_xml_namespace(second.tag) == u'Свойства':
                            self.import_properties(second)

                elif remove_xml_namespace(first.tag) == u'Каталог':
                    if u'СодержитТолькоИзменения' in first.attrib:
                        self.catalog_only_changes = first.attrib[u'СодержитТолькоИзменения'] != 'false'
                    for second in first.getchildren():
                        # products & props values
                        if remove_xml_namespace(second.tag) == u'Товары':
                            self.import_products(second)
                            self.import_property_values()

                elif remove_xml_namespace(first.tag) == u'ПакетПредложений':
                    for second in first.getchildren():
                        # offers
                        if remove_xml_namespace(second.tag) == u'Предложения':
                            self.import_offers(second)
        log.info('total import time: %s' % (datetime.now() - start_time))

    def process_images(self, images_dict):
        if not self.image_manager:
            return False
        log.info('process images')
        for xml_id, image_path in images_dict.iteritems():
            path = os.path.join(settings.MEDIA_ROOT, '1c_exchange', image_path)
            try:
                data = {'file': File(open(path))}
                product = self.model_product.objects.get(pk=self.xml_products[xml_id])
                images = getattr(product, self.image_manager)
                if self.first_image_delete and self.image_position:
                    images.filter(**{self.image_position: 1}).delete()
                if self.image_position:
                    data[self.image_position] = 1
                img = images.create(**data)
                if self.image_main:
                    setattr(product, self.image_main, img.file)
                    product.save()
            except IOError, e:
                log.info(str(e))
        log.info('process images time: %s' % (datetime.now() - self.exec_time))
        self.exec_time = datetime.now()
