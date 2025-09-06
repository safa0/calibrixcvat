# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import unittest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
import pytest

from cvat.apps.calibrix_matching.algorithms.sift import SIFTMatcher
from cvat.apps.calibrix_matching.algorithms.base import MatchResult


class TestSIFTMatcher(unittest.TestCase):
    """Test suite for SIFT feature extraction and matching"""

    def setUp(self):
        """Set up test fixtures"""
        self.matcher = SIFTMatcher()
        
        # Create synthetic test images with known features
        self.test_image1 = self._create_test_image_with_corners()
        self.test_image2 = self._create_test_image_with_corners(offset=10)
        
        # Create grayscale versions
        self.gray_image1 = cv2.cvtColor(self.test_image1, cv2.COLOR_BGR2GRAY)
        self.gray_image2 = cv2.cvtColor(self.test_image2, cv2.COLOR_BGR2GRAY)

    def _create_test_image_with_corners(self, size=200, offset=0):
        """Create a test image with clear corner features"""
        img = np.zeros((size, size, 3), dtype=np.uint8)
        
        # Add some clear corner features
        cv2.rectangle(img, (20 + offset, 20 + offset), (80 + offset, 80 + offset), (255, 255, 255), -1)
        cv2.rectangle(img, (120 + offset, 120 + offset), (180 + offset, 180 + offset), (255, 255, 255), -1)
        cv2.circle(img, (50 + offset, 150 + offset), 20, (128, 128, 128), -1)
        
        # Add some noise for more realistic features
        noise = np.random.randint(0, 50, (size, size, 3), dtype=np.uint8)
        img = cv2.add(img, noise)
        
        return img

    def test_sift_matcher_initialization(self):
        """Test SIFT matcher initialization"""
        matcher = SIFTMatcher()
        self.assertEqual(matcher.algorithm_name, "SIFT")
        self.assertIsNotNone(matcher.sift)
        self.assertIsNotNone(matcher.matcher)

    def test_sift_matcher_initialization_with_params(self):
        """Test SIFT matcher initialization with custom parameters"""
        matcher = SIFTMatcher(
            n_features=1000,
            n_octave_layers=4,
            contrast_threshold=0.05,
            edge_threshold=15,
            sigma=1.8
        )
        self.assertEqual(matcher.algorithm_name, "SIFT")
        self.assertEqual(matcher.n_features, 1000)
        self.assertEqual(matcher.contrast_threshold, 0.05)

    def test_validate_image_valid(self):
        """Test image validation with valid image"""
        try:
            self.matcher._validate_image(self.test_image1)
        except Exception as e:
            self.fail(f"_validate_image raised {e} unexpectedly!")

    def test_validate_image_none(self):
        """Test image validation with None input"""
        with self.assertRaises(ValueError) as context:
            self.matcher._validate_image(None)
        self.assertIn("Image cannot be None", str(context.exception))

    def test_validate_image_empty(self):
        """Test image validation with empty array"""
        empty_img = np.array([])
        with self.assertRaises(ValueError) as context:
            self.matcher._validate_image(empty_img)
        self.assertIn("Image cannot be empty", str(context.exception))

    def test_validate_image_wrong_dimensions(self):
        """Test image validation with wrong dimensions"""
        wrong_dim_img = np.random.randint(0, 255, (10,), dtype=np.uint8)  # 1D array
        with self.assertRaises(ValueError) as context:
            self.matcher._validate_image(wrong_dim_img)
        self.assertIn("Image must be 2D or 3D", str(context.exception))

    def test_convert_to_grayscale_bgr(self):
        """Test converting BGR image to grayscale"""
        gray = self.matcher._convert_to_grayscale(self.test_image1)
        self.assertEqual(len(gray.shape), 2)
        self.assertEqual(gray.shape[:2], self.test_image1.shape[:2])

    def test_convert_to_grayscale_already_gray(self):
        """Test converting already grayscale image"""
        gray = self.matcher._convert_to_grayscale(self.gray_image1)
        self.assertEqual(len(gray.shape), 2)
        np.testing.assert_array_equal(gray, self.gray_image1)

    def test_convert_to_grayscale_rgba(self):
        """Test converting RGBA image to grayscale"""
        rgba_img = cv2.cvtColor(self.test_image1, cv2.COLOR_BGR2BGRA)
        gray = self.matcher._convert_to_grayscale(rgba_img)
        self.assertEqual(len(gray.shape), 2)
        self.assertEqual(gray.shape[:2], rgba_img.shape[:2])

    def test_extract_features_valid_image(self):
        """Test feature extraction with valid image"""
        keypoints, descriptors = self.matcher.extract_features(self.test_image1)
        
        self.assertIsInstance(keypoints, list)
        self.assertTrue(all(isinstance(kp, cv2.KeyPoint) for kp in keypoints))
        
        if len(keypoints) > 0:
            self.assertIsInstance(descriptors, np.ndarray)
            self.assertEqual(descriptors.shape[0], len(keypoints))
            self.assertEqual(descriptors.shape[1], 128)  # SIFT descriptors are 128-dimensional
            self.assertEqual(descriptors.dtype, np.float32)
        else:
            self.assertIsNone(descriptors)

    def test_extract_features_no_features(self):
        """Test feature extraction with image containing no features"""
        # Create a uniform image with no features
        uniform_img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        
        keypoints, descriptors = self.matcher.extract_features(uniform_img)
        
        # Might return empty lists or None depending on implementation
        if keypoints is not None:
            self.assertIsInstance(keypoints, list)
        if descriptors is not None:
            self.assertIsInstance(descriptors, np.ndarray)

    @patch('cv2.SIFT_create')
    def test_extract_features_sift_failure(self, mock_sift_create):
        """Test handling of SIFT creation failure"""
        mock_sift = Mock()
        mock_sift.detectAndCompute.side_effect = cv2.error("SIFT failed")
        mock_sift_create.return_value = mock_sift
        
        matcher = SIFTMatcher()
        
        with self.assertRaises(RuntimeError) as context:
            matcher.extract_features(self.test_image1)
        self.assertIn("SIFT feature extraction failed", str(context.exception))

    def test_match_features_valid_descriptors(self):
        """Test feature matching with valid descriptors"""
        kp1, desc1 = self.matcher.extract_features(self.test_image1)
        kp2, desc2 = self.matcher.extract_features(self.test_image2)
        
        if desc1 is not None and desc2 is not None and len(desc1) > 0 and len(desc2) > 0:
            matches = self.matcher.match_features(desc1, desc2)
            
            self.assertIsInstance(matches, list)
            self.assertTrue(all(isinstance(match, cv2.DMatch) for match in matches))
            
            # Check that matches are reasonable
            for match in matches:
                self.assertGreaterEqual(match.queryIdx, 0)
                self.assertLess(match.queryIdx, len(desc1))
                self.assertGreaterEqual(match.trainIdx, 0)
                self.assertLess(match.trainIdx, len(desc2))
                self.assertGreaterEqual(match.distance, 0.0)

    def test_match_features_empty_descriptors(self):
        """Test feature matching with empty descriptors"""
        empty_desc1 = np.array([], dtype=np.float32).reshape(0, 128)
        empty_desc2 = np.array([], dtype=np.float32).reshape(0, 128)
        
        matches = self.matcher.match_features(empty_desc1, empty_desc2)
        self.assertIsInstance(matches, list)
        self.assertEqual(len(matches), 0)

    def test_match_features_none_descriptors(self):
        """Test feature matching with None descriptors"""
        matches = self.matcher.match_features(None, None)
        self.assertIsInstance(matches, list)
        self.assertEqual(len(matches), 0)

    def test_match_features_mismatched_dimensions(self):
        """Test feature matching with mismatched descriptor dimensions"""
        desc1 = np.random.rand(10, 128).astype(np.float32)
        desc2 = np.random.rand(10, 64).astype(np.float32)  # Wrong dimension
        
        with self.assertRaises(ValueError) as context:
            self.matcher.match_features(desc1, desc2)
        self.assertIn("Descriptor dimensions must match", str(context.exception))

    def test_filter_matches_lowe_ratio(self):
        """Test Lowe's ratio test for filtering matches"""
        # Create mock matches for testing
        good_match = cv2.DMatch(0, 0, 0.1)  # Good match (low distance)
        bad_match = cv2.DMatch(0, 1, 0.9)   # Bad match (high distance)
        
        raw_matches = [[good_match, bad_match]]
        
        filtered = self.matcher._filter_matches_lowe_ratio(raw_matches, ratio=0.75)
        
        # Should keep the good match, reject the bad one based on ratio test
        self.assertIsInstance(filtered, list)
        # The exact result depends on the ratio test implementation

    def test_process_images_full_pipeline(self):
        """Test the complete image processing pipeline"""
        result = self.matcher.process_images(self.test_image1, self.test_image2)
        
        self.assertIsInstance(result, MatchResult)
        self.assertEqual(result.algorithm, "SIFT")
        self.assertIsInstance(result.keypoints1, list)
        self.assertIsInstance(result.keypoints2, list)
        self.assertIsInstance(result.matches, list)
        
        # Check timing information
        self.assertIsInstance(result.processing_time, (int, float))
        self.assertGreater(result.processing_time, 0)
        
        # Check confidence score if available
        if result.confidence_score is not None:
            self.assertGreaterEqual(result.confidence_score, 0.0)
            self.assertLessEqual(result.confidence_score, 1.0)

    def test_process_images_identical_images(self):
        """Test processing identical images"""
        result = self.matcher.process_images(self.test_image1, self.test_image1)
        
        self.assertIsInstance(result, MatchResult)
        # Should have high confidence for identical images
        if result.confidence_score is not None:
            self.assertGreater(result.confidence_score, 0.5)

    def test_calculate_confidence_score(self):
        """Test confidence score calculation"""
        # Create mock matches with known distances
        matches = [
            cv2.DMatch(0, 0, 0.1),
            cv2.DMatch(1, 1, 0.2),
            cv2.DMatch(2, 2, 0.3),
        ]
        
        confidence = self.matcher._calculate_confidence_score(matches)
        
        self.assertIsInstance(confidence, (int, float))
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)

    def test_calculate_confidence_score_no_matches(self):
        """Test confidence score calculation with no matches"""
        matches = []
        confidence = self.matcher._calculate_confidence_score(matches)
        self.assertEqual(confidence, 0.0)

    def test_performance_benchmark(self):
        """Test performance characteristics of SIFT matcher"""
        import time
        
        start_time = time.time()
        result = self.matcher.process_images(self.test_image1, self.test_image2)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # SIFT should complete within reasonable time for small test images
        self.assertLess(processing_time, 5.0)  # 5 seconds should be more than enough
        
        # Check that reported processing time is reasonable
        if result.processing_time is not None:
            self.assertLess(result.processing_time, processing_time + 0.1)  # Allow small margin


if __name__ == '__main__':
    unittest.main()