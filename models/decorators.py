# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
import datetime


def auto_now(attrs=(dict(name='created_at', on_add=True),)):
    def decorator(cls):
        def pre_save(instance, **kwargs):
            for attr in attrs:
                if instance.id and 'on_add' in attr:
                    continue
                if getattr(instance, attr['name']) is not None:
                    continue
                if 'datetime' in attr:
                    setattr(instance, attr['name'], datetime.datetime.now())
                else:
                    setattr(instance, attr['name'], datetime.date.today())
            return instance
        models.signals.pre_save.connect(pre_save, sender=cls, weak=False)
        return cls
    return decorator


def generate_url(target_attr='url', slug_source='slug', parent_attr='parent'):
    def decorator(cls):
        def pre_save(instance, **kwargs):
            parent = getattr(instance, parent_attr)
            url = ''
            if parent:
                url = '%s/' % getattr(parent, target_attr)
            url += getattr(instance, slug_source)
            setattr(instance, target_attr, url)
            return instance
        models.signals.pre_save.connect(pre_save, sender=cls, weak=False)
        return cls
    return decorator


def ordering(attr='pos', by_parent_queryset=None, by_property=None, by_method=None, step=10, **method_kwargs):
    def decorator(cls):
        def pre_save(instance, **kwargs):
            if getattr(instance, attr) is None:
                try:
                    queryset = kwargs['sender'].objects

                    if by_parent_queryset is not None:
                        keys = by_parent_queryset.split('.')
                        parent = getattr(instance, keys[0])
                        queryset = getattr(parent, keys[1])

                    if by_property is not None:
                        filter_data = {
                            by_property: getattr(instance, by_property)
                        }
                        queryset = queryset.filter(**filter_data)

                    if by_method is not None:
                        queryset = getattr(instance, by_method)(**method_kwargs)

                    last = getattr(queryset.order_by('-' + attr).first(), attr)
                except AttributeError:
                    last = 0
                setattr(instance, attr, last + step)
            return instance
        models.signals.pre_save.connect(pre_save, sender=cls, weak=False)
        return cls
    return decorator


def slugify(source_attr='title', target_attr='slug'):
    def decorator(cls):
        from pytils import translit

        def pre_save(instance, **kwargs):
            if getattr(instance, target_attr) == '':
                setattr(instance,
                        target_attr,
                        translit.slugify(getattr(instance, source_attr)))
            return instance
        models.signals.pre_save.connect(pre_save, sender=cls, weak=False)
        return cls
    return decorator


def update_related(target, source_field='file', target_field='main_image'):
    def decorator(cls):
        def post_save(sender, **kwargs):
            field = filter(lambda x: x.name == target, sender._meta.get_fields())[0]
            obj = getattr(kwargs['instance'], target)
            src = getattr(obj, field.related_query_name()).first()
            setattr(obj, target_field, getattr(src, source_field))
            obj.save()
        models.signals.post_save.connect(post_save, sender=cls, weak=False)
        return cls
    return decorator
