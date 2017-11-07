import base64
import importlib
import logging
import os
import shutil
import zipfile
from django.contrib import auth
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt


file_limit = getattr(settings, 'C1_EXCHANGE_FILE_LIMIT', 1024*1024*10)
c1_exchange_module = getattr(settings, 'C1_EXCHANGE_MODULE', 'tools.c1_exchange')
upload_dir = os.path.join(settings.MEDIA_ROOT, '1c_exchange')
log = logging.getLogger('c1_exchange')


def catalog_checkauth(request):
    try:
        opts = request.META['HTTP_AUTHORIZATION'].split(' ')
        if len(opts) == 2 and opts[0].lower() == 'basic':
            username, password = base64.b64decode(opts[1]).split(":")
            user = auth.authenticate(username=username, password=password)
            auth.login(request, user)
    except KeyError:
        pass
    
    if request.user.is_superuser:
        request.session.save()
        request.session['is_checked'] = True
        resp = HttpResponse('success\n%s\n%s' % (
            settings.SESSION_COOKIE_NAME, request.session.session_key))
        log.info('authorisation success')
        return resp
    else:
        log.error('authorisation error: incorrect credentials, user is not superuser')
        return HttpResponseBadRequest('failure\nAuthorisation error: incorrect login or password.')


def catalog_init(request):
    if os.path.exists(upload_dir):
        shutil.rmtree(upload_dir)
    os.makedirs(upload_dir)
    log.info('init mode success')
    return HttpResponse('zip=yes\n''file_limit=%s' % str(file_limit))


def catalog_file(request):
    file_data = request.read()
    if len(file_data) < 1:
        log.error('bad request file_data len: %s' % len(file_data))
        return HttpResponseBadRequest('failure\n''bad request data')
    '''
    try:
        file_data = request.FILES.values()[0]
    except IndexError:
        return HttpResponseBadRequest('failure\n''there is no file')
    '''

    filename = request.GET.get('filename')
    if not filename or len(filename) < 3:
        log.error('bad filename: %s' % filename)
        return HttpResponseBadRequest('failure\n''bad filename')

    file_path = os.path.join(upload_dir, filename)
    try:
        with open(file_path, 'ab') as f:
            # for chunk in file_data.chunks():
            #     f.write(chunk)
            f.write(file_data)
            request.session['unzip_file'] = file_path
    except IOError, e:
        log.error(str(e))
        return HttpResponseBadRequest('failure\n%s' % str(e))

    log.info('file mode success')
    return HttpResponse('success')


def catalog_import(request):
    if 'unzip_file' in request.session:
        log.warn('unzip file: %s' % request.session.get('unzip_file'))
        try:
            z = zipfile.ZipFile(request.session.get('unzip_file'))
            z.extractall(upload_dir)
            del request.session['unzip_file']
        except IOError, e:
            log.error(str(e))
            return HttpResponseBadRequest('failure\n''problem with zip file')
        log.info('file unzipped')
        return HttpResponse('progress\nfile unzipped')

    filename = request.GET.get('filename')
    if not filename or len(filename) < 3:
        log.error('bad filename: %s' % filename)
        return HttpResponseBadRequest('failure\n''bad filename')

    c1m = importlib.import_module(c1_exchange_module)
    exchange = c1m.C1Exchange()
    exchange.process_import(os.path.join(upload_dir, filename))
    log.info('import mode success')
    return HttpResponse('success\nfile imported')


@csrf_exempt
def dispatch(request):
    if request.GET.get('mode') != 'checkauth' and not request.user.is_superuser:
        log.error('dispatch error: user is not superuser')
        return HttpResponseBadRequest('failure\nis not superuser')

    method = '%s_%s' % (request.GET.get('type'), request.GET.get('mode'))
    if method in globals():
        log.info('run %s..' % method)
        try:
            return globals()[method](request)
        except Exception, e:
            log.error(str(e))
            return HttpResponseBadRequest('failure\n%s' % str(e))
    else:
        log.error('method does not exists: %s' % method)
        return HttpResponseBadRequest('Method does not exists')


def sale_checkauth(request):
    return catalog_checkauth(request)


def sale_init(request):
    return catalog_init(request)


def sale_query(request):
    c1m = importlib.import_module(c1_exchange_module)
    exchange = c1m.C1Exchange()
    xml_data = exchange.process_export()
    return HttpResponse(xml_data, content_type='application/xml')


def sale_success(request):
    return HttpResponse('success')


def sale_file(request):
    return HttpResponse('success')
