# -*- coding: utf-8 -*-
import importlib
import os
from django.conf import settings
from django.core.management import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        c1_exchange_module = getattr(settings, 'C1_EXCHANGE_MODULE', 'tools.c1_exchange')
        c1m = importlib.import_module(c1_exchange_module)
        exchange = c1m.C1Exchange(verbose=True, logger=self.stdout.write)
        for f in (
            os.path.join(settings.MEDIA_ROOT, '1c_exchange', 'import.xml'),
            os.path.join(settings.MEDIA_ROOT, '1c_exchange', 'offers.xml')
        ):
            exchange.process_import(f)
