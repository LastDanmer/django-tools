# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os
from datetime import time
from hashlib import md5


def generate_upload_name(instance, filename, prefix=None, unique=False):
    if instance is None:
        return filename

    ext = os.path.splitext(filename)[1]
    name = str(instance.pk or '') + '-' + filename + '-' + (str(time()) if unique else '')
    filename = md5(name.encode('utf8')).hexdigest() + ext
    basedir = instance._meta.db_table
    if prefix:
        basedir = os.path.join(basedir, prefix)
    return os.path.join(basedir, filename[:2], filename[2:4], filename)


def make_tree(model=None, queryset=None):
    if model is None and queryset is None:
        raise AttributeError('no model or queryset for make_tree')

    if queryset is None:
        queryset = model.objects.all()
    sections = list(queryset)
    by_parent = {}

    for section in sections:
        parent_id = section.parent_id if section.parent_id else 0
        if parent_id not in by_parent:
            by_parent[parent_id] = []
        by_parent[parent_id].append(section)

    for section in sections:
        if section.id in by_parent:
            section.child_nodes = by_parent[section.id]

    if 0 in by_parent:
        return by_parent[0]
    return None
