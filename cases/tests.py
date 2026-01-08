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
