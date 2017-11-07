from django.views import generic
from django.utils.translation import check_for_language, LANGUAGE_SESSION_KEY
from .. import views as tools_views


class SetLang(tools_views.ReferrerMixin, generic.RedirectView):
    def get(self, request, *args, **kwargs):
        resp = super(SetLang, self).get(request, *args, **kwargs)
        if check_for_language(kwargs['lang']):
            request.session[LANGUAGE_SESSION_KEY] = kwargs['lang']
        return resp
