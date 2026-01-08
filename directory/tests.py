from django.test import TestCase
from .models import AuthorityContact

class AuthorityContactTest(TestCase):
    def setUp(self):
        self.contact_lagos = AuthorityContact.objects.create(
            agency_name="Lagos Police",
            email="lagos@police.ng",
            jurisdiction_level="state",
            jurisdiction_name="Lagos",
            priority=10,
            is_active=True
        )
        self.contact_nigeria = AuthorityContact.objects.create(
            agency_name="Nigeria Force",
            email="hq@police.ng",
            jurisdiction_level="country",
            jurisdiction_name="Nigeria",
            priority=5,
            is_active=True
        )
        self.contact_nairobi = AuthorityContact.objects.create(
            agency_name="Nairobi Police",
            email="nairobi@police.ke",
            jurisdiction_level="city",
            jurisdiction_name="Nairobi",
            priority=8,
            is_active=True
        )

    def test_find_by_location_exact_match(self):
        """Should find exact match for Lagos"""
        contact = AuthorityContact.find_by_location("Lagos")
        self.assertEqual(contact, self.contact_lagos)

    def test_find_by_location_partial_match(self):
        """Should find partial match (case insensitive)"""
        contact = AuthorityContact.find_by_location("nairobi")
        self.assertEqual(contact, self.contact_nairobi)

    def test_find_by_location_fallback(self):
        """Should return highest priority active contact if location unknown"""
        contact = AuthorityContact.find_by_location("London")
        # Should return Lagos because priority 10 > 8 > 5
        self.assertEqual(contact, self.contact_lagos)

    def test_find_by_location_none(self):
        """Should return highest priority contact if location is None"""
        contact = AuthorityContact.find_by_location(None)
        self.assertEqual(contact, self.contact_lagos)
