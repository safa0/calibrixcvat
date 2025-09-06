# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
from unittest import mock
from django.contrib.auth.models import Group, User
from rest_framework import status
from rest_framework.test import APITestCase

from cvat.apps.engine.tests.utils import ApiTestBase, ForceLogin
from cvat.apps.engine.models import Task, Project
from cvat.apps.calibrix_matching.models import ROITemplate, MatchingSession, DetectionResult


class CalibrixMatchingAPITestBase(ApiTestBase):
    """Base test class for Calibrix Matching API tests."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data for the entire test class."""
        cls.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin@test.com',
            password='admin_password'
        )
        cls.admin_user.is_staff = True
        cls.admin_user.is_superuser = True
        cls.admin_user.save()
        
        cls.user = User.objects.create_user(
            username='test_user',
            email='user@test.com',
            password='user_password'
        )
        
        cls.other_user = User.objects.create_user(
            username='other_user',
            email='other@test.com',
            password='other_password'
        )

        # Add users to worker group if it exists
        try:
            worker_group = Group.objects.get(name='worker')
            cls.user.groups.add(worker_group)
            cls.other_user.groups.add(worker_group)
            cls.admin_user.groups.add(worker_group)
        except Group.DoesNotExist:
            pass

        # Create test project and task
        cls.project = Project.objects.create(
            name='Test Project',
            owner=cls.admin_user
        )

        cls.task = Task.objects.create(
            name='Test Task',
            project=cls.project,
            owner=cls.admin_user
        )

        # Create test ROI template
        cls.roi_template = ROITemplate.objects.create(
            name='Test ROI Template',
            task=cls.task,
            coordinates={'x': 100, 'y': 200, 'width': 300, 'height': 400},
            feature_descriptor={
                'algorithm': 'SIFT',
                'keypoints': [[100, 200], [150, 250]],
                'descriptors': [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
            },
            created_by=cls.admin_user
        )


class ROITemplateAPITestCase(CalibrixMatchingAPITestBase):
    """Test cases for ROI Template API endpoints."""

    def setUp(self):
        super().setUp()
        self.roi_templates_url = "/api/calibrix/roi-templates/"

    def test_list_roi_templates_admin(self):
        """Test listing ROI templates as admin user."""
        response = self._get_request(self.roi_templates_url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Test ROI Template')

    def test_list_roi_templates_task_owner(self):
        """Test listing ROI templates as task owner."""
        response = self._get_request(self.roi_templates_url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_roi_templates_unauthorized(self):
        """Test listing ROI templates without authentication."""
        response = self.client.get(self.roi_templates_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_roi_template_valid_data(self):
        """Test creating a new ROI template with valid data."""
        data = {
            'name': 'New ROI Template',
            'task': self.task.id,
            'coordinates': {'x': 50, 'y': 60, 'width': 200, 'height': 300},
            'feature_descriptor': {
                'algorithm': 'ORB',
                'keypoints': [[50, 60], [100, 120]],
                'descriptors': [[0.7, 0.8, 0.9], [1.0, 1.1, 1.2]]
            }
        }
        
        response = self._post_request(
            self.roi_templates_url, 
            self.admin_user.username,
            data=data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New ROI Template')
        self.assertEqual(response.data['task'], self.task.id)

    def test_create_roi_template_invalid_coordinates(self):
        """Test creating ROI template with invalid coordinates."""
        data = {
            'name': 'Invalid ROI Template',
            'task': self.task.id,
            'coordinates': {'x': 50, 'y': 60},  # Missing width and height
            'feature_descriptor': {
                'algorithm': 'SIFT',
                'keypoints': [[50, 60]],
                'descriptors': [[0.7, 0.8, 0.9]]
            }
        }
        
        response = self._post_request(
            self.roi_templates_url, 
            self.admin_user.username,
            data=data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_roi_template_invalid_feature_descriptor(self):
        """Test creating ROI template with invalid feature descriptor."""
        data = {
            'name': 'Invalid Feature ROI Template',
            'task': self.task.id,
            'coordinates': {'x': 50, 'y': 60, 'width': 200, 'height': 300},
            'feature_descriptor': {
                'algorithm': 'SIFT'
                # Missing keypoints and descriptors
            }
        }
        
        response = self._post_request(
            self.roi_templates_url, 
            self.admin_user.username,
            data=data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_roi_template(self):
        """Test retrieving a specific ROI template."""
        url = f"{self.roi_templates_url}{self.roi_template.id}/"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.roi_template.id)
        self.assertEqual(response.data['name'], 'Test ROI Template')

    def test_update_roi_template(self):
        """Test updating an existing ROI template."""
        url = f"{self.roi_templates_url}{self.roi_template.id}/"
        data = {
            'name': 'Updated ROI Template',
            'task': self.task.id,
            'coordinates': {'x': 150, 'y': 250, 'width': 350, 'height': 450},
            'feature_descriptor': {
                'algorithm': 'AKAZE',
                'keypoints': [[150, 250], [200, 300]],
                'descriptors': [[0.2, 0.3, 0.4], [0.5, 0.6, 0.7]]
            }
        }
        
        response = self._put_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated ROI Template')

    def test_partial_update_roi_template(self):
        """Test partially updating an existing ROI template."""
        url = f"{self.roi_templates_url}{self.roi_template.id}/"
        data = {'name': 'Partially Updated ROI Template'}
        
        response = self._patch_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Partially Updated ROI Template')

    def test_delete_roi_template(self):
        """Test deleting an ROI template."""
        url = f"{self.roi_templates_url}{self.roi_template.id}/"
        response = self._delete_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify it's deleted
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_roi_templates_by_task(self):
        """Test filtering ROI templates by task ID."""
        # Create another task and ROI template
        other_task = Task.objects.create(
            name='Other Task',
            project=self.project,
            owner=self.admin_user
        )
        
        ROITemplate.objects.create(
            name='Other ROI Template',
            task=other_task,
            coordinates={'x': 200, 'y': 300, 'width': 400, 'height': 500},
            feature_descriptor={
                'algorithm': 'SURF',
                'keypoints': [[200, 300]],
                'descriptors': [[0.9, 1.0, 1.1]]
            },
            created_by=self.admin_user
        )
        
        # Filter by original task
        url = f"{self.roi_templates_url}?task={self.task.id}"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['task'], self.task.id)

    def test_search_roi_templates_by_name(self):
        """Test searching ROI templates by name."""
        # Create additional ROI templates
        ROITemplate.objects.create(
            name='Search Test Template',
            task=self.task,
            coordinates={'x': 300, 'y': 400, 'width': 500, 'height': 600},
            feature_descriptor={
                'algorithm': 'ORB',
                'keypoints': [[300, 400]],
                'descriptors': [[1.2, 1.3, 1.4]]
            },
            created_by=self.admin_user
        )
        
        # Search by name
        url = f"{self.roi_templates_url}?search=Search"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertIn('Search', response.data['results'][0]['name'])


class MatchingSessionAPITestCase(CalibrixMatchingAPITestBase):
    """Test cases for Matching Session API endpoints."""

    def setUp(self):
        super().setUp()
        self.matching_sessions_url = "/api/calibrix/matching-sessions/"

    def test_list_matching_sessions(self):
        """Test listing matching sessions."""
        # Create test matching session
        matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7
        )
        
        response = self._get_request(self.matching_sessions_url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], matching_session.id)

    def test_create_matching_session(self):
        """Test creating a new matching session."""
        data = {
            'roi_template': self.roi_template.id,
            'task': self.task.id,
            'algorithm_type': 'SIFT',
            'threshold': 0.8
        }
        
        response = self._post_request(
            self.matching_sessions_url, 
            self.admin_user.username,
            data=data
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['roi_template'], self.roi_template.id)
        self.assertEqual(response.data['task'], self.task.id)
        self.assertEqual(response.data['threshold'], 0.8)

    def test_create_matching_session_invalid_threshold(self):
        """Test creating matching session with invalid threshold."""
        data = {
            'roi_template': self.roi_template.id,
            'task': self.task.id,
            'algorithm_type': 'SIFT',
            'threshold': 1.5  # Invalid threshold > 1.0
        }
        
        response = self._post_request(
            self.matching_sessions_url, 
            self.admin_user.username,
            data=data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @mock.patch('cvat.apps.calibrix_matching.services.matching_service.run_matching_task')
    def test_start_matching_session(self):
        """Test starting a matching session."""
        matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7
        )
        
        url = f"{self.matching_sessions_url}{matching_session.id}/start/"
        response = self._post_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rq_id', response.data)

    def test_get_matching_session_status(self):
        """Test getting matching session status."""
        matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7,
            status=MatchingSession.Status.IN_PROGRESS
        )
        
        url = f"{self.matching_sessions_url}{matching_session.id}/"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'IN_PROGRESS')

    def test_cancel_matching_session(self):
        """Test canceling a matching session."""
        matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7,
            status=MatchingSession.Status.IN_PROGRESS
        )
        
        url = f"{self.matching_sessions_url}{matching_session.id}/cancel/"
        response = self._post_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify status is updated
        matching_session.refresh_from_db()
        self.assertEqual(matching_session.status, MatchingSession.Status.FAILED)


class DetectionResultAPITestCase(CalibrixMatchingAPITestBase):
    """Test cases for Detection Result API endpoints."""

    def setUp(self):
        super().setUp()
        self.detections_url = "/api/calibrix/detections/"
        
        # Create test matching session
        self.matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7
        )
        
        # Create test detection results
        self.detection1 = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=0,
            coordinates={'x': 120, 'y': 220, 'width': 280, 'height': 380},
            confidence_score=0.85
        )
        
        self.detection2 = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=1,
            coordinates={'x': 125, 'y': 225, 'width': 275, 'height': 375},
            confidence_score=0.92
        )

    def test_list_detections(self):
        """Test listing detection results."""
        response = self._get_request(self.detections_url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_filter_detections_by_matching_session(self):
        """Test filtering detections by matching session."""
        url = f"{self.detections_url}?matching_session={self.matching_session.id}"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_filter_detections_by_confidence(self):
        """Test filtering detections by minimum confidence score."""
        url = f"{self.detections_url}?min_confidence=0.9"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['confidence_score'], 0.92)

    def test_confirm_detection(self):
        """Test confirming a detection result."""
        url = f"{self.detections_url}{self.detection1.id}/confirm/"
        response = self._post_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify detection is confirmed
        self.detection1.refresh_from_db()
        self.assertTrue(self.detection1.is_confirmed)

    def test_get_detection_details(self):
        """Test retrieving detection details."""
        url = f"{self.detections_url}{self.detection1.id}/"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.detection1.id)
        self.assertEqual(response.data['frame_number'], 0)

    def test_bulk_confirm_detections(self):
        """Test bulk confirming multiple detections."""
        url = f"{self.detections_url}bulk_confirm/"
        data = {
            'detection_ids': [self.detection1.id, self.detection2.id]
        }
        
        response = self._post_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify both detections are confirmed
        self.detection1.refresh_from_db()
        self.detection2.refresh_from_db()
        self.assertTrue(self.detection1.is_confirmed)
        self.assertTrue(self.detection2.is_confirmed)


class GroundTruthAPITestCase(CalibrixMatchingAPITestBase):
    """Test cases for Ground Truth export API endpoints."""

    def setUp(self):
        super().setUp()
        self.ground_truth_url = "/api/calibrix/ground-truth/"
        
        # Create test data
        self.matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7
        )
        
        # Create confirmed detection
        DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=0,
            coordinates={'x': 120, 'y': 220, 'width': 280, 'height': 380},
            confidence_score=0.85,
            is_confirmed=True
        )

    def test_export_ground_truth_csv(self):
        """Test exporting ground truth data as CSV."""
        url = f"{self.ground_truth_url}export/"
        data = {
            'task': self.task.id,
            'format': 'csv'
        }
        
        response = self._post_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rq_id', response.data)

    def test_export_ground_truth_json(self):
        """Test exporting ground truth data as JSON."""
        url = f"{self.ground_truth_url}export/"
        data = {
            'task': self.task.id,
            'format': 'json'
        }
        
        response = self._post_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('rq_id', response.data)

    def test_export_ground_truth_invalid_task(self):
        """Test exporting ground truth with invalid task ID."""
        url = f"{self.ground_truth_url}export/"
        data = {
            'task': 99999,  # Non-existent task
            'format': 'csv'
        }
        
        response = self._post_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_export_status(self):
        """Test getting export job status."""
        # This would normally involve creating a background job
        # For now, test the endpoint structure
        url = f"{self.ground_truth_url}status/"
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class CalibrixPermissionsTestCase(CalibrixMatchingAPITestBase):
    """Test cases for Calibrix API permissions."""

    def test_roi_template_access_permissions(self):
        """Test access permissions for ROI templates."""
        url = f"/api/calibrix/roi-templates/{self.roi_template.id}/"
        
        # Admin should have access
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Task owner should have access
        response = self._get_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Other user should not have access
        response = self._get_request(url, self.other_user.username)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_matching_session_creation_permissions(self):
        """Test permissions for creating matching sessions."""
        url = "/api/calibrix/matching-sessions/"
        data = {
            'roi_template': self.roi_template.id,
            'task': self.task.id,
            'algorithm_type': 'SIFT',
            'threshold': 0.8
        }
        
        # Admin should be able to create
        response = self._post_request(url, self.admin_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Other user should not be able to create
        response = self._post_request(url, self.other_user.username, data=data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_detection_confirmation_permissions(self):
        """Test permissions for confirming detections."""
        matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type=MatchingSession.AlgorithmType.SIFT,
            threshold=0.7
        )
        
        detection = DetectionResult.objects.create(
            matching_session=matching_session,
            frame_number=0,
            coordinates={'x': 120, 'y': 220, 'width': 280, 'height': 380},
            confidence_score=0.85
        )
        
        url = f"/api/calibrix/detections/{detection.id}/confirm/"
        
        # Admin should be able to confirm
        response = self._post_request(url, self.admin_user.username)
        self.assertEqual(response.status_code, status.HTTP_200_OK)