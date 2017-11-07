# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from os import path
from . import import_zip
import logging

log = logging.getLogger(__name__)


@csrf_exempt
def import_zip(request):
    if request.META.get('HTTP_APIKEY') != settings.IMPORTXML_API_KEY:
        return HttpResponseBadRequest(u'ApiKey error')

    archive_path = path.join(settings.MEDIA_ROOT, 'import.zip')
    f = open(archive_path, 'wb')
    while True:
        data = request.read(64 * 1024)
        f.write(data)
        if not data:
            break
    f.close()
    try:
        import_zip(archive_path)
    except Exception as e:
        import traceback
        tr = unicode(traceback.format_exc())
        log.error(tr)
        return HttpResponseBadRequest(tr)
    return HttpResponse()
