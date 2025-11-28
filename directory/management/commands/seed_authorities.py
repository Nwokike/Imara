from django.core.management.base import BaseCommand
from directory.models import AuthorityContact


class Command(BaseCommand):
    help = 'Seeds the database with demo authority contacts for Project Imara'

    def handle(self, *args, **options):
        authorities = [
            {
                'agency_name': 'Nigeria Police Force - Cybercrime Unit',
                'email': 'cybercrime@npf.gov.ng',
                'phone': '+234-1-234-5678',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Nigeria',
                'tags': ['Cybercrime', 'Online Harassment', 'Digital Threats'],
                'priority': 10,
                'notes': 'Primary contact for cybercrime cases in Nigeria'
            },
            {
                'agency_name': 'Lagos State Domestic Violence Unit',
                'email': 'dvru@lagostate.gov.ng',
                'phone': '+234-1-765-4321',
                'jurisdiction_level': 'state',
                'jurisdiction_name': 'Lagos',
                'tags': ['Domestic Violence', 'Women Safety', 'Threats'],
                'priority': 9,
                'notes': 'Lagos state specialized unit for domestic violence and threats'
            },
            {
                'agency_name': 'Kenya National Police - Gender Desk',
                'email': 'genderdesk@police.go.ke',
                'phone': '+254-20-234-5678',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Kenya',
                'tags': ['Gender Violence', 'Women Safety', 'Online Harassment'],
                'priority': 10,
                'notes': 'National gender desk for Kenya'
            },
            {
                'agency_name': 'Nairobi Women Safety Initiative',
                'email': 'safety@nairobiws.org',
                'phone': '+254-20-111-2222',
                'jurisdiction_level': 'city',
                'jurisdiction_name': 'Nairobi',
                'tags': ['Women Safety', 'Harassment', 'Support Services'],
                'priority': 8,
                'notes': 'NGO providing support for women in Nairobi'
            },
            {
                'agency_name': 'South Africa Police Service - SAPS',
                'email': 'cybercrime@saps.gov.za',
                'phone': '+27-12-345-6789',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'South Africa',
                'tags': ['Cybercrime', 'Online Threats', 'Digital Violence'],
                'priority': 10,
                'notes': 'South African Police Service cybercrime division'
            },
            {
                'agency_name': 'Ghana Domestic Violence Victim Support',
                'email': 'support@dovvsu.gov.gh',
                'phone': '+233-30-234-5678',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Ghana',
                'tags': ['Domestic Violence', 'Women Safety', 'Victim Support'],
                'priority': 9,
                'notes': 'Ghana DOVVSU for domestic violence cases'
            },
            {
                'agency_name': 'Accra Women Rights Coalition',
                'email': 'help@accrawrc.org',
                'phone': '+233-30-111-2222',
                'jurisdiction_level': 'city',
                'jurisdiction_name': 'Accra',
                'tags': ['Women Rights', 'Harassment', 'Legal Support'],
                'priority': 7,
                'notes': 'NGO providing legal support for women in Accra'
            },
            {
                'agency_name': 'Uganda Police - Child and Family Protection',
                'email': 'cfpu@police.go.ug',
                'phone': '+256-41-234-5678',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Uganda',
                'tags': ['Family Protection', 'Women Safety', 'Child Protection'],
                'priority': 9,
                'notes': 'Uganda Police child and family protection unit'
            },
            {
                'agency_name': 'Tanzania Women Legal Aid Centre',
                'email': 'help@wlac.or.tz',
                'phone': '+255-22-234-5678',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Tanzania',
                'tags': ['Legal Aid', 'Women Rights', 'Harassment'],
                'priority': 8,
                'notes': 'Legal aid for women in Tanzania'
            },
            {
                'agency_name': 'Pan-African Women Safety Network',
                'email': 'alerts@pawsn.org',
                'phone': '+1-555-SAFETY',
                'jurisdiction_level': 'regional',
                'jurisdiction_name': 'Africa',
                'tags': ['Women Safety', 'Online Violence', 'Support Network'],
                'priority': 5,
                'notes': 'Fallback contact for regions without specific contacts'
            },
        ]

        created_count = 0
        updated_count = 0

        for auth_data in authorities:
            authority, created = AuthorityContact.objects.update_or_create(
                email=auth_data['email'],
                defaults=auth_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {authority.agency_name}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {authority.agency_name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeding complete! Created: {created_count}, Updated: {updated_count}'
        ))
