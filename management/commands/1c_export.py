# -*- coding: utf-8 -*-
import importlib
from django.conf import settings
from django.core.management import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('file_path', nargs='?')

    def handle(self, *args, **options):
        c1_exchange_module = getattr(settings, 'C1_EXCHANGE_MODULE', 'tools.c1_exchange')
        c1m = importlib.import_module(c1_exchange_module)
        exchange = c1m.C1Exchange(verbose=True, logger=self.stdout.write)
        data = exchange.process_export()
        if options['file_path']:
            f = open(options['file_path'], 'w')
            f.write(data)
            f.close()
        else:
            print data
