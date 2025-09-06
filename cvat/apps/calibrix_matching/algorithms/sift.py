# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from typing import List, Tuple, Optional
import logging

import numpy as np
import cv2

from .base import FeatureExtractor


logger = logging.getLogger(__name__)


class SIFTMatcher(FeatureExtractor):
    """
    SIFT (Scale-Invariant Feature Transform) feature extraction and matching implementation.
    
    SIFT is particularly good for:
    - Scale invariant feature detection
    - Rotation invariant matching
    - Distinctive feature description
    - Handling significant viewpoint changes
    
    This implementation provides configurable SIFT parameters and robust matching
    with Lowe's ratio test for filtering good matches.
    """

    def __init__(self, 
                 n_features: int = 0,
                 n_octave_layers: int = 3,
                 contrast_threshold: float = 0.04,
                 edge_threshold: float = 10,
                 sigma: float = 1.6,
                 ratio_test_threshold: float = 0.75):
        """
        Initialize SIFT matcher with configurable parameters.
        
        Args:
            n_features: Maximum number of features to detect (0 = no limit)
            n_octave_layers: Number of layers in each octave
            contrast_threshold: Contrast threshold for feature detection
            edge_threshold: Edge threshold for filtering edge-like features
            sigma: Gaussian sigma for the first level of the first octave
            ratio_test_threshold: Threshold for Lowe's ratio test (0.75 typical)
        """
        super().__init__()
        
        self.n_features = n_features
        self.n_octave_layers = n_octave_layers
        self.contrast_threshold = contrast_threshold
        self.edge_threshold = edge_threshold
        self.sigma = sigma
        self.ratio_test_threshold = ratio_test_threshold
        
        # Initialize SIFT detector and descriptor
        self.sift = cv2.SIFT_create(
            nfeatures=n_features,
            nOctaveLayers=n_octave_layers,
            contrastThreshold=contrast_threshold,
            edgeThreshold=edge_threshold,
            sigma=sigma
        )
        
        # Initialize feature matcher (FLANN-based for SIFT)
        FLANN_INDEX_KDTREE = 1
        index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
        search_params = dict(checks=50)
        self.matcher = cv2.FlannBasedMatcher(index_params, search_params)
        
        logger.info(f"SIFT matcher initialized with {n_features} max features")

    @property
    def algorithm_name(self) -> str:
        """Get the algorithm name."""
        return "SIFT"

    def extract_features(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
        """
        Extract SIFT features from an image.
        
        Args:
            image: Input image (BGR, RGB, or grayscale)
            
        Returns:
            Tuple of (keypoints, descriptors) where descriptors are float32 arrays
            
        Raises:
            ValueError: If image is invalid
            RuntimeError: If SIFT feature extraction fails
        """
        self._validate_image(image)
        
        try:
            # Convert to grayscale
            gray = self._convert_to_grayscale(image)
            
            # Detect keypoints and compute descriptors
            keypoints, descriptors = self.sift.detectAndCompute(gray, None)
            
            # Convert keypoints tuple to list for consistency
            keypoints = list(keypoints) if keypoints is not None else []
            
            logger.debug(f"SIFT extracted {len(keypoints)} keypoints")
            
            return keypoints, descriptors
            
        except cv2.error as e:
            logger.error(f"SIFT feature extraction failed: {str(e)}")
            raise RuntimeError(f"SIFT feature extraction failed: {str(e)}") from e

    def match_features(self, descriptors1: Optional[np.ndarray], 
                      descriptors2: Optional[np.ndarray]) -> List[cv2.DMatch]:
        """
        Match SIFT features between two sets of descriptors.
        
        Uses FLANN-based matching with Lowe's ratio test for robust matching.
        
        Args:
            descriptors1: SIFT descriptors from first image
            descriptors2: SIFT descriptors from second image
            
        Returns:
            List of good matches after ratio test filtering
            
        Raises:
            ValueError: If descriptors are incompatible
        """
        if descriptors1 is None or descriptors2 is None:
            return []
        
        if len(descriptors1) == 0 or len(descriptors2) == 0:
            return []
        
        # Validate descriptor dimensions
        if descriptors1.shape[1] != descriptors2.shape[1]:
            raise ValueError(
                f"Descriptor dimensions must match: "
                f"{descriptors1.shape[1]} vs {descriptors2.shape[1]}"
            )
        
        try:
            # Use FLANN matcher for efficient matching
            raw_matches = self.matcher.knnMatch(descriptors1, descriptors2, k=2)
            
            # Apply Lowe's ratio test
            good_matches = self._filter_matches_lowe_ratio(raw_matches, self.ratio_test_threshold)
            
            logger.debug(f"SIFT matching: {len(raw_matches)} raw -> {len(good_matches)} good matches")
            
            return good_matches
            
        except cv2.error as e:
            logger.error(f"SIFT matching failed: {str(e)}")
            # Return empty matches on error rather than crashing
            return []

    def _filter_matches_lowe_ratio(self, raw_matches: List[List[cv2.DMatch]], 
                                  ratio: float = 0.75) -> List[cv2.DMatch]:
        """
        Apply Lowe's ratio test to filter good matches.
        
        The ratio test compares the distance of the best match to the second-best match.
        If the ratio is below the threshold, the match is considered reliable.
        
        Args:
            raw_matches: Raw matches from knnMatch (k=2)
            ratio: Ratio threshold for filtering (typically 0.75)
            
        Returns:
            List of filtered good matches
        """
        good_matches = []
        
        for match_pair in raw_matches:
            if len(match_pair) == 2:
                best_match, second_match = match_pair
                # Apply Lowe's ratio test
                if best_match.distance < ratio * second_match.distance:
                    good_matches.append(best_match)
        
        return good_matches

    def _calculate_confidence_score(self, matches: List[cv2.DMatch]) -> float:
        """
        Calculate confidence score specific to SIFT matches.
        
        SIFT confidence considers:
        - Number of matches (more matches = higher confidence)
        - Match distances (lower distances = higher confidence)
        - Distribution of matches across the image
        
        Args:
            matches: List of SIFT matches
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not matches:
            return 0.0
        
        # SIFT-specific confidence calculation
        distances = [match.distance for match in matches]
        
        # SIFT distances are typically in range 0-500, with good matches < 100
        mean_distance = np.mean(distances)
        distance_confidence = max(0.0, 1.0 - (mean_distance / 200.0))
        
        # Factor in number of matches (SIFT typically needs 4+ for geometric verification)
        match_count = len(matches)
        if match_count >= 10:
            count_confidence = 1.0
        elif match_count >= 4:
            count_confidence = match_count / 10.0
        else:
            count_confidence = 0.3  # Low confidence for few matches
        
        # Combine factors with SIFT-specific weighting
        confidence = (distance_confidence * 0.6) + (count_confidence * 0.4)
        
        return max(0.0, min(1.0, confidence))

    def get_algorithm_info(self) -> dict:
        """Get detailed information about SIFT configuration."""
        info = super().get_algorithm_info()
        info.update({
            'n_features': self.n_features,
            'n_octave_layers': self.n_octave_layers,
            'contrast_threshold': self.contrast_threshold,
            'edge_threshold': self.edge_threshold,
            'sigma': self.sigma,
            'ratio_test_threshold': self.ratio_test_threshold,
            'descriptor_size': 128,
            'descriptor_type': 'float32'
        })
        return info