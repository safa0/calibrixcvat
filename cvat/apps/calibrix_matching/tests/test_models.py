# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from cvat.apps.engine.models import Task
from cvat.apps.calibrix_matching.models import (
    ROITemplate, MatchingSession, DetectionResult
)


class ROITemplateModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Create a minimal task for foreign key relationship
        self.task = Task.objects.create(
            name='Test Task',
            owner=self.user,
            mode='annotation'
        )
        self.valid_coordinates = {
            'x': 100,
            'y': 200,
            'width': 300,
            'height': 400
        }
        self.valid_feature_descriptor = {
            'algorithm': 'SIFT',
            'keypoints': [
                {'x': 150, 'y': 250, 'size': 10, 'angle': 45.0, 'response': 0.8},
                {'x': 200, 'y': 300, 'size': 8, 'angle': 90.0, 'response': 0.6}
            ],
            'descriptors': [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
        }

    def test_roi_template_creation(self):
        """Test successful creation of ROITemplate."""
        roi = ROITemplate.objects.create(
            name='Test ROI',
            task=self.task,
            coordinates=self.valid_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        self.assertEqual(roi.name, 'Test ROI')
        self.assertEqual(roi.task, self.task)
        self.assertEqual(roi.coordinates, self.valid_coordinates)
        self.assertEqual(roi.feature_descriptor, self.valid_feature_descriptor)
        self.assertEqual(roi.created_by, self.user)
        self.assertIsNotNone(roi.created_at)

    def test_roi_template_str_representation(self):
        """Test string representation of ROITemplate."""
        roi = ROITemplate.objects.create(
            name='Test ROI',
            task=self.task,
            coordinates=self.valid_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        expected_str = f"ROI Template: Test ROI (Task: {self.task.name})"
        self.assertEqual(str(roi), expected_str)

    def test_roi_template_name_required(self):
        """Test that name field is required."""
        with self.assertRaises(IntegrityError):
            ROITemplate.objects.create(
                task=self.task,
                coordinates=self.valid_coordinates,
                feature_descriptor=self.valid_feature_descriptor,
                created_by=self.user
            )

    def test_roi_template_task_required(self):
        """Test that task field is required."""
        with self.assertRaises(IntegrityError):
            ROITemplate.objects.create(
                name='Test ROI',
                coordinates=self.valid_coordinates,
                feature_descriptor=self.valid_feature_descriptor,
                created_by=self.user
            )

    def test_roi_template_coordinates_required(self):
        """Test that coordinates field is required."""
        with self.assertRaises(IntegrityError):
            ROITemplate.objects.create(
                name='Test ROI',
                task=self.task,
                feature_descriptor=self.valid_feature_descriptor,
                created_by=self.user
            )

    def test_roi_template_feature_descriptor_required(self):
        """Test that feature_descriptor field is required."""
        with self.assertRaises(IntegrityError):
            ROITemplate.objects.create(
                name='Test ROI',
                task=self.task,
                coordinates=self.valid_coordinates,
                created_by=self.user
            )

    def test_roi_template_created_by_required(self):
        """Test that created_by field is required."""
        with self.assertRaises(IntegrityError):
            ROITemplate.objects.create(
                name='Test ROI',
                task=self.task,
                coordinates=self.valid_coordinates,
                feature_descriptor=self.valid_feature_descriptor
            )

    def test_roi_template_coordinates_validation(self):
        """Test validation of coordinates field."""
        invalid_coordinates = {'x': 'invalid', 'y': 200}
        roi = ROITemplate(
            name='Test ROI',
            task=self.task,
            coordinates=invalid_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            roi.full_clean()

    def test_roi_template_coordinates_required_fields(self):
        """Test that coordinates must have required fields."""
        incomplete_coordinates = {'x': 100, 'y': 200}  # missing width, height
        roi = ROITemplate(
            name='Test ROI',
            task=self.task,
            coordinates=incomplete_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            roi.full_clean()

    def test_roi_template_feature_descriptor_validation(self):
        """Test validation of feature_descriptor field."""
        invalid_descriptor = {'algorithm': 'SIFT'}  # missing required fields
        roi = ROITemplate(
            name='Test ROI',
            task=self.task,
            coordinates=self.valid_coordinates,
            feature_descriptor=invalid_descriptor,
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            roi.full_clean()

    def test_roi_template_name_max_length(self):
        """Test name field maximum length."""
        long_name = 'x' * 256  # Assuming max length is 255
        roi = ROITemplate(
            name=long_name,
            task=self.task,
            coordinates=self.valid_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        with self.assertRaises(ValidationError):
            roi.full_clean()

    def test_roi_template_cascade_delete_with_task(self):
        """Test that ROI template is deleted when task is deleted."""
        roi = ROITemplate.objects.create(
            name='Test ROI',
            task=self.task,
            coordinates=self.valid_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        task_id = self.task.id
        roi_id = roi.id
        
        self.task.delete()
        
        with self.assertRaises(ROITemplate.DoesNotExist):
            ROITemplate.objects.get(id=roi_id)

    def test_roi_template_set_null_on_user_delete(self):
        """Test that created_by is set to null when user is deleted."""
        roi = ROITemplate.objects.create(
            name='Test ROI',
            task=self.task,
            coordinates=self.valid_coordinates,
            feature_descriptor=self.valid_feature_descriptor,
            created_by=self.user
        )
        user_id = self.user.id
        roi_id = roi.id
        
        self.user.delete()
        
        roi.refresh_from_db()
        self.assertIsNone(roi.created_by)


class MatchingSessionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.task = Task.objects.create(
            name='Test Task',
            owner=self.user,
            mode='annotation'
        )
        self.roi_template = ROITemplate.objects.create(
            name='Test ROI',
            task=self.task,
            coordinates={'x': 100, 'y': 200, 'width': 300, 'height': 400},
            feature_descriptor={
                'algorithm': 'SIFT',
                'keypoints': [{'x': 150, 'y': 250, 'size': 10}],
                'descriptors': [[0.1, 0.2, 0.3]]
            },
            created_by=self.user
        )

    def test_matching_session_creation(self):
        """Test successful creation of MatchingSession."""
        session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8,
            status='PENDING'
        )
        self.assertEqual(session.roi_template, self.roi_template)
        self.assertEqual(session.task, self.task)
        self.assertEqual(session.algorithm_type, 'SIFT')
        self.assertEqual(session.threshold, 0.8)
        self.assertEqual(session.status, 'PENDING')
        self.assertIsNotNone(session.created_at)
        self.assertIsNotNone(session.updated_at)

    def test_matching_session_str_representation(self):
        """Test string representation of MatchingSession."""
        session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8,
            status='PENDING'
        )
        expected_str = f"Matching Session: {session.id} (ROI: {self.roi_template.name}, Status: PENDING)"
        self.assertEqual(str(session), expected_str)

    def test_matching_session_required_fields(self):
        """Test that all required fields are enforced."""
        with self.assertRaises(IntegrityError):
            MatchingSession.objects.create(
                task=self.task,
                algorithm_type='SIFT',
                threshold=0.8,
                status='PENDING'
            )  # missing roi_template

    def test_matching_session_default_status(self):
        """Test default status is PENDING."""
        session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8
            # status not provided
        )
        self.assertEqual(session.status, 'PENDING')

    def test_matching_session_threshold_validation(self):
        """Test threshold validation (should be between 0 and 1)."""
        session = MatchingSession(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=1.5,  # Invalid threshold > 1
            status='PENDING'
        )
        with self.assertRaises(ValidationError):
            session.full_clean()

    def test_matching_session_negative_threshold(self):
        """Test negative threshold validation."""
        session = MatchingSession(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=-0.1,  # Invalid negative threshold
            status='PENDING'
        )
        with self.assertRaises(ValidationError):
            session.full_clean()

    def test_matching_session_algorithm_choices(self):
        """Test algorithm_type choices validation."""
        session = MatchingSession(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='INVALID_ALGORITHM',
            threshold=0.8,
            status='PENDING'
        )
        with self.assertRaises(ValidationError):
            session.full_clean()

    def test_matching_session_status_choices(self):
        """Test status choices validation."""
        session = MatchingSession(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8,
            status='INVALID_STATUS'
        )
        with self.assertRaises(ValidationError):
            session.full_clean()

    def test_matching_session_cascade_delete_roi_template(self):
        """Test cascade delete when ROI template is deleted."""
        session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8,
            status='PENDING'
        )
        session_id = session.id
        
        self.roi_template.delete()
        
        with self.assertRaises(MatchingSession.DoesNotExist):
            MatchingSession.objects.get(id=session_id)

    def test_matching_session_cascade_delete_task(self):
        """Test cascade delete when task is deleted."""
        session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8,
            status='PENDING'
        )
        session_id = session.id
        
        self.task.delete()
        
        with self.assertRaises(MatchingSession.DoesNotExist):
            MatchingSession.objects.get(id=session_id)


class DetectionResultModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.task = Task.objects.create(
            name='Test Task',
            owner=self.user,
            mode='annotation'
        )
        self.roi_template = ROITemplate.objects.create(
            name='Test ROI',
            task=self.task,
            coordinates={'x': 100, 'y': 200, 'width': 300, 'height': 400},
            feature_descriptor={
                'algorithm': 'SIFT',
                'keypoints': [{'x': 150, 'y': 250, 'size': 10}],
                'descriptors': [[0.1, 0.2, 0.3]]
            },
            created_by=self.user
        )
        self.matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.8,
            status='PENDING'
        )
        self.valid_coordinates = {
            'x': 150,
            'y': 250,
            'width': 200,
            'height': 300
        }

    def test_detection_result_creation(self):
        """Test successful creation of DetectionResult."""
        result = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        self.assertEqual(result.matching_session, self.matching_session)
        self.assertEqual(result.frame_number, 42)
        self.assertEqual(result.coordinates, self.valid_coordinates)
        self.assertEqual(result.confidence_score, 0.85)
        self.assertFalse(result.is_confirmed)
        self.assertIsNotNone(result.created_at)

    def test_detection_result_str_representation(self):
        """Test string representation of DetectionResult."""
        result = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        expected_str = f"Detection Result: Frame {result.frame_number}, Score: {result.confidence_score:.2f}"
        self.assertEqual(str(result), expected_str)

    def test_detection_result_required_fields(self):
        """Test that all required fields are enforced."""
        with self.assertRaises(IntegrityError):
            DetectionResult.objects.create(
                frame_number=42,
                coordinates=self.valid_coordinates,
                confidence_score=0.85,
                is_confirmed=False
            )  # missing matching_session

    def test_detection_result_default_is_confirmed(self):
        """Test default value for is_confirmed is False."""
        result = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=0.85
            # is_confirmed not provided
        )
        self.assertFalse(result.is_confirmed)

    def test_detection_result_frame_number_validation(self):
        """Test frame number validation (should be non-negative)."""
        result = DetectionResult(
            matching_session=self.matching_session,
            frame_number=-1,  # Invalid negative frame number
            coordinates=self.valid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_detection_result_confidence_score_validation(self):
        """Test confidence score validation (should be between 0 and 1)."""
        result = DetectionResult(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=1.5,  # Invalid score > 1
            is_confirmed=False
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_detection_result_negative_confidence_score(self):
        """Test negative confidence score validation."""
        result = DetectionResult(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=-0.1,  # Invalid negative score
            is_confirmed=False
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_detection_result_coordinates_validation(self):
        """Test coordinates field validation."""
        invalid_coordinates = {'x': 'invalid', 'y': 250}
        result = DetectionResult(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=invalid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_detection_result_coordinates_required_fields(self):
        """Test that coordinates must have required fields."""
        incomplete_coordinates = {'x': 150, 'y': 250}  # missing width, height
        result = DetectionResult(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=incomplete_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        with self.assertRaises(ValidationError):
            result.full_clean()

    def test_detection_result_cascade_delete_matching_session(self):
        """Test cascade delete when matching session is deleted."""
        result = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        result_id = result.id
        
        self.matching_session.delete()
        
        with self.assertRaises(DetectionResult.DoesNotExist):
            DetectionResult.objects.get(id=result_id)

    def test_detection_result_unique_per_session_frame(self):
        """Test that detection results are unique per session and frame."""
        # Create first result
        DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=42,
            coordinates=self.valid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        
        # Try to create another result for same session and frame
        with self.assertRaises(IntegrityError):
            DetectionResult.objects.create(
                matching_session=self.matching_session,
                frame_number=42,  # Same frame number
                coordinates={'x': 200, 'y': 300, 'width': 150, 'height': 200},
                confidence_score=0.75,
                is_confirmed=False
            )

    def test_detection_result_ordering(self):
        """Test default ordering by frame number."""
        # Create results in random order
        result2 = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=100,
            coordinates=self.valid_coordinates,
            confidence_score=0.85,
            is_confirmed=False
        )
        result1 = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=50,
            coordinates=self.valid_coordinates,
            confidence_score=0.75,
            is_confirmed=False
        )
        result3 = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=150,
            coordinates=self.valid_coordinates,
            confidence_score=0.90,
            is_confirmed=False
        )
        
        # Check they are ordered by frame number
        results = list(DetectionResult.objects.all())
        self.assertEqual(results, [result1, result2, result3])