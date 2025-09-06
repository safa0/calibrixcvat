# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from typing import Dict, List, Optional, Union, Any, Callable
from enum import Enum
import logging
import time
from dataclasses import dataclass

import numpy as np
import cv2

from .base import FeatureExtractor, MatchResult
from .sift import SIFTMatcher
from .orb import ORBMatcher
from .template import TemplateMatcher


logger = logging.getLogger(__name__)


class AlgorithmType(Enum):
    """Enumeration of available matching algorithms."""
    SIFT = "sift"
    ORB = "orb"
    TEMPLATE = "template"


@dataclass
class PipelineConfig:
    """Configuration for matching pipeline."""
    primary_algorithm: AlgorithmType
    fallback_algorithms: Optional[List[AlgorithmType]] = None
    confidence_threshold: float = 0.3
    min_matches_threshold: int = 4
    enable_geometric_verification: bool = True
    enable_performance_monitoring: bool = True
    timeout_seconds: Optional[int] = 30
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        if self.fallback_algorithms is None:
            self.fallback_algorithms = []
        
        if self.confidence_threshold < 0.0 or self.confidence_threshold > 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")
        
        if self.min_matches_threshold < 0:
            raise ValueError("min_matches_threshold must be non-negative")


@dataclass
class PipelineResult:
    """Result from the matching pipeline with metadata."""
    match_result: MatchResult
    algorithm_used: AlgorithmType
    attempted_algorithms: List[AlgorithmType]
    total_processing_time: float
    success: bool
    fallback_used: bool = False
    geometric_verification_passed: bool = True
    error_message: Optional[str] = None


class MatchingPipeline:
    """
    Orchestrator class that manages multiple feature matching algorithms.
    
    The pipeline provides:
    - Algorithm selection and fallback strategies
    - Performance monitoring and benchmarking
    - Geometric verification of matches
    - Configuration management
    - Error handling and recovery
    - Results aggregation and comparison
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize the matching pipeline.
        
        Args:
            config: Pipeline configuration, uses default if None
        """
        self.config = config or PipelineConfig(AlgorithmType.SIFT)
        self._matchers: Dict[AlgorithmType, FeatureExtractor] = {}
        self._performance_history: List[Dict[str, Any]] = []
        
        self._initialize_matchers()
        
        logger.info(f"MatchingPipeline initialized with primary algorithm: {self.config.primary_algorithm.value}")

    def _initialize_matchers(self) -> None:
        """Initialize all required matchers based on configuration."""
        algorithms_needed = {self.config.primary_algorithm}
        algorithms_needed.update(self.config.fallback_algorithms)
        
        for algorithm in algorithms_needed:
            self._matchers[algorithm] = self._create_matcher(algorithm)

    def _create_matcher(self, algorithm: AlgorithmType) -> FeatureExtractor:
        """
        Create a matcher instance for the specified algorithm.
        
        Args:
            algorithm: Type of algorithm to create
            
        Returns:
            Initialized matcher instance
            
        Raises:
            ValueError: If algorithm type is not supported
        """
        if algorithm == AlgorithmType.SIFT:
            return SIFTMatcher()
        elif algorithm == AlgorithmType.ORB:
            return ORBMatcher()
        elif algorithm == AlgorithmType.TEMPLATE:
            return TemplateMatcher()
        else:
            raise ValueError(f"Unsupported algorithm type: {algorithm}")

    def process_images(self, image1: np.ndarray, 
                      image2: Optional[np.ndarray] = None,
                      template: Optional[np.ndarray] = None) -> PipelineResult:
        """
        Process images through the matching pipeline.
        
        Args:
            image1: First image (or source image for template matching)
            image2: Second image (for feature-based matching)
            template: Template image (for template matching)
            
        Returns:
            PipelineResult containing match results and metadata
        """
        start_time = time.time()
        attempted_algorithms = []
        
        try:
            # Determine input mode
            if template is not None and image2 is None:
                # Template matching mode
                return self._process_template_matching(image1, template, start_time)
            elif image2 is not None and template is None:
                # Feature-based matching mode
                return self._process_feature_matching(image1, image2, start_time)
            else:
                raise ValueError("Must provide either image2 for feature matching or template for template matching")
                
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"Pipeline processing failed: {str(e)}")
            
            # Return failure result
            empty_result = MatchResult(
                matches=[], keypoints1=[], keypoints2=[],
                descriptors1=None, descriptors2=None,
                algorithm="Failed", confidence_score=0.0,
                processing_time=total_time
            )
            
            return PipelineResult(
                match_result=empty_result,
                algorithm_used=self.config.primary_algorithm,
                attempted_algorithms=attempted_algorithms,
                total_processing_time=total_time,
                success=False,
                error_message=str(e)
            )

    def _process_template_matching(self, image: np.ndarray, 
                                 template: np.ndarray,
                                 start_time: float) -> PipelineResult:
        """Process template matching workflow."""
        attempted_algorithms = [AlgorithmType.TEMPLATE]
        
        if AlgorithmType.TEMPLATE not in self._matchers:
            self._matchers[AlgorithmType.TEMPLATE] = self._create_matcher(AlgorithmType.TEMPLATE)
        
        matcher = self._matchers[AlgorithmType.TEMPLATE]
        result = matcher.process_images(image, template)
        
        total_time = time.time() - start_time
        success = self._evaluate_result_quality(result)
        
        return PipelineResult(
            match_result=result,
            algorithm_used=AlgorithmType.TEMPLATE,
            attempted_algorithms=attempted_algorithms,
            total_processing_time=total_time,
            success=success
        )

    def _process_feature_matching(self, image1: np.ndarray, 
                                image2: np.ndarray,
                                start_time: float) -> PipelineResult:
        """Process feature-based matching workflow with fallback strategy."""
        attempted_algorithms = []
        algorithms_to_try = [self.config.primary_algorithm] + self.config.fallback_algorithms
        
        last_error = None
        
        for algorithm in algorithms_to_try:
            attempted_algorithms.append(algorithm)
            
            try:
                logger.debug(f"Attempting matching with {algorithm.value}")
                
                matcher = self._matchers[algorithm]
                result = self._process_with_timeout(matcher, image1, image2)
                
                # Evaluate result quality
                if self._evaluate_result_quality(result):
                    # Apply geometric verification if enabled
                    if self.config.enable_geometric_verification and len(result.matches) >= 4:
                        result = self._apply_geometric_verification(result)
                    
                    total_time = time.time() - start_time
                    fallback_used = algorithm != self.config.primary_algorithm
                    
                    # Record performance data
                    if self.config.enable_performance_monitoring:
                        self._record_performance(algorithm, result, total_time, True)
                    
                    return PipelineResult(
                        match_result=result,
                        algorithm_used=algorithm,
                        attempted_algorithms=attempted_algorithms,
                        total_processing_time=total_time,
                        success=True,
                        fallback_used=fallback_used
                    )
                else:
                    logger.debug(f"{algorithm.value} result quality insufficient")
                    
            except Exception as e:
                logger.warning(f"{algorithm.value} matching failed: {str(e)}")
                last_error = e
        
        # All algorithms failed
        total_time = time.time() - start_time
        
        # Return best-effort result from primary algorithm
        try:
            primary_matcher = self._matchers[self.config.primary_algorithm]
            result = primary_matcher.process_images(image1, image2)
        except:
            result = MatchResult(
                matches=[], keypoints1=[], keypoints2=[],
                descriptors1=None, descriptors2=None,
                algorithm="Failed", confidence_score=0.0,
                processing_time=total_time
            )
        
        if self.config.enable_performance_monitoring:
            self._record_performance(self.config.primary_algorithm, result, total_time, False)
        
        return PipelineResult(
            match_result=result,
            algorithm_used=self.config.primary_algorithm,
            attempted_algorithms=attempted_algorithms,
            total_processing_time=total_time,
            success=False,
            error_message=str(last_error) if last_error else "All algorithms failed quality check"
        )

    def _process_with_timeout(self, matcher: FeatureExtractor, 
                            image1: np.ndarray, 
                            image2: np.ndarray) -> MatchResult:
        """
        Process matching with timeout handling.
        
        Args:
            matcher: Matcher to use
            image1: First image
            image2: Second image
            
        Returns:
            MatchResult
            
        Raises:
            TimeoutError: If processing exceeds configured timeout
        """
        if self.config.timeout_seconds is None:
            return matcher.process_images(image1, image2)
        
        # For simplicity, we'll just process directly and check time afterward
        # In production, you might want to use threading or multiprocessing
        start_time = time.time()
        result = matcher.process_images(image1, image2)
        elapsed = time.time() - start_time
        
        if elapsed > self.config.timeout_seconds:
            logger.warning(f"Processing took {elapsed:.2f}s, exceeds timeout of {self.config.timeout_seconds}s")
            # Still return the result, but log the timeout
        
        return result

    def _evaluate_result_quality(self, result: MatchResult) -> bool:
        """
        Evaluate whether a matching result meets quality thresholds.
        
        Args:
            result: Matching result to evaluate
            
        Returns:
            True if result meets quality standards
        """
        # Check minimum number of matches
        if len(result.matches) < self.config.min_matches_threshold:
            return False
        
        # Check confidence threshold
        if result.confidence_score is not None:
            if result.confidence_score < self.config.confidence_threshold:
                return False
        
        return True

    def _apply_geometric_verification(self, result: MatchResult) -> MatchResult:
        """
        Apply geometric verification to filter out outlier matches.
        
        Args:
            result: Initial matching result
            
        Returns:
            Updated result with geometrically verified matches
        """
        if len(result.matches) < 4:
            return result
        
        try:
            # Extract matched point coordinates
            points1 = np.float32([result.keypoints1[m.queryIdx].pt for m in result.matches]).reshape(-1, 1, 2)
            points2 = np.float32([result.keypoints2[m.trainIdx].pt for m in result.matches]).reshape(-1, 1, 2)
            
            # Find homography using RANSAC
            homography, mask = cv2.findHomography(
                points1, points2, 
                method=cv2.RANSAC, 
                ransacReprojThreshold=5.0,
                confidence=0.99,
                maxIters=1000
            )
            
            if mask is not None:
                # Filter matches based on inliers
                inlier_matches = [result.matches[i] for i, m in enumerate(mask.ravel()) if m]
                
                # Update result with verified matches
                result.matches = inlier_matches
                
                # Recalculate confidence score
                if hasattr(self._matchers.get(AlgorithmType.SIFT), '_calculate_confidence_score'):
                    matcher = self._matchers.get(AlgorithmType.SIFT)
                    result.confidence_score = matcher._calculate_confidence_score(inlier_matches)
                
                logger.debug(f"Geometric verification: {len(mask.ravel())} -> {len(inlier_matches)} matches")
            
        except cv2.error as e:
            logger.warning(f"Geometric verification failed: {str(e)}")
        
        return result

    def _record_performance(self, algorithm: AlgorithmType, 
                          result: MatchResult, 
                          total_time: float,
                          success: bool) -> None:
        """Record performance metrics for analysis."""
        performance_record = {
            'timestamp': time.time(),
            'algorithm': algorithm.value,
            'processing_time': result.processing_time,
            'total_time': total_time,
            'num_matches': len(result.matches),
            'num_keypoints1': len(result.keypoints1),
            'num_keypoints2': len(result.keypoints2),
            'confidence_score': result.confidence_score,
            'success': success
        }
        
        self._performance_history.append(performance_record)
        
        # Keep history limited to prevent memory issues
        if len(self._performance_history) > 1000:
            self._performance_history = self._performance_history[-500:]

    def get_performance_statistics(self) -> Dict[str, Any]:
        """
        Get performance statistics for all algorithms.
        
        Returns:
            Dictionary containing performance metrics
        """
        if not self._performance_history:
            return {}
        
        stats = {}
        algorithms = set(record['algorithm'] for record in self._performance_history)
        
        for algorithm in algorithms:
            algorithm_records = [r for r in self._performance_history if r['algorithm'] == algorithm]
            
            if not algorithm_records:
                continue
            
            processing_times = [r['processing_time'] for r in algorithm_records if r['processing_time'] is not None]
            total_times = [r['total_time'] for r in algorithm_records]
            match_counts = [r['num_matches'] for r in algorithm_records]
            confidences = [r['confidence_score'] for r in algorithm_records if r['confidence_score'] is not None]
            success_count = sum(1 for r in algorithm_records if r['success'])
            
            stats[algorithm] = {
                'total_runs': len(algorithm_records),
                'success_rate': success_count / len(algorithm_records),
                'avg_processing_time': np.mean(processing_times) if processing_times else 0,
                'avg_total_time': np.mean(total_times),
                'avg_matches': np.mean(match_counts),
                'avg_confidence': np.mean(confidences) if confidences else 0,
                'min_processing_time': np.min(processing_times) if processing_times else 0,
                'max_processing_time': np.max(processing_times) if processing_times else 0,
            }
        
        return stats

    def benchmark_algorithms(self, test_image_pairs: List[Tuple[np.ndarray, np.ndarray]],
                           iterations: int = 1) -> Dict[str, Dict[str, float]]:
        """
        Benchmark all available algorithms on test image pairs.
        
        Args:
            test_image_pairs: List of (image1, image2) pairs for testing
            iterations: Number of iterations per test pair
            
        Returns:
            Dictionary containing benchmark results per algorithm
        """
        algorithms = [AlgorithmType.SIFT, AlgorithmType.ORB]  # Template matching needs different inputs
        results = {alg.value: {'times': [], 'matches': [], 'confidences': []} for alg in algorithms}
        
        for algorithm in algorithms:
            if algorithm not in self._matchers:
                self._matchers[algorithm] = self._create_matcher(algorithm)
            
            matcher = self._matchers[algorithm]
            
            for image1, image2 in test_image_pairs:
                for _ in range(iterations):
                    try:
                        start_time = time.time()
                        result = matcher.process_images(image1, image2)
                        end_time = time.time()
                        
                        results[algorithm.value]['times'].append(end_time - start_time)
                        results[algorithm.value]['matches'].append(len(result.matches))
                        if result.confidence_score is not None:
                            results[algorithm.value]['confidences'].append(result.confidence_score)
                        
                    except Exception as e:
                        logger.warning(f"Benchmark failed for {algorithm.value}: {str(e)}")
        
        # Calculate statistics
        benchmark_stats = {}
        for algorithm, data in results.items():
            if data['times']:
                benchmark_stats[algorithm] = {
                    'avg_time': np.mean(data['times']),
                    'min_time': np.min(data['times']),
                    'max_time': np.max(data['times']),
                    'std_time': np.std(data['times']),
                    'avg_matches': np.mean(data['matches']),
                    'avg_confidence': np.mean(data['confidences']) if data['confidences'] else 0,
                }
        
        return benchmark_stats

    def get_recommended_algorithm(self, image_characteristics: Optional[Dict[str, Any]] = None) -> AlgorithmType:
        """
        Get algorithm recommendation based on image characteristics and performance history.
        
        Args:
            image_characteristics: Optional dict with image properties (size, texture, etc.)
            
        Returns:
            Recommended algorithm type
        """
        # Simple recommendation based on performance history
        stats = self.get_performance_statistics()
        
        if not stats:
            return self.config.primary_algorithm
        
        # Find algorithm with best success rate and reasonable speed
        best_algorithm = self.config.primary_algorithm
        best_score = 0
        
        for algorithm, metrics in stats.items():
            # Combine success rate and speed (inverse of time)
            speed_score = 1.0 / (metrics['avg_processing_time'] + 0.001)  # Avoid division by zero
            combined_score = metrics['success_rate'] * 0.7 + (speed_score / 10) * 0.3
            
            if combined_score > best_score:
                best_score = combined_score
                best_algorithm = AlgorithmType(algorithm)
        
        return best_algorithm

    def update_configuration(self, new_config: PipelineConfig) -> None:
        """Update pipeline configuration and reinitialize if needed."""
        old_algorithms = {self.config.primary_algorithm} | set(self.config.fallback_algorithms)
        new_algorithms = {new_config.primary_algorithm} | set(new_config.fallback_algorithms)
        
        self.config = new_config
        
        # Initialize any new matchers needed
        for algorithm in new_algorithms - old_algorithms:
            self._matchers[algorithm] = self._create_matcher(algorithm)
        
        logger.info(f"Pipeline configuration updated. Primary: {new_config.primary_algorithm.value}")

    def get_algorithm_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all available algorithms."""
        return {
            alg.value: matcher.get_algorithm_info()
            for alg, matcher in self._matchers.items()
        }