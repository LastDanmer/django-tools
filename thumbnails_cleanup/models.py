# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django_cleanup.signals import cleanup_post_delete
from django_cleanup.signals import cleanup_pre_delete
from easy_thumbnails.files import get_thumbnailer
from easy_thumbnails.signals import saved_file
from easy_thumbnails.signal_handlers import generate_aliases_global
import shutil
import os


saved_file.connect(generate_aliases_global)


def delete_thumbnails(**kwargs):
    kwargs['file'].old_path = kwargs['file'].path
    get_thumbnailer(kwargs['file']).delete_thumbnails()
cleanup_pre_delete.connect(delete_thumbnails)


def cleanup_empty_dirs(**kwargs):
    # initially set first dir path of file ...
    path = os.path.dirname(kwargs['file'].old_path)

    # ... and remove all empty parent directories
    while True:
        if path == settings.MEDIA_ROOT:
            break
        if len(os.listdir(path)) == 0:
            shutil.rmtree(path)
        path = os.path.dirname(path)
cleanup_post_delete.connect(cleanup_empty_dirs)
