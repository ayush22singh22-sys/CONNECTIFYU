"""
Management command: import_staff
Usage:
    python manage.py import_staff path/to/staff.csv

CSV format (header required):
    username,first_name,last_name,email,role,department,designation,unit_name

Example:
    prof_sharma,Rajesh,Sharma,rsharma@college.ac.in,FACULTY,Computer Science & Engineering,Associate Professor,Department of Computer Science & Engineering
"""
import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from events.models import UserProfile, StaffProfile, OrganizingUnit


class Command(BaseCommand):
    help = 'Bulk import staff members (Faculty, HOD, Deans, Director, etc.) from CSV'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to staff CSV file')
        parser.add_argument(
            '--default-password',
            type=str,
            default='password123',
            help='Default password for newly created staff accounts (default: password123)',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_file']
        default_pw = options['default_password']

        if not os.path.isfile(csv_path):
            raise CommandError(f"File not found: {csv_path}")

        created_count = 0
        updated_count = 0
        errors = []

        valid_roles = dict(UserProfile.ROLE_CHOICES)

        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            required = {'username', 'email', 'role'}
            if not required.issubset(set(reader.fieldnames or [])):
                raise CommandError(f"CSV must contain at least: {required}. Found: {reader.fieldnames}")

            for lineno, row in enumerate(reader, start=2):
                username = (row.get('username') or '').strip()
                email = (row.get('email') or '').strip()
                role = (row.get('role') or 'FACULTY').strip().upper()
                first = (row.get('first_name') or '').strip()
                last = (row.get('last_name') or '').strip()
                dept = (row.get('department') or '').strip()
                designation = (row.get('designation') or '').strip()
                unit_name = (row.get('unit_name') or '').strip()

                if not username or not email:
                    errors.append(f"Line {lineno}: missing username or email")
                    continue

                if role not in valid_roles:
                    errors.append(f"Line {lineno}: invalid role '{role}'. Valid: {list(valid_roles.keys())}")
                    continue

                # Find or assign unit if specified
                unit = None
                if unit_name:
                    unit = OrganizingUnit.objects.filter(name__icontains=unit_name).first()

                user, created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': first,
                        'last_name': last,
                        'email': email,
                        'is_staff': True,
                    }
                )

                if created:
                    user.set_password(default_pw)
                    user.save()
                    created_count += 1
                    self.stdout.write(f"  Created user: {username} ({role})")
                else:
                    user.first_name = first or user.first_name
                    user.last_name = last or user.last_name
                    user.email = email or user.email
                    user.is_staff = True
                    user.save()
                    updated_count += 1
                    self.stdout.write(f"  Updated user: {username} ({role})")

                # UserProfile
                uprof, _ = UserProfile.objects.get_or_create(user=user)
                uprof.role = role
                uprof.department = dept
                uprof.save()

                # StaffProfile
                sprof, _ = StaffProfile.objects.get_or_create(user=user)
                sprof.designation = designation or f"{valid_roles[role]} — {dept}"
                if unit:
                    sprof.organizing_unit = unit
                sprof.save()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Staff import complete! Created: {created_count} | Updated: {updated_count} | Errors: {len(errors)}"
        ))
        for err in errors:
            self.stdout.write(self.style.ERROR(f"  ERROR: {err}"))
