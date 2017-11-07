# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django import http
from django.conf import settings
from django.contrib import messages
from django.contrib.admin.helpers import Fieldset
from django.core import mail
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404
from django.template import loader
from django.template import RequestContext
from django.utils.http import is_safe_url
from django.views import generic
import json


class BaseAdminFormView(generic.FormView):
    """Основа для кастомизации AdminForm"""
    template_name = 'admin/form.html'
    success_message = None
    form_class = None
    page_title = None

    def get_success_url(self):
        return self.request.get_full_path()

    def form_valid(self, form):
        if self.success_message:
            messages.success(self.request, self.success_message)
            return self.render_to_response(self.get_context_data(form=form))
        else:
            return super(BaseAdminFormView, self).form_valid(form)

    def get_context_data(self, **kwargs):
        context = super(BaseAdminFormView, self).get_context_data(**kwargs)
        context['adminform'] = [Fieldset(
            context['form'],
            fields=(x.name for x in context['form'].visible_fields()))]
        return context


class ManyTemplatesMixin(object):
    """Возвращает JSON с html от нескольких шаблонов из «template_names»"""
    template_names = {}

    def update_data(self, data):
        return data

    def render_to_response(self, context, **response_kwargs):
        response_kwargs.setdefault('content_type', self.content_type)
        data = {}
        for key, template_name in self.template_names.iteritems():
            t = loader.get_template(template_name)
            c = RequestContext(self.request, context)
            data[key] = t.render(c)
        return http.HttpResponse(json.dumps(self.update_data(data), cls=DjangoJSONEncoder), mimetype='application/json')


class NotifyViewMixin(object):
    """Отправляет сообщение на email после успешной отправки формы"""
    field_labels = {}
    use_model_fields = False
    message_subject = 'Сообщение с сайта'
    message_from = None
    message_to = None

    def __init__(self, *args, **kwargs):
        super(NotifyViewMixin, self).__init__(*args, **kwargs)
        if not self.message_from:
            self.message_from = settings.DEFAULT_FROM_EMAIL
        if not self.message_to:
            self.message_to = settings.DEFAULT_TO_EMAIL

    @staticmethod
    def clean_field_value(value):
        if value is True:
            value = 'Да'
        elif isinstance(value, dt):
            value = value.strftime('%d.%m.%Y %H:%M')
        return value

    def message_row(self, label, value):
        return '%s: %s<br>\n' % (label, value)

    def message_body(self, msg):
        return msg

    def form_valid(self, form):
        message_body = ''
        if self.use_model_fields:
            for f in self.model._meta.get_fields():
                if f.auto_created:
                    continue
                value = type(self).clean_field_value(getattr(form.instance, f.name))
                if value:
                    message_body += self.message_row(self.field_labels.get(f.name, f.verbose_name), value)
        else:
            for k, f in [x for x in form.fields.items() if x[0] != 'captcha']:
                value = type(self).clean_field_value(form.cleaned_data[k])
                if value:
                    message_body += self.message_row(self.field_labels.get(k, f.label), value)

        message = mail.EmailMessage(
            self.message_subject,
            self.message_body(message_body),
            self.message_from,
            self.message_to)
        for file in form.files.values():
            message.attach(file.name, file.read(), file.content_type)
        message.content_subtype = 'html'
        message.send()
        return super(NotifyViewMixin, self).form_valid(form)


class ReferrerMixin(object):
    """Редиректит на предыдущую страницу после отправки формы"""
    def get_redirect_url(self, *args, **kwargs):
        url = self.request.META.get('HTTP_REFERER')
        return url if is_safe_url(url, self.request.get_host()) else '/'

    def get_success_url(self):
        return self.get_redirect_url()


class LoginRequiredMixin(object):
    """Требует авторизацию и при отсутствии отправляет на «login_redirect» либо на 404"""
    login_redirect = getattr(settings, 'LOGIN', False)

    def get_login_redirect(self):
        return self.login_redirect

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated() and self.is_correct_user():
            return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
        else:
            login_redirect = self.get_login_redirect()
            if login_redirect:
                return http.HttpResponseRedirect(login_redirect)
            else:
                raise http.Http404()

    def is_correct_user(self):
        return True


class SectionView(generic.ListView):
    """Гибрид «ListView» и «DetailView», доблавяет объект «section» в «ListView»"""
    section = None
    section_attr = 'section'
    section_kwargs = ['slug']
    section_model = None
    section_mptt = True

    def get_section_kwargs(self):
        return {arg: self.kwargs[arg] for arg in self.section_kwargs}

    def get_section(self):
        return get_object_or_404(self.section_model, **self.get_section_kwargs())

    def get_queryset(self):
        if not self.section_attr:
            raise NotImplementedError('"section_attr" must be defined for this view')
        if not self.section_model:
            raise NotImplementedError('"section_model" must be defined for this view')
        self.section = self.get_section()
        queryset = super(SectionView, self).get_queryset()
        if self.section_mptt:
            filter_data = {'%s__in' % self.section_attr: self.section.get_descendants(True)}
        else:
            filter_data = {self.section_attr: self.section}
        return queryset.filter(**filter_data).distinct()

    def get_context_data(self, **kwargs):
        ctx = super(SectionView, self).get_context_data(**kwargs)
        ctx['section'] = self.section
        return ctx
