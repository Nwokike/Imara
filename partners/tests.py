from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import PartnerOrganization, PartnerUser, PartnerInvite


class PartnerOrganizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testadmin',
            email='admin@test.com',
            password='testpass123'
        )
        self.org = PartnerOrganization.objects.create(
            name='Test Organization',
            jurisdiction='Kenya'
        )
        self.partner_user = PartnerUser.objects.create(
            user=self.user,
            organization=self.org,
            role='ADMIN'
        )
    
    def test_organization_slug_generation(self):
        """Test that slugs are auto-generated"""
        org = PartnerOrganization.objects.create(
            name='Another Test Org',
            jurisdiction='Nigeria'
        )
        self.assertEqual(org.slug, 'another-test-org')
    
    def test_slug_collision_handling(self):
        """Test that duplicate slugs get counter suffix"""
        org2 = PartnerOrganization.objects.create(
            name='Test Organization',
            jurisdiction='Uganda'
        )
        self.assertEqual(org2.slug, 'test-organization-1')
    
    def test_seats_used_property(self):
        """Test seats_used calculation"""
        self.assertEqual(self.org.seats_used, 1)
    
    def test_is_at_capacity(self):
        """Test capacity check"""
        self.org.max_seats = 1
        self.org.save()
        self.assertTrue(self.org.is_at_capacity)


class PartnerInviteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin', email='admin@test.com', password='pass'
        )
        self.org = PartnerOrganization.objects.create(
            name='Test Org', jurisdiction='Kenya'
        )
    
    def test_invite_token_generated(self):
        """Test that invite tokens are generated"""
        invite = PartnerInvite.objects.create(
            email='invite@test.com',
            organization=self.org,
            role='RESPONDER',
            invited_by=self.user
        )
        self.assertIsNotNone(invite.token)
        self.assertEqual(len(invite.token), 43)  # secrets.token_urlsafe(32) length


class PartnerLoginTests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_login_page_loads(self):
        """Test partner login page loads"""
        response = self.client.get(reverse('partners:login'))
        self.assertEqual(response.status_code, 200)
