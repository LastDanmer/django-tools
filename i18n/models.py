# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models
from django.db.models.base import ModelBase
from copy import deepcopy
from .utils import get_language


class LangModelBase(ModelBase):
    """Добавляет локализованные версии полей указанных в «_lang_fields»"""
    def __new__(cls, name, bases, attrs):
        if '_lang_fields' not in attrs:
            raise ImproperlyConfigured('missing _lang_fields attribute')

        # check settings
        if not hasattr(settings, 'LANGUAGES'):
            raise ImproperlyConfigured('not found LANGUAGES in settings')

        current_lng = get_language()
        disable_required = getattr(settings, 'TOOLS_I18N_DISABLE_REQUIRED', False)
        default_lang = getattr(settings, 'LANG_DEFAULT')

        # add new field copies
        for attr_name in attrs['_lang_fields']:
            for lng, verbose in settings.LANGUAGES:
                attr_obj = deepcopy(attrs[attr_name])
                if attr_obj.verbose_name:
                    attr_obj.verbose_name += u' (%s)' % lng
                if disable_required and lng != default_lang:
                    attr_obj.null = True
                    attr_obj.blank = True
                attrs['%s_%s' % (attr_name, lng)] = attr_obj
            del attrs[attr_name]

        if 'Meta' in attrs and hasattr(attrs['Meta'], 'ordering'):
            ordering = []
            for f in attrs['Meta'].ordering:
                if f in attrs['_lang_fields']:
                    ordering.append('%s_%s' % (f, current_lng))
                else:
                    ordering.append(f)
            attrs['Meta'].ordering = ordering

        model = super(LangModelBase, cls).__new__(cls, name, bases, attrs)

        def __getattr__(self, item):
            if item in self._lang_fields:
                return getattr(self, '%s_%s' % (item, current_lng))
            raise AttributeError
        model.__getattr__ = __getattr__
        return model


class WithLangModelBase(ModelBase):
    def __new__(cls, name, bases, attrs):
        if '_lang_fields_' not in attrs:
            raise ImproperlyConfigured('missing _lang_fields_ attribute for %s model' % name)

        attrs['_original_fields_'] = {}
        for attr_name in attrs['_lang_fields_']:
            attrs['_original_fields_'][attr_name] = deepcopy(attrs[attr_name])
            attrs['_base_%s' % attr_name] = deepcopy(attrs[attr_name])
            del attrs[attr_name]

        model = super(WithLangModelBase, cls).__new__(cls, name, bases, attrs)

        def __getattr__(self, item):
            if not hasattr(self, '_current_lang_'):
                self._current_lang_ = get_language()

            if item in self._lang_fields_:
                if not hasattr(self, '_lang_inst_'):
                    lang_objects = self._lang_objects_.filter(_lang=self._current_lang_)
                    if lang_objects.count() > 0:
                        self._lang_inst_ = lang_objects[0]
                    else:
                        self._lang_inst_ = None
                if self._lang_inst_:
                    return getattr(self._lang_inst_, item)
                else:
                    return getattr(self, '_base_%s' % item)
            raise AttributeError

        model.__getattr__ = __getattr__
        return model


def create_lang_model(base):
    if not hasattr(settings, 'LANGUAGES'):
        raise ImproperlyConfigured('not found LANGUAGES in settings')

    if not hasattr(base, '_lang_fields_'):
        raise ImproperlyConfigured('missing _lang_fields_ attribute for %s model' % base.__name__)

    class Meta:
        verbose_name = 'Языковая версия'
        verbose_name_plural = 'Языковые версии'
    attrs = {
        'Meta': Meta,
        '__module__': base.__module__,
        '_base': models.ForeignKey(base, related_name='_lang_objects_'),
        '_lang': models.CharField(verbose_name='Язык', choices=settings.LANGUAGES, max_length=2),}
    for field in base._lang_fields_:
        attrs[field] = deepcopy(base._original_fields_[field])
    lang_model = type(str('%sLang' % base.__name__), (models.Model,), attrs)

    def __unicode__(self):
        lang = filter(lambda x: x[0] == self._lang, settings.LANGUAGES)
        return lang[0][1] if len(lang) > 0 else self._lang
    lang_model.__unicode__ = __unicode__
    return lang_model
