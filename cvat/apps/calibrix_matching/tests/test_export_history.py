# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch

import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from cvat.apps.engine.models import Task
from ..models import ROITemplate, MatchingSession, DetectionResult, ExportHistory, ExportDownload
from ..services.export_history_service import ExportHistoryService
from ..services.enhanced_export_service import EnhancedGroundTruthExportService
from ..services.ground_truth_export import ExportConfig


class ExportHistoryTestCase(TestCase):
    """Base test case for export history functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test task
        self.task = Task.objects.create(
            name='Test Export History Task',
            organization_id=None,
            owner=self.user,
            mode='annotation'
        )
        
        # Create test ROI template
        self.roi_template = ROITemplate.objects.create(
            name='Test ROI Template',
            task=self.task,
            coordinates={'x': 100, 'y': 100, 'width': 200, 'height': 150},
            feature_descriptor={
                'algorithm': 'SIFT',
                'keypoints': [],
                'descriptors': []
            },
            created_by=self.user
        )
        
        # Create test matching session
        self.matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.7,
            status='COMPLETED'
        )
        
        # Create sample detection results
        self.detections = []
        for i in range(20):
            detection = DetectionResult.objects.create(
                matching_session=self.matching_session,
                frame_number=i * 5,
                coordinates={
                    'x': 100 + i * 10,
                    'y': 100 + i * 5,
                    'width': 80 + i * 2,
                    'height': 60 + i * 2
                },
                confidence_score=0.8 + i * 0.01,
                is_confirmed=i % 3 == 0
            )
            self.detections.append(detection)
        
        # Create export history service
        self.history_service = ExportHistoryService(self.task.id)


class TestExportHistoryModel(ExportHistoryTestCase):
    """Test ExportHistory model functionality."""
    
    def test_export_history_creation(self):
        """Test creating export history records."""
        config = ExportConfig(export_format='coco', confirmed_only=True)
        
        export_record = self.history_service.create_export_record(
            export_format='coco',
            config=config,
            user=self.user
        )
        
        self.assertIsNotNone(export_record.export_id)
        self.assertEqual(export_record.task, self.task)
        self.assertEqual(export_record.created_by, self.user)
        self.assertEqual(export_record.export_format, 'coco')
        self.assertEqual(export_record.status, ExportHistory.ExportStatus.PENDING)
        self.assertGreater(export_record.total_detections, 0)
        self.assertTrue(export_record.confirmed_detections_only)
    
    def test_export_history_status_transitions(self):
        """Test export status transitions and automatic field updates."""
        config = ExportConfig(export_format='csv')
        export_record = self.history_service.create_export_record('csv', config, self.user)
        
        # Test marking as started
        export_record.mark_as_started()
        export_record.refresh_from_db()
        
        self.assertEqual(export_record.status, ExportHistory.ExportStatus.IN_PROGRESS)
        self.assertIsNotNone(export_record.started_at)
        
        # Test marking as completed
        test_path = '/tmp/test_export.csv'
        export_record.mark_as_completed(test_path, file_size=1024)
        export_record.refresh_from_db()
        
        self.assertEqual(export_record.status, ExportHistory.ExportStatus.COMPLETED)
        self.assertEqual(export_record.export_path, test_path)
        self.assertEqual(export_record.file_size_bytes, 1024)
        self.assertIsNotNone(export_record.completed_at)
        self.assertIsNotNone(export_record.duration_seconds)
        self.assertIsNotNone(export_record.processing_rate)
    
    def test_export_history_properties(self):
        """Test export history computed properties."""
        config = ExportConfig(export_format='yolo')
        export_record = self.history_service.create_export_record('yolo', config, self.user)
        
        # Test initial properties
        self.assertFalse(export_record.is_successful)
        self.assertFalse(export_record.is_in_progress)
        self.assertFalse(export_record.has_failed)
        
        # Test in progress
        export_record.mark_as_started()
        self.assertTrue(export_record.is_in_progress)
        
        # Test completed
        export_record.mark_as_completed('/tmp/test.zip', 2048)
        self.assertTrue(export_record.is_successful)
        self.assertFalse(export_record.is_in_progress)
        self.assertEqual(export_record.file_size_mb, 2048 / (1024 * 1024))
    
    def test_export_summary(self):
        """Test export summary generation."""
        config = ExportConfig(export_format='pascal_voc')
        export_record = self.history_service.create_export_record('pascal_voc', config, self.user)
        export_record.mark_as_completed('/tmp/test.xml', 512)
        
        summary = export_record.get_export_summary()
        
        required_fields = [
            'export_id', 'format', 'status', 'total_detections',
            'file_size_mb', 'duration_seconds', 'created_at', 'completed_at'
        ]
        
        for field in required_fields:
            self.assertIn(field, summary)
        
        self.assertEqual(summary['format'], 'pascal_voc')
        self.assertEqual(summary['status'], ExportHistory.ExportStatus.COMPLETED)


class TestExportHistoryService(ExportHistoryTestCase):
    """Test ExportHistoryService functionality."""
    
    def test_create_export_record_with_parent(self):
        """Test creating incremental export records."""
        # Create base export
        config = ExportConfig(export_format='coco')
        base_export = self.history_service.create_export_record('coco', config, self.user)
        base_export.mark_as_completed('/tmp/base.json', 1024)
        
        # Create incremental export
        incremental_export = self.history_service.create_export_record(
            export_format='coco',
            config=config,
            user=self.user,
            parent_export_id=base_export.export_id
        )
        
        self.assertTrue(incremental_export.is_incremental)
        self.assertEqual(incremental_export.parent_export, base_export)
    
    def test_get_export_history_filtering(self):
        """Test export history retrieval with filters."""
        # Create various exports
        configs = [
            ExportConfig(export_format='coco'),
            ExportConfig(export_format='yolo'),
            ExportConfig(export_format='csv'),
        ]
        
        exports = []
        for i, config in enumerate(configs):
            export = self.history_service.create_export_record(
                config.export_format, config, self.user
            )
            if i == 0:
                export.mark_as_completed(f'/tmp/test{i}.json', 1024)
            elif i == 1:
                export.mark_as_failed('Test error')
            exports.append(export)
        
        # Test format filtering
        coco_exports = self.history_service.get_export_history(format_filter='coco')
        self.assertEqual(len(coco_exports), 1)
        self.assertEqual(coco_exports[0].export_format, 'coco')
        
        # Test status filtering
        completed_exports = self.history_service.get_export_history(
            status_filter=ExportHistory.ExportStatus.COMPLETED
        )
        self.assertEqual(len(completed_exports), 1)
        self.assertTrue(completed_exports[0].is_successful)
        
        # Test user filtering
        user_exports = self.history_service.get_export_history(user_filter=self.user)
        self.assertEqual(len(user_exports), 3)
    
    def test_find_similar_exports(self):
        """Test finding similar exports."""
        config = ExportConfig(
            export_format='coco',
            confirmed_only=True,
            min_confidence=0.8
        )
        
        # Create a completed export
        export1 = self.history_service.create_export_record('coco', config, self.user)
        export1.mark_as_completed('/tmp/similar1.json', 1024)
        
        # Find similar exports
        similar = self.history_service.find_similar_exports(config, time_window_hours=1)
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0].export_id, export1.export_id)
        
        # Test with different config (should not match)
        different_config = ExportConfig(export_format='yolo', confirmed_only=True)
        similar_different = self.history_service.find_similar_exports(different_config)
        self.assertEqual(len(similar_different), 0)
    
    def test_calculate_export_diff(self):
        """Test calculating differences between exports."""
        config = ExportConfig(export_format='coco', confirmed_only=True)
        
        # Create base export
        base_export = self.history_service.create_export_record('coco', config, self.user)
        base_export.mark_as_completed('/tmp/base.json', 1024)
        
        # Create new detections after base export
        new_detection = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=999,
            coordinates={'x': 500, 'y': 500, 'width': 100, 'height': 100},
            confidence_score=0.9,
            is_confirmed=True
        )
        
        # Calculate diff
        diff_info = self.history_service.calculate_export_diff(
            base_export.export_id, config
        )
        
        self.assertIn('base_export_id', diff_info)
        self.assertIn('base_detection_count', diff_info)
        self.assertIn('current_detection_count', diff_info)
        self.assertIn('new_detections_since_base', diff_info)
        self.assertIn('change_percentage', diff_info)
        self.assertGreater(diff_info['new_detections_since_base'], 0)
    
    def test_export_statistics(self):
        """Test export statistics generation."""
        # Create various exports
        configs_and_statuses = [
            (ExportConfig(export_format='coco'), ExportHistory.ExportStatus.COMPLETED),
            (ExportConfig(export_format='yolo'), ExportHistory.ExportStatus.FAILED),
            (ExportConfig(export_format='csv'), ExportHistory.ExportStatus.IN_PROGRESS),
        ]
        
        for config, status in configs_and_statuses:
            export = self.history_service.create_export_record(
                config.export_format, config, self.user
            )
            if status == ExportHistory.ExportStatus.COMPLETED:
                export.mark_as_completed('/tmp/test.json', 1024)
            elif status == ExportHistory.ExportStatus.FAILED:
                export.mark_as_failed('Test error')
            elif status == ExportHistory.ExportStatus.IN_PROGRESS:
                export.mark_as_started()
        
        stats = self.history_service.get_export_statistics()
        
        # Verify required statistics fields
        required_fields = [
            'task_id', 'task_name', 'total_exports', 'successful_exports',
            'failed_exports', 'in_progress_exports', 'success_rate',
            'format_distribution', 'user_activity', 'performance_statistics'
        ]
        
        for field in required_fields:
            self.assertIn(field, stats)
        
        self.assertEqual(stats['total_exports'], 3)
        self.assertEqual(stats['successful_exports'], 1)
        self.assertEqual(stats['failed_exports'], 1)
        self.assertEqual(stats['in_progress_exports'], 1)
        self.assertAlmostEqual(stats['success_rate'], 33.33, places=1)
    
    def test_cleanup_operations(self):
        """Test archive and cleanup operations."""
        # Create old export
        config = ExportConfig(export_format='csv')
        old_export = self.history_service.create_export_record('csv', config, self.user)
        old_export.mark_as_completed('/tmp/old.csv', 512)
        
        # Manually set old creation date
        old_date = timezone.now() - timedelta(days=35)
        ExportHistory.objects.filter(id=old_export.id).update(created_at=old_date)
        
        # Test archival
        archived_count = self.history_service.archive_old_exports(days_old=30)
        self.assertEqual(archived_count, 1)
        
        old_export.refresh_from_db()
        self.assertTrue(old_export.is_archived)
        self.assertIsNotNone(old_export.archived_at)


class TestEnhancedExportService(ExportHistoryTestCase):
    """Test EnhancedGroundTruthExportService functionality."""
    
    def setUp(self):
        super().setUp()
        self.enhanced_service = EnhancedGroundTruthExportService(self.task.id)
    
    @patch('cvat.apps.calibrix_matching.services.ground_truth_export.GroundTruthExportService.export')
    def test_export_with_history_tracking(self, mock_export):
        """Test export with automatic history tracking."""
        mock_export.return_value = {
            'status': 'completed',
            'export_path': '/tmp/test_export.csv',
            'total_detections': 10,
            'duration_seconds': 1.5
        }
        
        config = ExportConfig(export_format='csv', confirmed_only=False)
        
        result = self.enhanced_service.export_with_history(
            config=config,
            user=self.user,
            check_duplicates=False
        )
        
        # Verify result contains history information
        self.assertIn('export_id', result)
        self.assertIn('export_history', result)
        self.assertTrue(result.get('history_tracked', False))
        
        # Verify export record was created
        export_records = ExportHistory.objects.filter(task=self.task)
        self.assertEqual(export_records.count(), 1)
        
        export_record = export_records.first()
        self.assertEqual(export_record.export_format, 'csv')
        self.assertEqual(export_record.created_by, self.user)
        self.assertTrue(export_record.is_successful)
    
    def test_duplicate_detection(self):
        """Test duplicate export detection."""
        config = ExportConfig(export_format='coco', confirmed_only=True)
        
        # Create a recent similar export
        recent_export = self.history_service.create_export_record('coco', config, self.user)
        recent_export.mark_as_completed('/tmp/recent.json', 1024)
        
        # Try to export with duplicate checking
        result = self.enhanced_service.export_with_history(
            config=config,
            user=self.user,
            check_duplicates=True
        )
        
        self.assertEqual(result['status'], 'duplicate_found')
        self.assertIn('similar_exports', result)
        self.assertGreater(len(result['similar_exports']), 0)
    
    def test_export_recommendations(self):
        """Test export recommendation system."""
        config = ExportConfig(
            export_format='yolo',
            compression_format='none',  # Should trigger compression recommendation
            include_images=True  # Should trigger performance recommendation for large datasets
        )
        
        recommendations = self.enhanced_service.get_export_recommendations(config)
        
        # Verify recommendation structure
        required_sections = ['config_suggestions', 'performance_tips', 'similar_exports', 'incremental_candidates']
        for section in required_sections:
            self.assertIn(section, recommendations)
        
        # Should have compression recommendation for YOLO format
        compression_suggestions = [
            s for s in recommendations['config_suggestions']
            if s.get('type') == 'compression'
        ]
        self.assertGreater(len(compression_suggestions), 0)
    
    def test_export_validation(self):
        """Test export configuration validation."""
        # Valid configuration
        valid_config = ExportConfig(
            export_format='coco',
            confirmed_only=True,
            min_confidence=0.8
        )
        
        validation_result = self.enhanced_service.validate_export_config(valid_config)
        self.assertTrue(validation_result['is_valid'])
        self.assertEqual(len(validation_result['errors']), 0)
        
        # Invalid configuration
        invalid_config = ExportConfig(
            export_format='coco',
            min_confidence=1.5  # Invalid - should be <= 1.0
        )
        
        validation_result = self.enhanced_service.validate_export_config(invalid_config)
        self.assertFalse(validation_result['is_valid'])
        self.assertGreater(len(validation_result['errors']), 0)
    
    def test_export_progress_tracking(self):
        """Test export progress tracking."""
        config = ExportConfig(export_format='csv')
        export_record = self.history_service.create_export_record('csv', config, self.user)
        
        # Test pending status
        progress = self.enhanced_service.get_export_progress(export_record.export_id)
        self.assertEqual(progress['status'], ExportHistory.ExportStatus.PENDING)
        
        # Test in progress status
        export_record.mark_as_started()
        progress = self.enhanced_service.get_export_progress(export_record.export_id)
        self.assertEqual(progress['status'], ExportHistory.ExportStatus.IN_PROGRESS)
        self.assertIn('elapsed_seconds', progress)
        self.assertIn('estimated_remaining_seconds', progress)
    
    def test_export_cancellation(self):
        """Test export cancellation."""
        config = ExportConfig(export_format='yolo')
        export_record = self.history_service.create_export_record('yolo', config, self.user)
        export_record.mark_as_started()
        
        # Cancel the export
        success = self.enhanced_service.cancel_export(export_record.export_id, self.user)
        self.assertTrue(success)
        
        export_record.refresh_from_db()
        self.assertEqual(export_record.status, ExportHistory.ExportStatus.CANCELLED)
        self.assertIn('Cancelled by user', export_record.error_message)
        
        # Try to cancel already completed export (should fail)
        completed_export = self.history_service.create_export_record('csv', config, self.user)
        completed_export.mark_as_completed('/tmp/completed.csv', 1024)
        
        success = self.enhanced_service.cancel_export(completed_export.export_id, self.user)
        self.assertFalse(success)


class TestExportDownload(ExportHistoryTestCase):
    """Test export download tracking."""
    
    def test_download_recording(self):
        """Test recording download events."""
        config = ExportConfig(export_format='coco')
        export_record = self.history_service.create_export_record('coco', config, self.user)
        export_record.mark_as_completed('/tmp/test.json', 2048)
        
        # Record download
        download = self.history_service.record_download(
            export_id=export_record.export_id,
            user=self.user,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0 Test',
            bytes_served=2048,
            completed=True
        )
        
        self.assertEqual(download.export_history, export_record)
        self.assertEqual(download.downloaded_by, self.user)
        self.assertEqual(download.download_ip, '192.168.1.1')
        self.assertEqual(download.bytes_served, 2048)
        self.assertTrue(download.download_completed)
    
    def test_download_statistics(self):
        """Test download statistics generation."""
        config = ExportConfig(export_format='csv')
        export_record = self.history_service.create_export_record('csv', config, self.user)
        export_record.mark_as_completed('/tmp/test.csv', 1024)
        
        # Record multiple downloads
        for i in range(3):
            self.history_service.record_download(
                export_id=export_record.export_id,
                user=self.user if i < 2 else None,  # Mix of authenticated and anonymous
                bytes_served=1024,
                completed=i != 2  # Last download incomplete
            )
        
        stats = self.history_service.get_download_statistics(export_record.export_id)
        
        self.assertEqual(stats['total_downloads'], 3)
        self.assertEqual(stats['completed_downloads'], 2)
        self.assertAlmostEqual(stats['completion_rate'], 66.67, places=1)
        self.assertEqual(stats['unique_users'], 1)  # Only authenticated users counted
        self.assertEqual(stats['total_bytes_served'], 3072)  # 3 * 1024


if __name__ == '__main__':
    pytest.main([__file__])