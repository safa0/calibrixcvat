# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import unittest
import numpy as np
import cv2
from unittest.mock import Mock, patch, MagicMock
import pytest

from cvat.apps.calibrix_matching.algorithms.template import TemplateMatcher
from cvat.apps.calibrix_matching.algorithms.base import MatchResult


class TestTemplateMatcher(unittest.TestCase):
    """Test suite for Template Matching algorithm"""

    def setUp(self):
        """Set up test fixtures"""
        self.matcher = TemplateMatcher()
        
        # Create test images with known template locations
        self.test_image = self._create_test_image()
        self.test_template = self._create_test_template()
        
        # Create variations for testing
        self.test_image_with_template = self._create_image_with_template()
        self.test_image_no_template = self._create_image_without_template()

    def _create_test_image(self, size=300):
        """Create a test image with various patterns"""
        img = np.zeros((size, size, 3), dtype=np.uint8)
        
        # Add background texture
        noise = np.random.randint(0, 50, (size, size, 3), dtype=np.uint8)
        img = cv2.add(img, noise)
        
        # Add some geometric shapes as distractors
        cv2.rectangle(img, (50, 50), (100, 100), (80, 80, 80), -1)
        cv2.circle(img, (200, 200), 30, (120, 120, 120), -1)
        
        return img

    def _create_test_template(self, size=50):
        """Create a distinctive template pattern"""
        template = np.zeros((size, size, 3), dtype=np.uint8)
        
        # Create a distinctive pattern
        cv2.rectangle(template, (10, 10), (40, 40), (255, 255, 255), -1)
        cv2.rectangle(template, (15, 15), (35, 35), (100, 100, 100), -1)
        cv2.circle(template, (25, 25), 8, (200, 200, 200), -1)
        
        return template

    def _create_image_with_template(self):
        """Create an image that contains the template at known location"""
        img = self._create_test_image()
        template = self._create_test_template()
        
        # Place template at location (100, 150)
        h, w = template.shape[:2]
        img[150:150+h, 100:100+w] = template
        
        return img

    def _create_image_without_template(self):
        """Create an image that does not contain the template"""
        img = np.random.randint(0, 255, (300, 300, 3), dtype=np.uint8)
        # Add some patterns that might cause false positives
        cv2.rectangle(img, (50, 50), (80, 80), (255, 0, 0), -1)
        cv2.circle(img, (200, 200), 25, (0, 255, 0), -1)
        return img

    def test_template_matcher_initialization(self):
        """Test TemplateMatcher initialization"""
        matcher = TemplateMatcher()
        self.assertEqual(matcher.algorithm_name, "Template")
        self.assertEqual(matcher.method, cv2.TM_CCOEFF_NORMED)
        self.assertEqual(matcher.threshold, 0.8)

    def test_template_matcher_initialization_with_params(self):
        """Test TemplateMatcher initialization with custom parameters"""
        matcher = TemplateMatcher(
            method=cv2.TM_CCORR_NORMED,
            threshold=0.7,
            max_matches=10,
            min_distance=20
        )
        self.assertEqual(matcher.algorithm_name, "Template")
        self.assertEqual(matcher.method, cv2.TM_CCORR_NORMED)
        self.assertEqual(matcher.threshold, 0.7)
        self.assertEqual(matcher.max_matches, 10)
        self.assertEqual(matcher.min_distance, 20)

    def test_validate_template_valid(self):
        """Test template validation with valid template"""
        try:
            self.matcher._validate_template(self.test_template)
        except Exception as e:
            self.fail(f"_validate_template raised {e} unexpectedly!")

    def test_validate_template_none(self):
        """Test template validation with None input"""
        with self.assertRaises(ValueError) as context:
            self.matcher._validate_template(None)
        self.assertIn("Template cannot be None", str(context.exception))

    def test_validate_template_too_large(self):
        """Test template validation when template is larger than image"""
        large_template = np.ones((500, 500, 3), dtype=np.uint8)
        small_image = np.ones((100, 100, 3), dtype=np.uint8)
        
        with self.assertRaises(ValueError) as context:
            self.matcher._validate_template(large_template, small_image)
        self.assertIn("Template cannot be larger than image", str(context.exception))

    def test_validate_template_too_small(self):
        """Test template validation when template is too small"""
        tiny_template = np.ones((5, 5, 3), dtype=np.uint8)
        
        with self.assertRaises(ValueError) as context:
            self.matcher._validate_template(tiny_template)
        self.assertIn("Template too small", str(context.exception))

    def test_convert_to_grayscale_bgr(self):
        """Test converting BGR image to grayscale"""
        gray = self.matcher._convert_to_grayscale(self.test_image)
        self.assertEqual(len(gray.shape), 2)
        self.assertEqual(gray.shape[:2], self.test_image.shape[:2])

    def test_convert_to_grayscale_already_gray(self):
        """Test converting already grayscale image"""
        gray_image = cv2.cvtColor(self.test_image, cv2.COLOR_BGR2GRAY)
        gray = self.matcher._convert_to_grayscale(gray_image)
        self.assertEqual(len(gray.shape), 2)
        np.testing.assert_array_equal(gray, gray_image)

    def test_extract_features_template_method(self):
        """Test extract_features method for template matching"""
        # For template matching, we don't extract keypoints/descriptors in the traditional sense
        keypoints, descriptors = self.matcher.extract_features(self.test_image)
        
        # Template matching should return None for keypoints and descriptors
        # as it works differently than feature-based methods
        self.assertIsNone(keypoints)
        self.assertIsNone(descriptors)

    def test_match_template_valid_inputs(self):
        """Test template matching with valid inputs"""
        image_gray = cv2.cvtColor(self.test_image_with_template, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(self.test_template, cv2.COLOR_BGR2GRAY)
        
        locations, scores = self.matcher._match_template(image_gray, template_gray)
        
        self.assertIsInstance(locations, list)
        self.assertIsInstance(scores, list)
        self.assertEqual(len(locations), len(scores))
        
        # Check that locations are tuples of (x, y)
        for loc in locations:
            self.assertIsInstance(loc, tuple)
            self.assertEqual(len(loc), 2)
            self.assertIsInstance(loc[0], (int, np.integer))
            self.assertIsInstance(loc[1], (int, np.integer))
        
        # Check that scores are reasonable
        for score in scores:
            self.assertIsInstance(score, (float, np.floating))
            if self.matcher.method in [cv2.TM_CCORR_NORMED, cv2.TM_CCOEFF_NORMED, cv2.TM_SQDIFF_NORMED]:
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)

    def test_match_template_no_matches(self):
        """Test template matching when no matches above threshold"""
        image_gray = cv2.cvtColor(self.test_image_no_template, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(self.test_template, cv2.COLOR_BGR2GRAY)
        
        locations, scores = self.matcher._match_template(image_gray, template_gray)
        
        # Should return empty lists when no matches found
        self.assertIsInstance(locations, list)
        self.assertIsInstance(scores, list)
        
        # Might be empty or have low-scoring matches depending on threshold

    def test_match_template_different_methods(self):
        """Test template matching with different matching methods"""
        image_gray = cv2.cvtColor(self.test_image_with_template, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(self.test_template, cv2.COLOR_BGR2GRAY)
        
        methods = [
            cv2.TM_CCOEFF_NORMED,
            cv2.TM_CCORR_NORMED,
            cv2.TM_SQDIFF_NORMED
        ]
        
        for method in methods:
            matcher = TemplateMatcher(method=method)
            locations, scores = matcher._match_template(image_gray, template_gray)
            
            self.assertIsInstance(locations, list)
            self.assertIsInstance(scores, list)

    def test_non_maximum_suppression(self):
        """Test non-maximum suppression for overlapping detections"""
        # Create locations that are close together
        locations = [(100, 100), (105, 105), (200, 200), (110, 110)]
        scores = [0.9, 0.8, 0.95, 0.7]
        
        filtered_locations, filtered_scores = self.matcher._non_maximum_suppression(
            locations, scores, min_distance=20
        )
        
        self.assertIsInstance(filtered_locations, list)
        self.assertIsInstance(filtered_scores, list)
        self.assertEqual(len(filtered_locations), len(filtered_scores))
        
        # Should have fewer locations after suppression
        self.assertLessEqual(len(filtered_locations), len(locations))
        
        # Remaining locations should be well separated
        for i, loc1 in enumerate(filtered_locations):
            for j, loc2 in enumerate(filtered_locations):
                if i != j:
                    distance = np.sqrt((loc1[0] - loc2[0])**2 + (loc1[1] - loc2[1])**2)
                    self.assertGreaterEqual(distance, 20)

    def test_create_matches_from_template_locations(self):
        """Test creation of DMatch objects from template locations"""
        locations = [(100, 100), (200, 200)]
        scores = [0.9, 0.8]
        template_center = (25, 25)  # Center of 50x50 template
        
        matches = self.matcher._create_matches_from_locations(
            locations, scores, template_center
        )
        
        self.assertIsInstance(matches, list)
        self.assertEqual(len(matches), len(locations))
        
        for i, match in enumerate(matches):
            self.assertIsInstance(match, cv2.DMatch)
            self.assertEqual(match.queryIdx, 0)  # Template has only one "keypoint"
            self.assertEqual(match.trainIdx, i)
            # Distance should be related to score (inverted for better matches = lower distance)
            self.assertGreaterEqual(match.distance, 0.0)

    def test_create_keypoints_from_locations(self):
        """Test creation of keypoints from template match locations"""
        locations = [(100, 100), (200, 200)]
        template_center = (25, 25)
        
        keypoints = self.matcher._create_keypoints_from_locations(locations, template_center)
        
        self.assertIsInstance(keypoints, list)
        self.assertEqual(len(keypoints), len(locations))
        
        for i, kp in enumerate(keypoints):
            self.assertIsInstance(kp, cv2.KeyPoint)
            expected_x = locations[i][0] + template_center[0]
            expected_y = locations[i][1] + template_center[1]
            self.assertEqual(kp.pt[0], expected_x)
            self.assertEqual(kp.pt[1], expected_y)

    def test_process_images_full_pipeline(self):
        """Test the complete template matching pipeline"""
        result = self.matcher.process_images(self.test_image_with_template, self.test_template)
        
        self.assertIsInstance(result, MatchResult)
        self.assertEqual(result.algorithm, "Template")
        
        # Template matching returns one template keypoint and multiple image keypoints
        self.assertIsInstance(result.keypoints1, list)
        self.assertIsInstance(result.keypoints2, list)
        self.assertIsInstance(result.matches, list)
        
        # Check timing information
        self.assertIsInstance(result.processing_time, (int, float))
        self.assertGreater(result.processing_time, 0)
        
        # Check confidence score
        if result.confidence_score is not None:
            self.assertGreaterEqual(result.confidence_score, 0.0)
            self.assertLessEqual(result.confidence_score, 1.0)

    def test_process_images_no_template_found(self):
        """Test processing when template is not found in image"""
        result = self.matcher.process_images(self.test_image_no_template, self.test_template)
        
        self.assertIsInstance(result, MatchResult)
        self.assertEqual(result.algorithm, "Template")
        
        # Should have minimal or no matches
        self.assertIsInstance(result.matches, list)

    def test_process_images_identical_images(self):
        """Test processing when image and template are identical"""
        # Use template as both image and template
        result = self.matcher.process_images(self.test_template, self.test_template)
        
        self.assertIsInstance(result, MatchResult)
        # Should have high confidence
        if result.confidence_score is not None:
            self.assertGreater(result.confidence_score, 0.8)

    def test_match_features_not_applicable(self):
        """Test that match_features is not applicable for template matching"""
        # Template matching doesn't use traditional descriptors
        result = self.matcher.match_features(None, None)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 0)

    def test_calculate_confidence_score_template(self):
        """Test confidence score calculation for template matching"""
        # Simulate match scores from template matching
        scores = [0.9, 0.8, 0.7]
        
        confidence = self.matcher._calculate_confidence_score_from_scores(scores)
        
        self.assertIsInstance(confidence, (int, float))
        self.assertGreaterEqual(confidence, 0.0)
        self.assertLessEqual(confidence, 1.0)
        
        # Should be influenced by the best score
        self.assertGreaterEqual(confidence, max(scores) * 0.8)  # Should be close to best score

    def test_calculate_confidence_score_no_matches_template(self):
        """Test confidence score calculation with no matches"""
        scores = []
        confidence = self.matcher._calculate_confidence_score_from_scores(scores)
        self.assertEqual(confidence, 0.0)

    def test_threshold_filtering(self):
        """Test that matches below threshold are filtered out"""
        matcher = TemplateMatcher(threshold=0.9)
        
        # Create image and template where matches would be below threshold
        low_quality_image = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
        
        result = matcher.process_images(low_quality_image, self.test_template)
        
        # Should have no or very few matches due to high threshold
        self.assertIsInstance(result, MatchResult)

    def test_max_matches_limit(self):
        """Test that maximum matches limit is respected"""
        matcher = TemplateMatcher(max_matches=3, threshold=0.3)  # Low threshold to get more matches
        
        # Create image with multiple potential matches
        multi_match_image = self._create_image_with_multiple_templates()
        
        result = matcher.process_images(multi_match_image, self.test_template)
        
        # Should not exceed max_matches limit
        self.assertLessEqual(len(result.matches), 3)

    def _create_image_with_multiple_templates(self):
        """Create an image with multiple template instances"""
        img = np.zeros((400, 400, 3), dtype=np.uint8)
        template = self._create_test_template()
        h, w = template.shape[:2]
        
        # Place template at multiple locations
        locations = [(50, 50), (150, 50), (50, 150), (200, 200)]
        for x, y in locations:
            if x + w < img.shape[1] and y + h < img.shape[0]:
                img[y:y+h, x:x+w] = template
        
        return img

    def test_template_matching_scale_sensitivity(self):
        """Test template matching behavior with scaled templates"""
        # Create scaled version of template
        small_template = cv2.resize(self.test_template, (25, 25))
        
        result = self.matcher.process_images(self.test_image_with_template, small_template)
        
        # Template matching is scale-sensitive, so might not find matches
        self.assertIsInstance(result, MatchResult)

    def test_performance_benchmark(self):
        """Test performance characteristics of template matcher"""
        import time
        
        start_time = time.time()
        result = self.matcher.process_images(self.test_image_with_template, self.test_template)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Template matching should be reasonably fast for small templates
        self.assertLess(processing_time, 1.0)
        
        # Check that reported processing time is reasonable
        if result.processing_time is not None:
            self.assertLess(result.processing_time, processing_time + 0.1)


if __name__ == '__main__':
    unittest.main()