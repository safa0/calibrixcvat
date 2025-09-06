# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from typing import List, Tuple, Optional
import logging

import numpy as np
import cv2

from .base import FeatureExtractor


logger = logging.getLogger(__name__)


class ORBMatcher(FeatureExtractor):
    """
    ORB (Oriented FAST and Rotated BRIEF) feature extraction and matching implementation.
    
    ORB is particularly good for:
    - Real-time applications (very fast)
    - Rotation invariance
    - Good performance with limited computational resources
    - Binary descriptors (efficient storage and matching)
    
    This implementation provides configurable ORB parameters and efficient matching
    using Hamming distance for binary descriptors.
    """

    def __init__(self,
                 n_features: int = 500,
                 scale_factor: float = 1.2,
                 n_levels: int = 8,
                 edge_threshold: int = 31,
                 first_level: int = 0,
                 wta_k: int = 2,
                 patch_size: int = 31,
                 fast_threshold: int = 20,
                 cross_check: bool = True,
                 distance_threshold: Optional[int] = None):
        """
        Initialize ORB matcher with configurable parameters.
        
        Args:
            n_features: Maximum number of features to detect
            scale_factor: Pyramid decimation ratio (must be greater than 1)
            n_levels: Number of pyramid levels
            edge_threshold: Size of border where features are not detected
            first_level: Level of pyramid to put source image to
            wta_k: Number of points for oriented BRIEF descriptor
            patch_size: Size of patch used by oriented BRIEF descriptor
            fast_threshold: FAST threshold for keypoint detection
            cross_check: Enable cross-check in matching for better results
            distance_threshold: Maximum distance for matches (None = no threshold)
        """
        super().__init__()
        
        self.n_features = n_features
        self.scale_factor = scale_factor
        self.n_levels = n_levels
        self.edge_threshold = edge_threshold
        self.first_level = first_level
        self.wta_k = wta_k
        self.patch_size = patch_size
        self.fast_threshold = fast_threshold
        self.cross_check = cross_check
        self.distance_threshold = distance_threshold
        
        # Initialize ORB detector and descriptor
        self.orb = cv2.ORB_create(
            nfeatures=n_features,
            scaleFactor=scale_factor,
            nlevels=n_levels,
            edgeThreshold=edge_threshold,
            firstLevel=first_level,
            WTA_K=wta_k,
            patchSize=patch_size,
            fastThreshold=fast_threshold
        )
        
        # Initialize matcher for binary descriptors (Hamming distance)
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=cross_check)
        
        logger.info(f"ORB matcher initialized with {n_features} max features")

    @property
    def algorithm_name(self) -> str:
        """Get the algorithm name."""
        return "ORB"

    def extract_features(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
        """
        Extract ORB features from an image.
        
        Args:
            image: Input image (BGR, RGB, or grayscale)
            
        Returns:
            Tuple of (keypoints, descriptors) where descriptors are uint8 binary arrays
            
        Raises:
            ValueError: If image is invalid
            RuntimeError: If ORB feature extraction fails
        """
        self._validate_image(image)
        
        try:
            # Convert to grayscale
            gray = self._convert_to_grayscale(image)
            
            # Detect keypoints and compute descriptors
            keypoints, descriptors = self.orb.detectAndCompute(gray, None)
            
            # Convert keypoints tuple to list for consistency
            keypoints = list(keypoints) if keypoints is not None else []
            
            logger.debug(f"ORB extracted {len(keypoints)} keypoints")
            
            return keypoints, descriptors
            
        except cv2.error as e:
            logger.error(f"ORB feature extraction failed: {str(e)}")
            raise RuntimeError(f"ORB feature extraction failed: {str(e)}") from e

    def match_features(self, descriptors1: Optional[np.ndarray], 
                      descriptors2: Optional[np.ndarray],
                      cross_check: Optional[bool] = None,
                      distance_threshold: Optional[int] = None) -> List[cv2.DMatch]:
        """
        Match ORB features between two sets of descriptors.
        
        Uses Hamming distance matching optimized for binary descriptors.
        
        Args:
            descriptors1: ORB descriptors from first image
            descriptors2: ORB descriptors from second image
            cross_check: Override default cross-check setting
            distance_threshold: Override default distance threshold
            
        Returns:
            List of matches, optionally filtered by distance threshold
            
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
            # Use appropriate matcher based on cross_check parameter
            use_cross_check = cross_check if cross_check is not None else self.cross_check
            use_threshold = distance_threshold if distance_threshold is not None else self.distance_threshold
            
            if use_cross_check != self.cross_check:
                # Create temporary matcher with different cross-check setting
                temp_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=use_cross_check)
                matches = temp_matcher.match(descriptors1, descriptors2)
            else:
                matches = self.matcher.match(descriptors1, descriptors2)
            
            # Sort matches by distance (best matches first)
            matches = sorted(matches, key=lambda x: x.distance)
            
            # Apply distance threshold if specified
            if use_threshold is not None:
                matches = [m for m in matches if m.distance <= use_threshold]
            
            logger.debug(f"ORB matching: {len(matches)} matches after filtering")
            
            return matches
            
        except cv2.error as e:
            logger.error(f"ORB matching failed: {str(e)}")
            return []

    def _calculate_confidence_score(self, matches: List[cv2.DMatch]) -> float:
        """
        Calculate confidence score specific to ORB matches.
        
        ORB confidence considers:
        - Number of matches (more matches = higher confidence)  
        - Hamming distances (lower distances = higher confidence)
        - Distribution and consistency of matches
        
        Args:
            matches: List of ORB matches
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not matches:
            return 0.0
        
        # ORB-specific confidence calculation
        distances = [match.distance for match in matches]
        
        # Hamming distances for ORB are typically 0-256, with good matches < 50
        mean_distance = np.mean(distances)
        max_expected_distance = 100.0  # Reasonable threshold for ORB
        distance_confidence = max(0.0, 1.0 - (mean_distance / max_expected_distance))
        
        # Factor in number of matches
        match_count = len(matches)
        if match_count >= 20:
            count_confidence = 1.0
        elif match_count >= 10:
            count_confidence = 0.8
        elif match_count >= 4:
            count_confidence = match_count / 10.0
        else:
            count_confidence = 0.2  # Low confidence for very few matches
        
        # Consider the quality distribution of matches
        if len(distances) > 1:
            distance_std = np.std(distances)
            consistency_factor = max(0.0, 1.0 - (distance_std / max_expected_distance))
        else:
            consistency_factor = 0.5
        
        # Combine factors with ORB-specific weighting
        confidence = (distance_confidence * 0.5) + (count_confidence * 0.35) + (consistency_factor * 0.15)
        
        return max(0.0, min(1.0, confidence))

    def match_with_ratio_test(self, descriptors1: Optional[np.ndarray],
                             descriptors2: Optional[np.ndarray],
                             ratio: float = 0.8) -> List[cv2.DMatch]:
        """
        Match features using k-nearest neighbor with ratio test.
        
        Alternative matching method that can provide better results
        for certain scenarios by using the ratio test.
        
        Args:
            descriptors1: ORB descriptors from first image
            descriptors2: ORB descriptors from second image
            ratio: Ratio threshold for filtering (typically 0.8 for ORB)
            
        Returns:
            List of good matches after ratio test
        """
        if descriptors1 is None or descriptors2 is None:
            return []
        
        if len(descriptors1) == 0 or len(descriptors2) == 0:
            return []
        
        try:
            # Use BFMatcher without cross-check for knnMatch
            temp_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
            raw_matches = temp_matcher.knnMatch(descriptors1, descriptors2, k=2)
            
            # Apply ratio test
            good_matches = []
            for match_pair in raw_matches:
                if len(match_pair) == 2:
                    best_match, second_match = match_pair
                    if best_match.distance < ratio * second_match.distance:
                        good_matches.append(best_match)
            
            logger.debug(f"ORB ratio test: {len(raw_matches)} raw -> {len(good_matches)} good matches")
            
            return good_matches
            
        except cv2.error as e:
            logger.error(f"ORB ratio test matching failed: {str(e)}")
            return []

    def estimate_affine_transform(self, keypoints1: List[cv2.KeyPoint],
                                keypoints2: List[cv2.KeyPoint],
                                matches: List[cv2.DMatch]) -> Tuple[Optional[np.ndarray], List[cv2.DMatch]]:
        """
        Estimate affine transformation and filter matches using RANSAC.
        
        This method can be used to filter outliers and get geometric consistency.
        
        Args:
            keypoints1: Keypoints from first image
            keypoints2: Keypoints from second image
            matches: Initial matches
            
        Returns:
            Tuple of (transformation_matrix, inlier_matches)
        """
        if len(matches) < 4:
            return None, matches
        
        try:
            # Extract matched point coordinates
            points1 = np.float32([keypoints1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            points2 = np.float32([keypoints2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            
            # Estimate affine transformation using RANSAC
            transform_matrix, mask = cv2.estimateAffinePartial2D(
                points1, points2, method=cv2.RANSAC, ransacReprojThreshold=3.0
            )
            
            # Filter inlier matches
            if mask is not None:
                inlier_matches = [matches[i] for i, m in enumerate(mask.ravel()) if m]
            else:
                inlier_matches = matches
            
            logger.debug(f"Affine transform: {len(matches)} -> {len(inlier_matches)} inliers")
            
            return transform_matrix, inlier_matches
            
        except cv2.error as e:
            logger.error(f"Affine transformation estimation failed: {str(e)}")
            return None, matches

    def get_algorithm_info(self) -> dict:
        """Get detailed information about ORB configuration."""
        info = super().get_algorithm_info()
        info.update({
            'n_features': self.n_features,
            'scale_factor': self.scale_factor,
            'n_levels': self.n_levels,
            'edge_threshold': self.edge_threshold,
            'first_level': self.first_level,
            'wta_k': self.wta_k,
            'patch_size': self.patch_size,
            'fast_threshold': self.fast_threshold,
            'cross_check': self.cross_check,
            'distance_threshold': self.distance_threshold,
            'descriptor_size': 32,
            'descriptor_type': 'uint8_binary'
        })
        return info