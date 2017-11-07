# -*- coding: utf-8 -*-
from django.db import models


class ForeignKey(models.ForeignKey):
    def __init__(self, to, *args, **kwargs):
        try:
            kwargs['verbose_name'] = to._meta.verbose_name
        except AttributeError:
            pass
        super(ForeignKey, self).__init__(to, *args, **kwargs)
