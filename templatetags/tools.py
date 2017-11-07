# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django import template
from django.utils.http import urlencode
from urlparse import urlparse
from urlparse import parse_qs
from urlparse import urlunparse
import re

register = template.Library()


@register.filter()
def clean_phone(phone):
    return re.sub(r'[^\d\+]', '', phone)


@register.filter()
def date_wd(date):
    return ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'][date.weekday()]


@register.filter()
def file_ext(file_obj, truncate=False):
    ext = file_obj.name.split('.')[-1]
    if truncate:
        ext = ext[:3]
    return ext


@register.filter()
def file_size(file_obj, delimiter=' ', suffix='б'):
    num = file_obj.size
    for unit in ['', 'к', 'м', 'г', 'т', 'п', 'е', 'з']:
        if abs(num) < 1024.0:
            return "%s%s%s%s" % (format_number(num, 2), delimiter, unit, suffix)
        num /= 1024.0
    return "%s%s%s%s" % (format_number(num, 2), 'Yi', delimiter, suffix)


def format_number(num, places):
    if num != int(num):
        return '%.*f' % (places, num)
    else:
        return str(int(num))


@register.simple_tag()
def page_url(base_url, page_num):
    url = list(urlparse(base_url))
    query = parse_qs(url[4])
    query['page'] = page_num
    url[4] = urlencode(query, doseq=True)
    return urlunparse(url)


@register.filter()
def pdb(obj):
    try:
        import ipdb
        ipdb.set_trace()
    except ImportError:
        import pdb
        pdb.set_trace()
