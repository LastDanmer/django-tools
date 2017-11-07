from django.views import generic


class SetAlertMixin(object):
    success_message = ''
    fail_message = ''

    def get_success_message(self, form):
        return self.success_message

    def get_fail_message(self, form):
        return self.fail_message

    def set_success_message(self, form):
        self.request.session['alert'] = self.get_success_message(form)

    def set_fail_message(self, form):
        self.request.session['alert'] = self.get_fail_message(form)

    def form_valid(self, form):
        self.set_success_message(form)
        return super(SetAlertMixin, self).form_valid(form)

    def form_invalid(self, form):
        self.set_fail_message(form)
        return super(SetAlertMixin, self).form_invalid(form)
