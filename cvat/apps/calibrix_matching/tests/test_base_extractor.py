# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import unittest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
import pytest

from cvat.apps.calibrix_matching.algorithms.base import FeatureExtractor, MatchResult


class TestFeatureExtractor(unittest.TestCase):
    """Test suite for FeatureExtractor base class"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock concrete implementation of FeatureExtractor
        self.mock_extractor = Mock(spec=FeatureExtractor)
        self.mock_extractor.algorithm_name = "TestMatcher"
        
        # Create test images
        self.test_image1 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        self.test_image2 = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Create test keypoints and descriptors
        self.test_keypoints1 = [cv2.KeyPoint(x=10, y=20, size=5), cv2.KeyPoint(x=30, y=40, size=7)]
        self.test_keypoints2 = [cv2.KeyPoint(x=15, y=25, size=6), cv2.KeyPoint(x=35, y=45, size=8)]
        
        self.test_descriptors1 = np.random.rand(2, 128).astype(np.float32)
        self.test_descriptors2 = np.random.rand(2, 128).astype(np.float32)

    def test_feature_extractor_abstract_methods(self):
        """Test that FeatureExtractor cannot be instantiated directly"""
        with self.assertRaises(TypeError):
            FeatureExtractor()

    def test_algorithm_name_property(self):
        """Test algorithm_name is properly defined"""
        self.assertEqual(self.mock_extractor.algorithm_name, "TestMatcher")

    def test_extract_features_interface(self):
        """Test extract_features method interface"""
        # Mock the extract_features method
        expected_result = (self.test_keypoints1, self.test_descriptors1)
        self.mock_extractor.extract_features.return_value = expected_result
        
        result = self.mock_extractor.extract_features(self.test_image1)
        
        self.mock_extractor.extract_features.assert_called_once_with(self.test_image1)
        self.assertEqual(result, expected_result)

    def test_match_features_interface(self):
        """Test match_features method interface"""
        # Mock match_features method
        expected_matches = [cv2.DMatch(0, 0, 0.5), cv2.DMatch(1, 1, 0.7)]
        self.mock_extractor.match_features.return_value = expected_matches
        
        result = self.mock_extractor.match_features(
            self.test_descriptors1, self.test_descriptors2
        )
        
        self.mock_extractor.match_features.assert_called_once_with(
            self.test_descriptors1, self.test_descriptors2
        )
        self.assertEqual(result, expected_matches)

    def test_process_images_interface(self):
        """Test process_images method interface"""
        # Mock process_images method
        expected_result = MatchResult(
            matches=[cv2.DMatch(0, 0, 0.5)],
            keypoints1=self.test_keypoints1,
            keypoints2=self.test_keypoints2,
            descriptors1=self.test_descriptors1,
            descriptors2=self.test_descriptors2,
            algorithm="TestMatcher",
            confidence_score=0.8,
            processing_time=0.1
        )
        self.mock_extractor.process_images.return_value = expected_result
        
        result = self.mock_extractor.process_images(self.test_image1, self.test_image2)
        
        self.mock_extractor.process_images.assert_called_once_with(
            self.test_image1, self.test_image2
        )
        self.assertEqual(result, expected_result)

    def test_validate_image_input_none(self):
        """Test image validation with None input"""
        # This would be tested in concrete implementations
        pass

    def test_validate_image_input_wrong_type(self):
        """Test image validation with wrong input type"""
        # This would be tested in concrete implementations
        pass

    def test_validate_image_input_empty_array(self):
        """Test image validation with empty array"""
        # This would be tested in concrete implementations
        pass

    def test_validate_image_input_wrong_dimensions(self):
        """Test image validation with wrong dimensions"""
        # This would be tested in concrete implementations
        pass


class TestMatchResult(unittest.TestCase):
    """Test suite for MatchResult dataclass"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_keypoints1 = [cv2.KeyPoint(x=10, y=20, size=5)]
        self.test_keypoints2 = [cv2.KeyPoint(x=15, y=25, size=6)]
        self.test_descriptors1 = np.random.rand(1, 128).astype(np.float32)
        self.test_descriptors2 = np.random.rand(1, 128).astype(np.float32)
        self.test_matches = [cv2.DMatch(0, 0, 0.5)]

    def test_match_result_creation(self):
        """Test MatchResult creation with valid data"""
        result = MatchResult(
            matches=self.test_matches,
            keypoints1=self.test_keypoints1,
            keypoints2=self.test_keypoints2,
            descriptors1=self.test_descriptors1,
            descriptors2=self.test_descriptors2,
            algorithm="SIFT",
            confidence_score=0.85,
            processing_time=0.15
        )
        
        self.assertEqual(result.matches, self.test_matches)
        self.assertEqual(result.keypoints1, self.test_keypoints1)
        self.assertEqual(result.keypoints2, self.test_keypoints2)
        np.testing.assert_array_equal(result.descriptors1, self.test_descriptors1)
        np.testing.assert_array_equal(result.descriptors2, self.test_descriptors2)
        self.assertEqual(result.algorithm, "SIFT")
        self.assertEqual(result.confidence_score, 0.85)
        self.assertEqual(result.processing_time, 0.15)

    def test_match_result_optional_fields(self):
        """Test MatchResult with optional fields set to None"""
        result = MatchResult(
            matches=self.test_matches,
            keypoints1=self.test_keypoints1,
            keypoints2=self.test_keypoints2,
            descriptors1=None,
            descriptors2=None,
            algorithm="Template",
            confidence_score=None,
            processing_time=None
        )
        
        self.assertEqual(result.matches, self.test_matches)
        self.assertIsNone(result.descriptors1)
        self.assertIsNone(result.descriptors2)
        self.assertIsNone(result.confidence_score)
        self.assertIsNone(result.processing_time)

    def test_match_result_to_dict(self):
        """Test MatchResult conversion to dictionary"""
        result = MatchResult(
            matches=self.test_matches,
            keypoints1=self.test_keypoints1,
            keypoints2=self.test_keypoints2,
            descriptors1=self.test_descriptors1,
            descriptors2=self.test_descriptors2,
            algorithm="ORB",
            confidence_score=0.9,
            processing_time=0.05
        )
        
        result_dict = result.to_dict()
        
        self.assertIn('algorithm', result_dict)
        self.assertIn('confidence_score', result_dict)
        self.assertIn('processing_time', result_dict)
        self.assertIn('num_matches', result_dict)
        self.assertIn('num_keypoints1', result_dict)
        self.assertIn('num_keypoints2', result_dict)
        
        self.assertEqual(result_dict['algorithm'], 'ORB')
        self.assertEqual(result_dict['confidence_score'], 0.9)
        self.assertEqual(result_dict['processing_time'], 0.05)
        self.assertEqual(result_dict['num_matches'], len(self.test_matches))
        self.assertEqual(result_dict['num_keypoints1'], len(self.test_keypoints1))
        self.assertEqual(result_dict['num_keypoints2'], len(self.test_keypoints2))


if __name__ == '__main__':
    unittest.main()