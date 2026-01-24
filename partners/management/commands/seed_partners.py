from django.core.management.base import BaseCommand
from partners.models import PartnerOrganization


class Command(BaseCommand):
    help = 'Seeds the database with partner organizations that can receive forensic alerts'

    def handle(self, *args, **options):
        partners = [
            {
                'name': 'FIDA Kenya',
                'org_type': PartnerOrganization.OrgType.NGO,
                'jurisdiction': 'Kenya',
                'contact_email': 'info@fidakenya.org',
                'phone': '1195',
                'website': 'https://fidakenya.org',
                'is_active': True,
                'is_verified': True,
            },
            {
                'name': 'Mifumi Uganda',
                'org_type': PartnerOrganization.OrgType.NGO,
                'jurisdiction': 'Uganda',
                'contact_email': 'info@mifumi.org',
                'phone': '0800 200 250',
                'website': 'https://mifumi.org',
                'is_active': True,
                'is_verified': True,
            },
            {
                'name': 'WLAC Tanzania',
                'org_type': PartnerOrganization.OrgType.NGO,
                'jurisdiction': 'Tanzania',
                'contact_email': 'info@wlac.or.tz',
                'phone': '0800 780 100',
                'website': 'https://wlac.or.tz',
                'is_active': True,
                'is_verified': True,
            },
            {
                'name': 'GBV Command Centre South Africa',
                'org_type': PartnerOrganization.OrgType.GOV,
                'jurisdiction': 'South Africa',
                'contact_email': 'gbv@dsd.gov.za',
                'phone': '0800 150 150',
                'website': 'https://www.gov.za',
                'is_active': True,
                'is_verified': True,
            },
            {
                'name': 'DSVRT Nigeria',
                'org_type': PartnerOrganization.OrgType.LEA,
                'jurisdiction': 'Nigeria',
                'contact_email': 'info@dsvrtlagos.org',
                'phone': '+234 0800 72 73 2255',
                'website': 'https://advancenigeria.org',
                'is_active': True,
                'is_verified': True,
            },
            {
                'name': 'DOVVSU Ghana',
                'org_type': PartnerOrganization.OrgType.LEA,
                'jurisdiction': 'Ghana',
                'contact_email': 'dovvsu@police.gov.gh',
                'phone': '055 1000 900',
                'website': 'https://police.gov.gh',
                'is_active': True,
                'is_verified': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for partner_data in partners:
            partner, created = PartnerOrganization.objects.update_or_create(
                name=partner_data['name'],
                jurisdiction=partner_data['jurisdiction'],
                defaults=partner_data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created: {partner.name} ({partner.jurisdiction})'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'Updated: {partner.name} ({partner.jurisdiction})'))

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeding complete! Created: {created_count}, Updated: {updated_count}'
        ))
