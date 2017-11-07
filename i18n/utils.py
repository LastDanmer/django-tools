from django.conf import settings
from django.utils import translation


def get_language():
    lng = translation.get_language()
    if not lng:
        lng = settings.LANG_DEFAULT
    if lng not in [l for l, v in settings.LANGUAGES]:
        lng, tmp = lng.split('-')
    return lng
