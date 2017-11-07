# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.contrib import admin


class I18NInline(object):
    def __init__(self, model, admin_site):
        model_use = self.model if hasattr(self, 'model') else model
        self.inlines.append(type(str('I18NInline'), (admin.StackedInline,), {
            'model': model_use._lang_objects_.related.related_model,
            'extra': 1}))
        super(I18NInline, self).__init__(model, admin_site)
