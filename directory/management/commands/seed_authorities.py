from django.core.management.base import BaseCommand
from directory.models import AuthorityContact


class Command(BaseCommand):
    help = 'Seeds the database with authority contacts and helplines for Project Imara'

    def handle(self, *args, **options):
        authorities = [
            {
                'agency_name': 'Kenya GBV Helpline (FIDA Kenya)',
                'email': 'info@fidakenya.org',
                'phone': '1195',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Kenya',
                'tags': ['Domestic Violence', 'Gender-Based Violence', 'GBV', 'Women Safety'],
                'priority': 10,
                'notes': 'Primary helpline for domestic and gender-based violence in Kenya. Call 1195.'
            },
            {
                'agency_name': 'Befrienders Kenya - Mental Health Crisis',
                'email': 'info@befrienderskenya.org',
                'phone': '+254 722 178 177',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Kenya',
                'tags': ['Mental Health', 'Crisis Support', 'Emotional Support', 'Suicide Prevention'],
                'priority': 9,
                'notes': 'Mental health and crisis support via Befrienders Kenya. mentalhealthafrica.org'
            },
            {
                'agency_name': 'Childline Kenya - Youth Helpline',
                'email': 'info@childlinekenya.co.ke',
                'phone': '116',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Kenya',
                'tags': ['Child Protection', 'Youth Support', 'Children Safety'],
                'priority': 8,
                'notes': 'Child and youth helpline in Kenya. Call 116 for free.'
            },
            {
                'agency_name': 'Mifumi Uganda - GBV Helpline',
                'email': 'info@mifumi.org',
                'phone': '0800 200 250',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Uganda',
                'tags': ['Domestic Violence', 'Sexual Violence', 'GBV', 'Women Safety'],
                'priority': 10,
                'notes': 'Toll-free helpline for domestic and sexual violence in Uganda via Mifumi.'
            },
            {
                'agency_name': 'Mental Health Uganda - Crisis Line',
                'email': 'info@mentalhealthuganda.org',
                'phone': '+256 414 664 264',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Uganda',
                'tags': ['Mental Health', 'Crisis Support', 'Emotional Support'],
                'priority': 9,
                'notes': 'General crisis and mental health support via Mental Health Uganda. mentalhealthafrica.org'
            },
            {
                'agency_name': 'Sauti 116 Uganda - Child Helpline',
                'email': 'info@sauti116.org',
                'phone': '116',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Uganda',
                'tags': ['Child Protection', 'Youth Support', 'Children Safety'],
                'priority': 8,
                'notes': 'Child and youth helpline in Uganda. Call 116 for free.'
            },
            {
                'agency_name': 'WLAC Tanzania - Women Abuse Helpline',
                'email': 'info@wlac.or.tz',
                'phone': '0800 780 100',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Tanzania',
                'tags': ['Domestic Violence', 'Women Abuse', 'GBV', 'Legal Aid'],
                'priority': 10,
                'notes': 'Women Legal Aid Centre Tanzania. Alternative: +255 22 266 4051'
            },
            {
                'agency_name': 'Tanzania Mental Health Trust',
                'email': 'info@tzmht.org',
                'phone': '+255 755 740 725',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Tanzania',
                'tags': ['Mental Health', 'Crisis Support', 'Emotional Support'],
                'priority': 9,
                'notes': 'Mental health and general crisis support in Tanzania. mentalhealthafrica.org'
            },
            {
                'agency_name': 'C-Sema Tanzania - Child Helpline',
                'email': 'info@csema.or.tz',
                'phone': '116',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Tanzania',
                'tags': ['Child Protection', 'Youth Support', 'Children Safety'],
                'priority': 8,
                'notes': 'Child helpline in Tanzania. Call 116 for free.'
            },
            {
                'agency_name': 'SADAG South Africa - Mental Health Crisis',
                'email': 'info@sadag.org',
                'phone': '0800 567 567',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'South Africa',
                'tags': ['Mental Health', 'Crisis Support', 'Suicide Prevention', 'Emotional Support'],
                'priority': 10,
                'notes': 'South African Depression and Anxiety Group. 24-hour crisis line. sadag.org'
            },
            {
                'agency_name': 'GBV Command Centre South Africa',
                'email': 'gbv@dsd.gov.za',
                'phone': '0800 150 150',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'South Africa',
                'tags': ['Gender-Based Violence', 'Domestic Violence', 'Women Safety', 'GBV'],
                'priority': 10,
                'notes': 'National GBV Command Centre. Toll-free 24/7 helpline for gender-based violence.'
            },
            {
                'agency_name': 'SADAG Substance Abuse Line South Africa',
                'email': 'substance@sadag.org',
                'phone': '0800 12 13 14',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'South Africa',
                'tags': ['Substance Abuse', 'Mental Health', 'Addiction Support'],
                'priority': 7,
                'notes': 'SADAG substance abuse and mental health support line. sadag.org'
            },
            {
                'agency_name': 'MANI Nigeria - Mental Health Crisis',
                'email': 'info@mentallyawareng.com',
                'phone': '+234 809 111 6264',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Nigeria',
                'tags': ['Mental Health', 'Crisis Support', 'Emotional Support'],
                'priority': 10,
                'notes': 'Mentally Aware Nigeria Initiative. Alternative: +234 811 680 686. mentalhealthafrica.org'
            },
            {
                'agency_name': 'DSVRT Nigeria - GBV Helpline',
                'email': 'info@dsvrtlagos.org',
                'phone': '+234 0800 72 73 2255',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Nigeria',
                'tags': ['Domestic Violence', 'Sexual Violence', 'GBV', 'Women Safety'],
                'priority': 10,
                'notes': 'Domestic and Sexual Violence Response Team. Emergency: 112. advancenigeria.org'
            },
            {
                'agency_name': 'Women Safe House Nigeria',
                'email': 'help@womensafehouse.org',
                'phone': '+234 811 266 3348',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Nigeria',
                'tags': ['Women Safety', 'Safe House', 'Crisis Support', 'Victim Support'],
                'priority': 9,
                'notes': 'Women and girl-victim support with safe-house crisis line. Evoca Foundation'
            },
            {
                'agency_name': 'DOVVSU Ghana - GBV Helpline',
                'email': 'dovvsu@police.gov.gh',
                'phone': '055 1000 900',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Ghana',
                'tags': ['Domestic Violence', 'Gender-Based Violence', 'GBV', 'Women Safety'],
                'priority': 10,
                'notes': 'Domestic Violence and Victims Support Unit. Ghana Police Service. commonwealthsaysnomore.org'
            },
            {
                'agency_name': 'Ghana Mental Health Lifeline',
                'email': 'info@mentalhealthghana.org',
                'phone': '+233 244 471 279',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Ghana',
                'tags': ['Mental Health', 'Crisis Support', 'Emotional Support'],
                'priority': 9,
                'notes': 'National mental health and crisis lifeline. mentalhealthafrica.org'
            },
            {
                'agency_name': 'Stop Abuse Ghana',
                'email': 'info@stopabuseghana.org',
                'phone': '+233 302 522 902',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Ghana',
                'tags': ['Abuse Support', 'Counselling', 'Women Safety', 'NGO'],
                'priority': 8,
                'notes': 'Abuse support and counselling services NGO. stopabuseghana.org'
            },
            {
                'agency_name': 'Child Helpline Rwanda',
                'email': 'info@childhelplinerw.org',
                'phone': '116',
                'jurisdiction_level': 'country',
                'jurisdiction_name': 'Rwanda',
                'tags': ['Child Protection', 'Youth Support', 'Children Safety'],
                'priority': 10,
                'notes': 'Child and youth helpline in Rwanda. Call 116 for free.'
            },
            {
                'agency_name': 'Pan-African Women Safety Network',
                'email': 'alerts@pawsn.org',
                'phone': '',
                'jurisdiction_level': 'regional',
                'jurisdiction_name': 'Africa',
                'tags': ['Women Safety', 'Online Violence', 'Support Network', 'Fallback'],
                'priority': 3,
                'notes': 'Fallback contact for regions without specific contacts'
            },
        ]

        created_count = 0
        updated_count = 0

        for auth_data in authorities:
            authority, created = AuthorityContact.objects.update_or_create(
                agency_name=auth_data['agency_name'],
                jurisdiction_name=auth_data['jurisdiction_name'],
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
