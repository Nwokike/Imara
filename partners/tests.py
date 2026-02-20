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

    def test_agent_pro_settings(self):
        """Test Agent Pro fields are persisted"""
        self.org.is_agent_enabled = True
        self.org.agent_persona = "A specialized legal advisor."
        self.org.save()
        
        updated_org = PartnerOrganization.objects.get(pk=self.org.pk)
        self.assertTrue(updated_org.is_agent_enabled)
        self.assertEqual(updated_org.agent_persona, "A specialized legal advisor.")


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
    
    def test_invite_expires_at_auto_set(self):
        """Test that expires_at is auto-set on save"""
        invite = PartnerInvite.objects.create(
            email='invite2@test.com',
            organization=self.org,
            role='RESPONDER',
            invited_by=self.user
        )
        self.assertIsNotNone(invite.expires_at)
    
    def test_is_expired_returns_false_when_expires_at_none(self):
        """Test is_expired handles None expires_at gracefully"""
        invite = PartnerInvite(
            email='test@test.com',
            organization=self.org,
            role='RESPONDER'
        )
        # Before save, expires_at is None
        self.assertFalse(invite.is_expired)
    
    def test_is_valid_returns_true_for_new_invite(self):
        """Test is_valid for new invite before save"""
        invite = PartnerInvite(
            email='test@test.com',
            organization=self.org,
            role='RESPONDER'
        )
        self.assertTrue(invite.is_valid)
    
    def test_is_expired_returns_true_for_past_date(self):
        """Test is_expired returns True for expired invites"""
        from django.utils import timezone
        from datetime import timedelta
        
        invite = PartnerInvite.objects.create(
            email='expired@test.com',
            organization=self.org,
            role='RESPONDER',
            invited_by=self.user
        )
        invite.expires_at = timezone.now() - timedelta(days=1)
        invite.save()
        self.assertTrue(invite.is_expired)
        self.assertFalse(invite.is_valid)


class PartnerLoginTests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_login_page_loads(self):
        """Test partner login page loads"""
        response = self.client.get(reverse('partners:login'))
        self.assertEqual(response.status_code, 200)


class PartnerPortalViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='partneradmin',
            email='partneradmin@test.com',
            password='testpass123'
        )
        self.org = PartnerOrganization.objects.create(
            name='Portal Org',
            jurisdiction='Kenya',
            contact_email='alerts@portal.org',
            is_active=True,
            is_verified=True,
        )
        PartnerUser.objects.create(user=self.user, organization=self.org, role='ADMIN', is_active=True)
        self.client.login(username='partneradmin', password='testpass123')

    def test_my_cases_page_loads(self):
        response = self.client.get(reverse('partners:my_cases'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'partners/my_cases.html')

    def test_settings_page_loads(self):
        response = self.client.get(reverse('partners:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'partners/settings.html')

    def test_settings_update_as_admin(self):
        response = self.client.post(reverse('partners:settings'), {
            "contact_email": "new@portal.org",
            "phone": "12345",
            "website": "https://portal.org",
        })
        self.assertIn(response.status_code, [200, 302])
        self.org.refresh_from_db()
        self.assertEqual(self.org.contact_email, "new@portal.org")


class PartnerAdminTests(TestCase):
    """Tests for Django admin views to catch configuration errors"""
    
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='superadmin',
            email='super@test.com',
            password='superpass123'
        )
        self.client = Client()
        self.client.login(username='superadmin', password='superpass123')
        
        self.org = PartnerOrganization.objects.create(
            name='Admin Test Org',
            jurisdiction='Kenya'
        )
    
    def test_partner_invite_add_view_loads(self):
        """Test that Partner Invite add view loads without errors"""
        response = self.client.get('/imara-admin/partners/partnerinvite/add/')
        self.assertEqual(response.status_code, 200)
    
    def test_partner_invite_changelist_loads(self):
        """Test that Partner Invite list view loads"""
        response = self.client.get('/imara-admin/partners/partnerinvite/')
        self.assertEqual(response.status_code, 200)
    
    def test_partner_invite_change_view_loads(self):
        """Test that Partner Invite change view loads for existing invite"""
        invite = PartnerInvite.objects.create(
            email='change@test.com',
            organization=self.org,
            role='RESPONDER',
            invited_by=self.superuser
        )
        response = self.client.get(f'/imara-admin/partners/partnerinvite/{invite.pk}/change/')
        self.assertEqual(response.status_code, 200)
    
    def test_partner_invite_can_be_created_via_admin(self):
        """Test creating a Partner Invite via admin form submission"""
        from django.utils import timezone
        from datetime import timedelta
        
        expires_at = timezone.now() + timedelta(days=7)
        response = self.client.post('/imara-admin/partners/partnerinvite/add/', {
            'email': 'newinvite@test.com',
            'organization': self.org.pk,
            'role': 'RESPONDER',
            'expires_at_0': expires_at.strftime('%Y-%m-%d'),
            'expires_at_1': expires_at.strftime('%H:%M:%S'),
        })
        # Check no server error (200 = validation error page, 302 = success redirect)
        self.assertIn(response.status_code, [200, 302])
    
    def test_partner_organization_add_view_loads(self):
        """Test that Partner Organization add view loads"""
        response = self.client.get('/imara-admin/partners/partnerorganization/add/')
        self.assertEqual(response.status_code, 200)
    
    def test_partner_user_add_view_loads(self):
        """Test that Partner User add view loads"""
        response = self.client.get('/imara-admin/partners/partneruser/add/')
        self.assertEqual(response.status_code, 200)

