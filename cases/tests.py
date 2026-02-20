from django.test import TestCase
from .models import IncidentReport, EvidenceAsset
import hashlib
from django.core.files.uploadedfile import SimpleUploadedFile

class CaseModelTest(TestCase):
    def test_incident_creation(self):
        incident = IncidentReport.objects.create(
            source="web",
            original_text="Test incident",
            risk_score=5
        )
        self.assertTrue(incident.case_id)
        self.assertEqual(incident.source, "web")
        self.assertEqual(incident.risk_score, 5)

    def test_evidence_hashing_text(self):
        incident = IncidentReport.objects.create(source="web")
        text_content = "This is evidence"
        evidence = EvidenceAsset.objects.create(
            incident=incident,
            asset_type="text",
            derived_text=text_content
        )
        # Verify hash was auto-generated
        expected_hash = hashlib.sha256(text_content.encode()).hexdigest()
        self.assertEqual(evidence.sha256_digest, expected_hash)

    def test_evidence_hashing_file(self):
        incident = IncidentReport.objects.create(source="web")
        file_content = b"fake image content"
        uploaded_file = SimpleUploadedFile("test.jpg", file_content, content_type="image/jpeg")
        
        evidence = EvidenceAsset.objects.create(
            incident=incident,
            asset_type="image",
            file=uploaded_file
        )
        
        # Verify hash was auto-generated for file
        expected_hash = hashlib.sha256(file_content).hexdigest()
        self.assertEqual(evidence.sha256_digest, expected_hash)

    def test_chain_hash_generation(self):
        """Test immutable evidence digest generation."""
        incident = IncidentReport.objects.create(source="web", original_text="Threat")
        EvidenceAsset.objects.create(incident=incident, asset_type="text", derived_text="Asset 1")
        
        chain_hash = incident.generate_chain_hash()
        self.assertEqual(len(chain_hash), 64)
        
        # Changing asset should change hash
        EvidenceAsset.objects.create(incident=incident, asset_type="text", derived_text="Asset 2")
        new_hash = incident.generate_chain_hash()
        self.assertNotEqual(chain_hash, new_hash)

    def test_reasoning_log_persistence(self):
        """Test that the 7-agent reasoning log stores and retrieves correctly."""
        incident = IncidentReport.objects.create(source="web")
        log = [{"agent": "Sentinel", "detail": "All safe"}]
        incident.reasoning_log = log
        incident.save()
        
        incident.refresh_from_db()
        self.assertEqual(incident.reasoning_log[0]["agent"], "Sentinel")

from django.urls import reverse
from django.contrib.auth.models import User
from partners.models import PartnerOrganization, PartnerUser

class CaseViewPermissionsTest(TestCase):
    def setUp(self):
        self.org = PartnerOrganization.objects.create(name="Legal Aid", jurisdiction="Kenya")
        self.partner_user = User.objects.create_user(username="lawyer", password="password")
        self.partner_profile = PartnerUser.objects.create(user=self.partner_user, organization=self.org)
        
        self.other_user = User.objects.create_user(username="other", password="password")
        self.staff_user = User.objects.create_superuser(username="admin", password="password", email="a@b.com")
        
        self.case = IncidentReport.objects.create(source="web", assigned_partner=self.org)

    def test_staff_can_view_case(self):
        self.client.login(username="admin", password="password")
        response = self.client.get(reverse('cases:case_detail', kwargs={'case_id': self.case.case_id}))
        self.assertEqual(response.status_code, 200)

    def test_assigned_partner_can_view_case(self):
        self.client.login(username="lawyer", password="password")
        response = self.client.get(reverse('cases:case_detail', kwargs={'case_id': self.case.case_id}))
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_user_blocked(self):
        self.client.login(username="other", password="password")
        response = self.client.get(reverse('cases:case_detail', kwargs={'case_id': self.case.case_id}))
        self.assertEqual(response.status_code, 403) # Forbidden by test_func
