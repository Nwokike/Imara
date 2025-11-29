from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import IncidentReport, EvidenceAsset

class IncidentReportTest(TestCase):
    def setUp(self):
        self.report = IncidentReport.objects.create(
            source='web',
            original_text="This is a test report for harassment.",
            reporter_email="test@example.com"
        )

    def test_report_creation(self):
        """Test that a report is correctly saved with a UUID"""
        self.assertTrue(isinstance(self.report, IncidentReport))
        self.assertIsNotNone(self.report.case_id)
        self.assertEqual(self.report.action, 'pending')

    def test_chain_hash_generation(self):
        """Test that the SHA-256 chain hash is generated automatically"""
        self.assertIsNotNone(self.report.chain_hash)
        self.assertEqual(len(self.report.chain_hash), 64)  # SHA-256 is 64 chars

class EvidenceAssetTest(TestCase):
    def setUp(self):
        self.report = IncidentReport.objects.create(source='web')

    def test_text_evidence_hashing(self):
        """Test that text evidence generates a correct SHA-256 hash"""
        evidence = EvidenceAsset.objects.create(
            incident=self.report,
            asset_type='text',
            derived_text="Evidence text content"
        )
        evidence.generate_hash()
        evidence.save()
        
        self.assertIsNotNone(evidence.sha256_digest)
        self.assertEqual(len(evidence.sha256_digest), 64)

    def test_file_evidence_hashing(self):
        """Test that file uploads are hashed correctly"""
        dummy_file = SimpleUploadedFile("test_audio.mp3", b"dummy audio content")
        evidence = EvidenceAsset.objects.create(
            incident=self.report,
            asset_type='audio',
            file=dummy_file
        )
        evidence.generate_hash()
        evidence.save()
        
        self.assertIsNotNone(evidence.sha256_digest)
