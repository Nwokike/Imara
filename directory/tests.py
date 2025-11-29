from django.test import TestCase
from .models import AuthorityContact

class AuthorityContactTest(TestCase):
    def setUp(self):
        # Create some dummy authorities
        AuthorityContact.objects.create(
            agency_name="Lagos Cybercrime Unit",
            email="lagos@police.ng",
            jurisdiction_name="Lagos",
            priority=10
        )
        AuthorityContact.objects.create(
            agency_name="Kenya DCI",
            email="dci@kenya.go.ke",
            jurisdiction_name="Kenya",
            priority=10
        )
        AuthorityContact.objects.create(
            agency_name="Global Fallback",
            email="help@global.org",
            jurisdiction_name="Global",
            priority=1
        )

    def test_find_by_location_exact(self):
        """Test finding an authority by exact location match"""
        authority = AuthorityContact.find_by_location("Lagos")
        self.assertEqual(authority.agency_name, "Lagos Cybercrime Unit")

    def test_find_by_location_case_insensitive(self):
        """Test that location matching ignores case"""
        authority = AuthorityContact.find_by_location("kenya")
        self.assertEqual(authority.agency_name, "Kenya DCI")

    def test_fallback_logic(self):
        """Test that it returns a default if location is unknown"""
        authority = AuthorityContact.find_by_location("Mars")
        # Should return the highest priority available if no match
        self.assertIsNotNone(authority)
