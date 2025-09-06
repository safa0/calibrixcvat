# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from typing import List, Tuple, Optional
import logging

import numpy as np
import cv2

from .base import FeatureExtractor


logger = logging.getLogger(__name__)


class TemplateMatcher(FeatureExtractor):
    """
    Template matching implementation using normalized cross-correlation.
    
    Template matching is particularly good for:
    - Finding specific patterns or objects in images
    - Exact or near-exact template detection
    - Applications where the template is known a priori
    - Quality control and pattern recognition tasks
    
    This implementation provides multiple matching methods and robust
    filtering of results with non-maximum suppression.
    """

    def __init__(self,
                 method: int = cv2.TM_CCOEFF_NORMED,
                 threshold: float = 0.8,
                 max_matches: int = 100,
                 min_distance: int = 10,
                 min_template_size: int = 10):
        """
        Initialize template matcher with configurable parameters.
        
        Args:
            method: OpenCV template matching method (TM_CCOEFF_NORMED, etc.)
            threshold: Minimum correlation threshold for accepting matches
            max_matches: Maximum number of matches to return
            min_distance: Minimum distance between matches (for NMS)
            min_template_size: Minimum template size in pixels
        """
        super().__init__()
        
        self.method = method
        self.threshold = threshold
        self.max_matches = max_matches
        self.min_distance = min_distance
        self.min_template_size = min_template_size
        
        # Validate method
        valid_methods = [
            cv2.TM_CCOEFF, cv2.TM_CCOEFF_NORMED,
            cv2.TM_CCORR, cv2.TM_CCORR_NORMED,
            cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED
        ]
        
        if method not in valid_methods:
            raise ValueError(f"Invalid template matching method: {method}")
        
        logger.info(f"Template matcher initialized with method {method}, threshold {threshold}")

    @property
    def algorithm_name(self) -> str:
        """Get the algorithm name."""
        return "Template"

    def extract_features(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
        """
        Extract features for template matching.
        
        Template matching doesn't extract traditional keypoints/descriptors,
        so this method returns None for both to maintain interface compatibility.
        
        Args:
            image: Input image
            
        Returns:
            Tuple of (None, None) since template matching works differently
        """
        self._validate_image(image)
        
        # Template matching doesn't use keypoints/descriptors in the traditional sense
        return None, None

    def match_features(self, descriptors1: Optional[np.ndarray], 
                      descriptors2: Optional[np.ndarray]) -> List[cv2.DMatch]:
        """
        Match features for template matching.
        
        Since template matching doesn't use descriptors, this method
        returns an empty list to maintain interface compatibility.
        
        Args:
            descriptors1: Not used for template matching
            descriptors2: Not used for template matching
            
        Returns:
            Empty list (template matching uses different workflow)
        """
        return []

    def process_images(self, image: np.ndarray, template: np.ndarray) -> 'MatchResult':
        """
        Process template matching between an image and template.
        
        This overrides the base class method to implement template-specific workflow:
        1. Validate inputs
        2. Convert to grayscale
        3. Perform template matching
        4. Find peaks in correlation map
        5. Apply non-maximum suppression
        6. Create keypoints and matches
        
        Args:
            image: Source image to search in
            template: Template pattern to find
            
        Returns:
            MatchResult with template matching results
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            self._validate_image(image)
            self._validate_template(template, image)
            
            # Convert to grayscale
            image_gray = self._convert_to_grayscale(image)
            template_gray = self._convert_to_grayscale(template)
            
            # Perform template matching
            locations, scores = self._match_template(image_gray, template_gray)
            
            # Create keypoints and matches from locations
            template_center = (template.shape[1] // 2, template.shape[0] // 2)
            
            # Template has one "keypoint" at its center
            template_keypoint = [cv2.KeyPoint(template_center[0], template_center[1], 
                                            max(template.shape[:2]))]
            
            # Create keypoints for each match location
            image_keypoints = self._create_keypoints_from_locations(locations, template_center)
            
            # Create DMatch objects
            matches = self._create_matches_from_locations(locations, scores, template_center)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score_from_scores(scores)
            
            processing_time = time.time() - start_time
            
            # Import here to avoid circular imports
            from .base import MatchResult
            
            result = MatchResult(
                matches=matches,
                keypoints1=template_keypoint,
                keypoints2=image_keypoints,
                descriptors1=None,  # Template matching doesn't use descriptors
                descriptors2=None,
                algorithm=self.algorithm_name,
                confidence_score=confidence_score,
                processing_time=processing_time
            )
            
            logger.info(f"Template matching completed: "
                       f"{len(matches)} matches, {confidence_score:.3f} confidence, "
                       f"{processing_time:.3f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Template matching failed: {str(e)}")
            raise RuntimeError(f"Template matching failed: {str(e)}") from e

    def _validate_template(self, template: np.ndarray, image: Optional[np.ndarray] = None) -> None:
        """
        Validate template for template matching.
        
        Args:
            template: Template image to validate
            image: Source image (optional, for size comparison)
            
        Raises:
            ValueError: If template is invalid
        """
        if template is None:
            raise ValueError("Template cannot be None")
        
        self._validate_image(template)  # Use base validation
        
        # Check minimum template size
        h, w = template.shape[:2]
        if h < self.min_template_size or w < self.min_template_size:
            raise ValueError(
                f"Template too small: {h}x{w}. "
                f"Minimum size: {self.min_template_size}x{self.min_template_size}"
            )
        
        # Check template size relative to image
        if image is not None:
            img_h, img_w = image.shape[:2]
            if h > img_h or w > img_w:
                raise ValueError(
                    f"Template ({h}x{w}) cannot be larger than image ({img_h}x{img_w})"
                )

    def _match_template(self, image: np.ndarray, template: np.ndarray) -> Tuple[List[Tuple[int, int]], List[float]]:
        """
        Perform template matching and find peak locations.
        
        Args:
            image: Grayscale source image
            template: Grayscale template
            
        Returns:
            Tuple of (locations, scores) where locations are (x, y) coordinates
        """
        # Perform template matching
        correlation_map = cv2.matchTemplate(image, template, self.method)
        
        # Find locations above threshold
        if self.method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            # For SQDIFF methods, lower values are better
            mask = correlation_map <= self.threshold
        else:
            # For other methods, higher values are better
            mask = correlation_map >= self.threshold
        
        # Find peak locations
        locations = np.where(mask)
        if len(locations[0]) == 0:
            return [], []
        
        # Convert to (x, y) coordinates with scores
        coords_and_scores = [
            ((int(x), int(y)), float(correlation_map[y, x]))
            for y, x in zip(locations[0], locations[1])
        ]
        
        # Sort by score (best first)
        if self.method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            coords_and_scores.sort(key=lambda x: x[1])  # Lower is better
        else:
            coords_and_scores.sort(key=lambda x: x[1], reverse=True)  # Higher is better
        
        # Limit number of matches
        coords_and_scores = coords_and_scores[:self.max_matches]
        
        locations = [coord for coord, score in coords_and_scores]
        scores = [score for coord, score in coords_and_scores]
        
        # Apply non-maximum suppression
        filtered_locations, filtered_scores = self._non_maximum_suppression(
            locations, scores, self.min_distance
        )
        
        return filtered_locations, filtered_scores

    def _non_maximum_suppression(self, locations: List[Tuple[int, int]], 
                                scores: List[float], 
                                min_distance: int) -> Tuple[List[Tuple[int, int]], List[float]]:
        """
        Apply non-maximum suppression to remove overlapping detections.
        
        Args:
            locations: List of (x, y) detection locations
            scores: Corresponding detection scores
            min_distance: Minimum distance between detections
            
        Returns:
            Tuple of (filtered_locations, filtered_scores)
        """
        if not locations:
            return [], []
        
        # Convert to numpy arrays for easier processing
        locations_array = np.array(locations)
        scores_array = np.array(scores)
        
        # Sort by score (best first)
        if self.method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            order = np.argsort(scores_array)
        else:
            order = np.argsort(scores_array)[::-1]
        
        keep = []
        
        while len(order) > 0:
            # Keep the best remaining detection
            i = order[0]
            keep.append(i)
            
            if len(order) == 1:
                break
            
            # Calculate distances to all other detections
            current_loc = locations_array[i]
            remaining_locs = locations_array[order[1:]]
            
            distances = np.sqrt(
                np.sum((remaining_locs - current_loc) ** 2, axis=1)
            )
            
            # Keep only detections that are far enough away
            far_enough = distances >= min_distance
            order = order[1:][far_enough]
        
        filtered_locations = [locations[i] for i in keep]
        filtered_scores = [scores[i] for i in keep]
        
        return filtered_locations, filtered_scores

    def _create_keypoints_from_locations(self, locations: List[Tuple[int, int]], 
                                       template_center: Tuple[int, int]) -> List[cv2.KeyPoint]:
        """
        Create keypoints from template match locations.
        
        Args:
            locations: List of (x, y) template match locations
            template_center: Center offset of template
            
        Returns:
            List of keypoints at match centers
        """
        keypoints = []
        for x, y in locations:
            # Keypoint at the center of the matched template
            center_x = x + template_center[0]
            center_y = y + template_center[1]
            
            # Size is based on template dimensions
            size = max(template_center) * 2
            
            keypoint = cv2.KeyPoint(center_x, center_y, size)
            keypoints.append(keypoint)
        
        return keypoints

    def _create_matches_from_locations(self, locations: List[Tuple[int, int]], 
                                     scores: List[float],
                                     template_center: Tuple[int, int]) -> List[cv2.DMatch]:
        """
        Create DMatch objects from template match locations.
        
        Args:
            locations: List of (x, y) template match locations
            scores: Corresponding match scores
            template_center: Center offset of template
            
        Returns:
            List of DMatch objects
        """
        matches = []
        for i, (location, score) in enumerate(zip(locations, scores)):
            # Convert score to distance (lower distance = better match)
            if self.method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
                distance = float(score)  # Already distance-like
            else:
                distance = float(1.0 - score)  # Convert correlation to distance
            
            # Template has queryIdx=0 (single template), match has trainIdx=i
            match = cv2.DMatch(0, i, distance)
            matches.append(match)
        
        return matches

    def _calculate_confidence_score_from_scores(self, scores: List[float]) -> float:
        """
        Calculate confidence score from template matching scores.
        
        Args:
            scores: List of template matching scores
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not scores:
            return 0.0
        
        # Use the best score as primary confidence indicator
        best_score = scores[0] if scores else 0.0
        
        # Normalize score based on method
        if self.method in [cv2.TM_SQDIFF, cv2.TM_SQDIFF_NORMED]:
            # For SQDIFF, lower is better, convert to 0-1 scale
            normalized_score = max(0.0, 1.0 - best_score)
        else:
            # For correlation methods, higher is better, already 0-1 for normalized methods
            if self.method in [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED]:
                normalized_score = max(0.0, best_score)
            else:
                # Non-normalized methods need different handling
                normalized_score = min(1.0, max(0.0, best_score / 1000.0))
        
        # Factor in number of matches
        num_matches = len(scores)
        if num_matches > 5:
            count_factor = 1.0
        else:
            count_factor = 0.5 + (num_matches / 10.0)
        
        # Combine score quality and quantity
        confidence = (normalized_score * 0.8) + (count_factor * 0.2)
        
        return max(0.0, min(1.0, confidence))

    def get_algorithm_info(self) -> dict:
        """Get detailed information about template matching configuration."""
        info = super().get_algorithm_info()
        
        method_names = {
            cv2.TM_CCOEFF: "TM_CCOEFF",
            cv2.TM_CCOEFF_NORMED: "TM_CCOEFF_NORMED",
            cv2.TM_CCORR: "TM_CCORR",
            cv2.TM_CCORR_NORMED: "TM_CCORR_NORMED",
            cv2.TM_SQDIFF: "TM_SQDIFF",
            cv2.TM_SQDIFF_NORMED: "TM_SQDIFF_NORMED"
        }
        
        info.update({
            'method': self.method,
            'method_name': method_names.get(self.method, f"Unknown_{self.method}"),
            'threshold': self.threshold,
            'max_matches': self.max_matches,
            'min_distance': self.min_distance,
            'min_template_size': self.min_template_size,
            'descriptor_size': None,
            'descriptor_type': None
        })
        return info


# Import time at module level to avoid issues
import time