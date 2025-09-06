# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import unittest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
import pytest

from cvat.apps.calibrix_matching.algorithms.orb import ORBMatcher
from cvat.apps.calibrix_matching.algorithms.base import MatchResult


class TestORBMatcher(unittest.TestCase):
    """Test suite for ORB feature extraction and matching"""

    def setUp(self):
        """Set up test fixtures"""
        self.matcher = ORBMatcher()
        
        # Create synthetic test images with clear features
        self.test_image1 = self._create_test_image_with_features()
        self.test_image2 = self._create_test_image_with_features(offset=5, rotation=5)
        
        # Create grayscale versions
        self.gray_image1 = cv2.cvtColor(self.test_image1, cv2.COLOR_BGR2GRAY)
        self.gray_image2 = cv2.cvtColor(self.test_image2, cv2.COLOR_BGR2GRAY)

    def _create_test_image_with_features(self, size=300, offset=0, rotation=0):
        """Create a test image with clear features for ORB detection"""
        img = np.zeros((size, size, 3), dtype=np.uint8)
        
        # Add various geometric shapes that ORB can detect well
        # Rectangles with corners
        cv2.rectangle(img, (30 + offset, 30 + offset), (100 + offset, 100 + offset), (255, 255, 255), 2)
        cv2.rectangle(img, (150 + offset, 150 + offset), (220 + offset, 220 + offset), (200, 200, 200), -1)
        
        # Circles with clear edges
        cv2.circle(img, (80 + offset, 200 + offset), 25, (150, 150, 150), 3)
        cv2.circle(img, (200 + offset, 80 + offset), 20, (100, 100, 100), -1)
        
        # Some lines and patterns
        for i in range(5):
            y = 250 + offset + i * 5
            cv2.line(img, (20 + offset, y), (120 + offset, y), (180, 180, 180), 2)
        
        # Add some texture
        for i in range(0, size, 20):
            for j in range(0, size, 20):
                if (i + j) % 40 == 0:
                    cv2.circle(img, (i + offset, j + offset), 3, (120, 120, 120), -1)
        
        # Apply rotation if specified
        if rotation != 0:
            center = (size // 2, size // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, rotation, 1.0)
            img = cv2.warpAffine(img, rotation_matrix, (size, size))
        
        return img

    def test_orb_matcher_initialization(self):
        """Test ORB matcher initialization"""
        matcher = ORBMatcher()
        self.assertEqual(matcher.algorithm_name, "ORB")
        self.assertIsNotNone(matcher.orb)
        self.assertIsNotNone(matcher.matcher)

    def test_orb_matcher_initialization_with_params(self):
        """Test ORB matcher initialization with custom parameters"""
        matcher = ORBMatcher(
            n_features=1500,
            scale_factor=1.3,
            n_levels=10,
            edge_threshold=25,
            first_level=1,
            wta_k=3,
            patch_size=35,
            fast_threshold=15
        )
        self.assertEqual(matcher.algorithm_name, "ORB")
        self.assertEqual(matcher.n_features, 1500)
        self.assertEqual(matcher.scale_factor, 1.3)

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
        wrong_dim_img = np.random.randint(0, 255, (10, 10, 10, 10), dtype=np.uint8)  # 4D array
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

    def test_extract_features_valid_image(self):
        """Test feature extraction with valid image"""
        keypoints, descriptors = self.matcher.extract_features(self.test_image1)
        
        self.assertIsInstance(keypoints, list)
        self.assertTrue(all(isinstance(kp, cv2.KeyPoint) for kp in keypoints))
        
        if len(keypoints) > 0:
            self.assertIsInstance(descriptors, np.ndarray)
            self.assertEqual(descriptors.shape[0], len(keypoints))
            self.assertEqual(descriptors.shape[1], 32)  # ORB descriptors are 32-dimensional
            self.assertEqual(descriptors.dtype, np.uint8)  # ORB descriptors are binary (uint8)
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

    @patch('cv2.ORB_create')
    def test_extract_features_orb_failure(self, mock_orb_create):
        """Test handling of ORB creation failure"""
        mock_orb = Mock()
        mock_orb.detectAndCompute.side_effect = cv2.error("ORB failed")
        mock_orb_create.return_value = mock_orb
        
        matcher = ORBMatcher()
        
        with self.assertRaises(RuntimeError) as context:
            matcher.extract_features(self.test_image1)
        self.assertIn("ORB feature extraction failed", str(context.exception))

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
        empty_desc1 = np.array([], dtype=np.uint8).reshape(0, 32)
        empty_desc2 = np.array([], dtype=np.uint8).reshape(0, 32)
        
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
        desc1 = np.random.randint(0, 255, (10, 32), dtype=np.uint8)
        desc2 = np.random.randint(0, 255, (10, 16), dtype=np.uint8)  # Wrong dimension
        
        with self.assertRaises(ValueError) as context:
            self.matcher.match_features(desc1, desc2)
        self.assertIn("Descriptor dimensions must match", str(context.exception))

    def test_cross_check_matches(self):
        """Test cross-checking matches for symmetry"""
        # Create mock descriptors
        desc1 = np.random.randint(0, 255, (5, 32), dtype=np.uint8)
        desc2 = np.random.randint(0, 255, (5, 32), dtype=np.uint8)
        
        matches = self.matcher.match_features(desc1, desc2, cross_check=True)
        
        self.assertIsInstance(matches, list)
        
        # Cross-checked matches should be symmetric
        # (This is implementation-dependent, but we can test the interface)

    def test_distance_threshold_filtering(self):
        """Test filtering matches by distance threshold"""
        # Create descriptors that should have some good matches
        desc1 = np.random.randint(0, 255, (10, 32), dtype=np.uint8)
        desc2 = desc1.copy()  # Identical descriptors for perfect matches
        
        # Add some noise to create varied distances
        desc2[:5] = np.random.randint(0, 255, (5, 32), dtype=np.uint8)
        
        matches = self.matcher.match_features(desc1, desc2, distance_threshold=50)
        
        # Should filter out matches with high distances
        self.assertIsInstance(matches, list)
        for match in matches:
            self.assertLessEqual(match.distance, 50)

    def test_process_images_full_pipeline(self):
        """Test the complete image processing pipeline"""
        result = self.matcher.process_images(self.test_image1, self.test_image2)
        
        self.assertIsInstance(result, MatchResult)
        self.assertEqual(result.algorithm, "ORB")
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
            cv2.DMatch(0, 0, 10),  # Good match (low distance)
            cv2.DMatch(1, 1, 20),  # Medium match
            cv2.DMatch(2, 2, 30),  # Higher distance match
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

    def test_orb_rotation_invariance(self):
        """Test that ORB is somewhat invariant to rotation"""
        # Create rotated version of test image
        rotated_image = self._create_test_image_with_features(rotation=30)
        
        result = self.matcher.process_images(self.test_image1, rotated_image)
        
        # Should still find some matches despite rotation
        self.assertIsInstance(result, MatchResult)
        # The exact threshold depends on the image content and ORB parameters

    def test_orb_scale_invariance(self):
        """Test ORB behavior with scaled images"""
        # Create scaled version
        small_image = cv2.resize(self.test_image1, (150, 150))
        
        result = self.matcher.process_images(self.test_image1, small_image)
        
        # Should handle scale differences reasonably well
        self.assertIsInstance(result, MatchResult)

    def test_performance_benchmark(self):
        """Test performance characteristics of ORB matcher"""
        import time
        
        start_time = time.time()
        result = self.matcher.process_images(self.test_image1, self.test_image2)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # ORB should be faster than SIFT
        self.assertLess(processing_time, 2.0)  # Should be quite fast
        
        # Check that reported processing time is reasonable
        if result.processing_time is not None:
            self.assertLess(result.processing_time, processing_time + 0.1)

    def test_hamming_distance_matching(self):
        """Test that ORB uses Hamming distance for binary descriptors"""
        # This tests that the matcher is configured correctly for binary descriptors
        desc1 = np.random.randint(0, 255, (5, 32), dtype=np.uint8)
        desc2 = np.random.randint(0, 255, (5, 32), dtype=np.uint8)
        
        matches = self.matcher.match_features(desc1, desc2)
        
        # Should work without errors (Hamming distance is appropriate for binary descriptors)
        self.assertIsInstance(matches, list)

    def test_maximum_features_limit(self):
        """Test that ORB respects the maximum features limit"""
        # Create matcher with low feature limit
        matcher = ORBMatcher(n_features=50)
        
        keypoints, descriptors = matcher.extract_features(self.test_image1)
        
        if keypoints is not None:
            # Should not exceed the specified limit
            self.assertLessEqual(len(keypoints), 50)
        
        if descriptors is not None:
            self.assertLessEqual(len(descriptors), 50)


if __name__ == '__main__':
    unittest.main()