# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Tuple, Optional, Union, Dict, Any
import time
import logging

import numpy as np
import cv2


logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """
    Data class to encapsulate the results of feature matching operations.
    
    Attributes:
        matches: List of OpenCV DMatch objects representing correspondences
        keypoints1: List of keypoints detected in the first image
        keypoints2: List of keypoints detected in the second image
        descriptors1: Feature descriptors for the first image (optional)
        descriptors2: Feature descriptors for the second image (optional)
        algorithm: Name of the algorithm used for matching
        confidence_score: Overall confidence score of the matching (0-1, optional)
        processing_time: Time taken for the matching operation in seconds (optional)
    """
    matches: List[cv2.DMatch]
    keypoints1: List[cv2.KeyPoint]
    keypoints2: List[cv2.KeyPoint]
    descriptors1: Optional[np.ndarray]
    descriptors2: Optional[np.ndarray]
    algorithm: str
    confidence_score: Optional[float] = None
    processing_time: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert MatchResult to a dictionary representation.
        
        Returns:
            Dictionary containing match result summary
        """
        return {
            'algorithm': self.algorithm,
            'num_matches': len(self.matches),
            'num_keypoints1': len(self.keypoints1),
            'num_keypoints2': len(self.keypoints2),
            'confidence_score': self.confidence_score,
            'processing_time': self.processing_time,
            'has_descriptors1': self.descriptors1 is not None,
            'has_descriptors2': self.descriptors2 is not None,
        }


class FeatureExtractor(ABC):
    """
    Abstract base class for computer vision feature extraction and matching algorithms.
    
    This class defines the interface that all feature extraction algorithms must implement,
    including SIFT, ORB, and template matching. It provides a consistent API for:
    - Feature extraction from images
    - Feature matching between image pairs
    - Complete processing pipelines
    - Performance monitoring and validation
    
    Subclasses must implement the core abstract methods while leveraging the common
    functionality provided by this base class.
    """

    def __init__(self):
        """Initialize the feature extractor."""
        self._initialize_logger()

    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        """
        Get the name of the algorithm.
        
        Returns:
            String identifier for the algorithm (e.g., "SIFT", "ORB", "Template")
        """
        pass

    @abstractmethod
    def extract_features(self, image: np.ndarray) -> Tuple[List[cv2.KeyPoint], Optional[np.ndarray]]:
        """
        Extract features from an image.
        
        Args:
            image: Input image as numpy array (BGR or grayscale)
            
        Returns:
            Tuple of (keypoints, descriptors) where:
            - keypoints: List of cv2.KeyPoint objects
            - descriptors: numpy array of feature descriptors (or None for template matching)
            
        Raises:
            ValueError: If image is invalid
            RuntimeError: If feature extraction fails
        """
        pass

    @abstractmethod
    def match_features(self, descriptors1: Optional[np.ndarray], 
                      descriptors2: Optional[np.ndarray]) -> List[cv2.DMatch]:
        """
        Match features between two sets of descriptors.
        
        Args:
            descriptors1: Feature descriptors from first image
            descriptors2: Feature descriptors from second image
            
        Returns:
            List of cv2.DMatch objects representing feature correspondences
            
        Raises:
            ValueError: If descriptors are incompatible
        """
        pass

    def process_images(self, image1: np.ndarray, image2: np.ndarray) -> MatchResult:
        """
        Process two images through the complete matching pipeline.
        
        This method orchestrates the entire matching process:
        1. Validates input images
        2. Extracts features from both images
        3. Matches features between images
        4. Calculates confidence scores
        5. Measures performance metrics
        
        Args:
            image1: First image as numpy array
            image2: Second image as numpy array
            
        Returns:
            MatchResult object containing all matching information
            
        Raises:
            ValueError: If images are invalid
            RuntimeError: If processing fails
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            self._validate_image(image1)
            self._validate_image(image2)
            
            # Extract features from both images
            logger.debug(f"Extracting features using {self.algorithm_name}")
            keypoints1, descriptors1 = self.extract_features(image1)
            keypoints2, descriptors2 = self.extract_features(image2)
            
            # Match features
            matches = self.match_features(descriptors1, descriptors2)
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(matches)
            
            processing_time = time.time() - start_time
            
            result = MatchResult(
                matches=matches,
                keypoints1=keypoints1,
                keypoints2=keypoints2,
                descriptors1=descriptors1,
                descriptors2=descriptors2,
                algorithm=self.algorithm_name,
                confidence_score=confidence_score,
                processing_time=processing_time
            )
            
            logger.info(f"{self.algorithm_name} processing completed: "
                       f"{len(matches)} matches, {confidence_score:.3f} confidence, "
                       f"{processing_time:.3f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"{self.algorithm_name} processing failed: {str(e)}")
            raise RuntimeError(f"{self.algorithm_name} processing failed: {str(e)}") from e

    def _validate_image(self, image: np.ndarray) -> None:
        """
        Validate that an image is suitable for processing.
        
        Args:
            image: Input image to validate
            
        Raises:
            ValueError: If image is invalid
        """
        if image is None:
            raise ValueError("Image cannot be None")
        
        if not isinstance(image, np.ndarray):
            raise ValueError(f"Image must be numpy array, got {type(image)}")
        
        if image.size == 0:
            raise ValueError("Image cannot be empty")
        
        if len(image.shape) not in [2, 3]:
            raise ValueError(f"Image must be 2D or 3D array, got {len(image.shape)}D")
        
        if len(image.shape) == 3 and image.shape[2] not in [3, 4]:
            raise ValueError(f"Color images must have 3 or 4 channels, got {image.shape[2]}")
        
        # Check reasonable size constraints
        min_size = 10
        max_size = 10000
        h, w = image.shape[:2]
        
        if h < min_size or w < min_size:
            raise ValueError(f"Image too small: {h}x{w}. Minimum size: {min_size}x{min_size}")
        
        if h > max_size or w > max_size:
            raise ValueError(f"Image too large: {h}x{w}. Maximum size: {max_size}x{max_size}")

    def _convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Convert image to grayscale if needed.
        
        Args:
            image: Input image (BGR, RGB, BGRA, RGBA, or grayscale)
            
        Returns:
            Grayscale image as 2D numpy array
        """
        if len(image.shape) == 2:
            # Already grayscale
            return image
        elif len(image.shape) == 3:
            if image.shape[2] == 3:
                # Assume BGR color space (OpenCV default)
                return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            elif image.shape[2] == 4:
                # BGRA or RGBA
                return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        
        raise ValueError(f"Unsupported image format: {image.shape}")

    def _calculate_confidence_score(self, matches: List[cv2.DMatch]) -> float:
        """
        Calculate a confidence score based on the quality of matches.
        
        Default implementation uses match distances and count.
        Subclasses can override for algorithm-specific confidence calculation.
        
        Args:
            matches: List of feature matches
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not matches:
            return 0.0
        
        # Calculate confidence based on match distances
        distances = [match.distance for match in matches]
        
        # Normalize distances (lower is better)
        mean_distance = np.mean(distances)
        max_distance = max(distances) if distances else 1.0
        
        # Convert to confidence score (higher is better)
        if max_distance > 0:
            distance_confidence = 1.0 - (mean_distance / max_distance)
        else:
            distance_confidence = 1.0
        
        # Factor in the number of matches
        match_count_factor = min(1.0, len(matches) / 10.0)  # Normalize to 10 good matches
        
        # Combine factors
        confidence = (distance_confidence * 0.7) + (match_count_factor * 0.3)
        
        return max(0.0, min(1.0, confidence))

    def _initialize_logger(self) -> None:
        """Initialize logging for the feature extractor."""
        logger.setLevel(logging.INFO)
        
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    def get_algorithm_info(self) -> Dict[str, Any]:
        """
        Get information about the algorithm configuration.
        
        Returns:
            Dictionary containing algorithm metadata
        """
        return {
            'algorithm_name': self.algorithm_name,
            'class_name': self.__class__.__name__,
            'module': self.__class__.__module__,
        }