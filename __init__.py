# -*- coding: utf-8 -*-
from math import floor


def check_url(url, request, include=True):
    if include and request.get_full_path() != '/' and url.startswith(request.get_full_path()):
        return True
    elif request.get_full_path() == url:
        return True
    return False


def chunks(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]


def get_dict_from_lxml(lxml_obj, translit=False, force_list=False, remove_namespaces=True, list_tags=list()):
    children = lxml_obj.getchildren()
    if (len(children) > 1 and children[0].tag == children[1].tag) or force_list:
        value = []
        for obj in children:
            value.append(get_dict_from_lxml(obj, translit, remove_namespaces=remove_namespaces))
    elif len(children) > 0:
        value = {}
        if translit:
            from pytils.translit import translify
        for obj in children:
            tag = obj.tag
            if remove_namespaces:
                tag = remove_xml_namespace(tag)
            if translit:
                tag = translify(tag)
            value[tag] = get_dict_from_lxml(
                obj, translit, force_list=tag in list_tags, remove_namespaces=remove_namespaces)
    else:
        value = lxml_obj.text
    return value


def get_tree_from_lxml(lxml_obj, sub_items_tag, parent_id_tag, initial=None, items_list=list()):
    item_dict = initial if initial else {}
    sub_items = []

    for elem in lxml_obj.getchildren():
        elem_tag = remove_xml_namespace(elem.tag)
        if elem_tag == sub_items_tag:
            sub_items = elem.getchildren()
        else:
            item_dict[elem_tag] = elem.text

    if len(item_dict):
        items_list.append(item_dict)
    for pos, elem in enumerate(sub_items, 1):
        initial = {'_position_': pos}
        if parent_id_tag in item_dict:
            initial['_parent_'] = item_dict[parent_id_tag]
        items_list = get_tree_from_lxml(elem, sub_items_tag, parent_id_tag, initial, items_list)
    return items_list


def random_string(num=8):
    import random
    import string
    return ''.join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(num))


def remove_xml_namespace(tag):
    if not hasattr(tag, 'find'):
        return tag
    i = tag.find('}')
    if i >= 0:
        tag = tag[i+1:]
    return tag


def unique(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]
