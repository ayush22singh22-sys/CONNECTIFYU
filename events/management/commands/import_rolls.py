"""
Management command: import_rolls
Usage:
    python manage.py import_rolls path/to/rolls.csv

CSV format (header required):
    roll_number,name,department,year

Example rows:
    21BCSE101,Aarav Patel,Computer Science & Engineering,1
    21BECE034,Ananya Sen,Electronics & Communication,1
"""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from events.models import RollWhitelist


class Command(BaseCommand):
    help = 'Import student roll numbers from a CSV file into the RollWhitelist table'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file (roll_number,name,department,year)')
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='If set, update existing entries even if already used (default: skip existing)',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        overwrite = options['overwrite']

        if not os.path.isfile(csv_path):
            raise CommandError(f"File not found: {csv_path}")

        created = 0
        updated = 0
        skipped = 0
        errors  = []

        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            # Validate required columns
            required = {'roll_number'}
            if not required.issubset(set(reader.fieldnames or [])):
                raise CommandError(
                    f"CSV must have at least a 'roll_number' column. "
                    f"Found: {reader.fieldnames}"
                )

            for lineno, row in enumerate(reader, start=2):
                roll = (row.get('roll_number') or '').strip().upper()
                if not roll:
                    errors.append(f"Line {lineno}: empty roll_number — skipped")
                    continue

                name  = (row.get('name') or '').strip()
                dept  = (row.get('department') or '').strip()
                try:
                    year = int((row.get('year') or '1').strip())
                    if year not in (1, 2, 3, 4):
                        raise ValueError
                except ValueError:
                    year = 1

                existing = RollWhitelist.objects.filter(roll_number=roll).first()

                if existing:
                    if overwrite:
                        existing.name       = name or existing.name
                        existing.department = dept or existing.department
                        existing.year       = year
                        existing.save()
                        updated += 1
                        self.stdout.write(f"  Updated : {roll}")
                    else:
                        skipped += 1
                        self.stdout.write(self.style.WARNING(f"  Skipped (exists): {roll}"))
                else:
                    RollWhitelist.objects.create(
                        roll_number=roll,
                        name=name,
                        department=dept,
                        year=year,
                        is_used=False,
                    )
                    created += 1
                    self.stdout.write(f"  Created : {roll} — {name}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done! Created: {created} | Updated: {updated} | Skipped: {skipped} | Errors: {len(errors)}"
        ))
        for e in errors:
            self.stdout.write(self.style.ERROR(f"  ERROR: {e}"))

