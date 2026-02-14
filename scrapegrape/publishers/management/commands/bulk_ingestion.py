import csv

from django.conf import settings
from django.core.management.base import BaseCommand

from publishers.tasks import analyze_url


class Command(BaseCommand):
    def handle(self, *args, **options):
        csv_path = settings.BASE_DIR.parent / "sites.csv"
        reader = csv.DictReader(open(csv_path))

        for row in reader:
            analyze_url.delay(row["URL"])
            print(row["URL"])
