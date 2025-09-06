# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import logging
import numpy as np
from collections import defaultdict, Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from pathlib import Path

from django.db.models import Q, Avg, Count, StdDev
from django.utils import timezone

from ..models import DetectionResult, MatchingSession, ROITemplate

logger = logging.getLogger(__name__)


@dataclass
class QualityMetric:
    """Represents a quality control metric."""
    name: str
    value: float
    threshold: float
    passed: bool
    message: str
    severity: str = 'info'  # info, warning, error


@dataclass
class ValidationResult:
    """Result of a validation check."""
    check_name: str
    passed: bool
    issues: List[Dict[str, Any]]
    metrics: List[QualityMetric]
    message: str


class AdvancedQualityController:
    """Advanced quality control system for detection data."""
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.logger = logging.getLogger(f"{__name__}.AdvancedQualityController")
        
        # Default quality thresholds
        self.thresholds = {
            'min_confidence': 0.1,
            'max_duplicate_iou': 0.8,
            'min_bbox_area': 100,  # pixels
            'max_bbox_aspect_ratio': 10.0,
            'min_detections_per_frame': 0,
            'max_detections_per_frame': 50,
            'confidence_std_threshold': 0.3,
            'frame_coverage_threshold': 0.1  # minimum 10% frame coverage
        }
    
    def run_comprehensive_validation(
        self, 
        detections: List[DetectionResult],
        custom_thresholds: Optional[Dict[str, float]] = None
    ) -> Dict[str, ValidationResult]:
        """Run comprehensive validation on detection data."""
        
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)
        
        validation_results = {}
        
        # Coordinate validation
        validation_results['coordinates'] = self._validate_coordinates(detections)
        
        # Confidence validation
        validation_results['confidence'] = self._validate_confidence_scores(detections)
        
        # Duplicate detection
        validation_results['duplicates'] = self._detect_duplicates(detections)
        
        # Bounding box validation
        validation_results['bounding_boxes'] = self._validate_bounding_boxes(detections)
        
        # Frame distribution validation
        validation_results['frame_distribution'] = self._validate_frame_distribution(detections)
        
        # Confidence consistency validation
        validation_results['confidence_consistency'] = self._validate_confidence_consistency(detections)
        
        # Temporal consistency validation
        validation_results['temporal_consistency'] = self._validate_temporal_consistency(detections)
        
        # ROI template distribution validation
        validation_results['roi_distribution'] = self._validate_roi_distribution(detections)
        
        # Data completeness validation
        validation_results['completeness'] = self._validate_data_completeness(detections)
        
        # Statistical anomaly detection
        validation_results['anomalies'] = self._detect_statistical_anomalies(detections)
        
        return validation_results
    
    def _validate_coordinates(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate bounding box coordinates."""
        issues = []
        valid_count = 0
        
        for detection in detections:
            coords = detection.coordinates
            
            # Check required fields
            required_fields = {'x', 'y', 'width', 'height'}
            missing_fields = required_fields - set(coords.keys())
            
            if missing_fields:
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'missing_coordinate_fields',
                    'details': f"Missing fields: {missing_fields}"
                })
                continue
            
            # Check numeric values
            try:
                x, y, w, h = float(coords['x']), float(coords['y']), \
                           float(coords['width']), float(coords['height'])
            except (ValueError, TypeError):
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'invalid_coordinate_values',
                    'details': "Coordinate values must be numeric"
                })
                continue
            
            # Check for negative or zero dimensions
            if w <= 0 or h <= 0:
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'invalid_dimensions',
                    'details': f"Width: {w}, Height: {h} - must be positive"
                })
                continue
            
            # Check for negative coordinates
            if x < 0 or y < 0:
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'negative_coordinates',
                    'details': f"X: {x}, Y: {y} - coordinates cannot be negative"
                })
                continue
            
            valid_count += 1
        
        total_count = len(detections)
        validity_rate = valid_count / total_count if total_count > 0 else 0
        
        metrics = [
            QualityMetric(
                name="coordinate_validity_rate",
                value=validity_rate,
                threshold=0.95,
                passed=validity_rate >= 0.95,
                message=f"{valid_count}/{total_count} detections have valid coordinates"
            )
        ]
        
        return ValidationResult(
            check_name="coordinate_validation",
            passed=len(issues) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Found {len(issues)} coordinate issues out of {total_count} detections"
        )
    
    def _validate_confidence_scores(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate confidence scores."""
        issues = []
        valid_scores = []
        
        for detection in detections:
            score = detection.confidence_score
            
            if score is None:
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'missing_confidence_score',
                    'details': "Confidence score is None"
                })
                continue
            
            try:
                float_score = float(score)
            except (ValueError, TypeError):
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'invalid_confidence_score',
                    'details': f"Score '{score}' is not numeric"
                })
                continue
            
            if not (0.0 <= float_score <= 1.0):
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'confidence_out_of_range',
                    'details': f"Score {float_score} not in range [0, 1]"
                })
                continue
            
            if float_score < self.thresholds['min_confidence']:
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'low_confidence_score',
                    'details': f"Score {float_score} below threshold {self.thresholds['min_confidence']}"
                })
            
            valid_scores.append(float_score)
        
        # Calculate metrics
        metrics = []
        if valid_scores:
            avg_confidence = np.mean(valid_scores)
            std_confidence = np.std(valid_scores)
            min_confidence = np.min(valid_scores)
            max_confidence = np.max(valid_scores)
            
            metrics.extend([
                QualityMetric(
                    name="average_confidence",
                    value=avg_confidence,
                    threshold=0.5,
                    passed=avg_confidence >= 0.5,
                    message=f"Average confidence: {avg_confidence:.3f}"
                ),
                QualityMetric(
                    name="confidence_std",
                    value=std_confidence,
                    threshold=self.thresholds['confidence_std_threshold'],
                    passed=std_confidence <= self.thresholds['confidence_std_threshold'],
                    message=f"Confidence std: {std_confidence:.3f}"
                ),
                QualityMetric(
                    name="min_confidence",
                    value=min_confidence,
                    threshold=self.thresholds['min_confidence'],
                    passed=min_confidence >= self.thresholds['min_confidence'],
                    message=f"Minimum confidence: {min_confidence:.3f}"
                )
            ])
        
        return ValidationResult(
            check_name="confidence_validation",
            passed=len([issue for issue in issues if issue['issue'] != 'low_confidence_score']) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Found {len(issues)} confidence issues"
        )
    
    def _detect_duplicates(self, detections: List[DetectionResult]) -> ValidationResult:
        """Detect duplicate detections."""
        issues = []
        duplicates_found = []
        
        # Group by frame
        frame_groups = defaultdict(list)
        for detection in detections:
            frame_groups[detection.frame_number].append(detection)
        
        for frame_number, frame_detections in frame_groups.items():
            for i, det1 in enumerate(frame_detections):
                for j, det2 in enumerate(frame_detections[i + 1:], i + 1):
                    iou = self._calculate_iou(det1.coordinates, det2.coordinates)
                    
                    if iou > self.thresholds['max_duplicate_iou']:
                        duplicate_pair = (det1.id, det2.id)
                        if duplicate_pair not in duplicates_found:
                            duplicates_found.append(duplicate_pair)
                            issues.append({
                                'detection_ids': [det1.id, det2.id],
                                'frame_number': frame_number,
                                'issue': 'duplicate_detection',
                                'details': f"IoU: {iou:.3f}, above threshold {self.thresholds['max_duplicate_iou']}"
                            })
        
        duplicate_rate = len(duplicates_found) / len(detections) if len(detections) > 0 else 0
        
        metrics = [
            QualityMetric(
                name="duplicate_rate",
                value=duplicate_rate,
                threshold=0.05,
                passed=duplicate_rate <= 0.05,
                message=f"{len(duplicates_found)} duplicate pairs found"
            )
        ]
        
        return ValidationResult(
            check_name="duplicate_detection",
            passed=len(duplicates_found) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Found {len(duplicates_found)} duplicate detection pairs"
        )
    
    def _validate_bounding_boxes(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate bounding box properties."""
        issues = []
        areas = []
        aspect_ratios = []
        
        for detection in detections:
            coords = detection.coordinates
            
            try:
                width = float(coords['width'])
                height = float(coords['height'])
                area = width * height
                aspect_ratio = max(width, height) / min(width, height)
                
                areas.append(area)
                aspect_ratios.append(aspect_ratio)
                
                # Check minimum area
                if area < self.thresholds['min_bbox_area']:
                    issues.append({
                        'detection_id': detection.id,
                        'frame_number': detection.frame_number,
                        'issue': 'small_bounding_box',
                        'details': f"Area {area:.1f} below threshold {self.thresholds['min_bbox_area']}"
                    })
                
                # Check aspect ratio
                if aspect_ratio > self.thresholds['max_bbox_aspect_ratio']:
                    issues.append({
                        'detection_id': detection.id,
                        'frame_number': detection.frame_number,
                        'issue': 'extreme_aspect_ratio',
                        'details': f"Aspect ratio {aspect_ratio:.2f} above threshold {self.thresholds['max_bbox_aspect_ratio']}"
                    })
                
            except (ValueError, TypeError, KeyError):
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'invalid_bbox_data',
                    'details': "Cannot calculate bbox properties"
                })
        
        metrics = []
        if areas:
            avg_area = np.mean(areas)
            avg_aspect_ratio = np.mean(aspect_ratios)
            
            metrics.extend([
                QualityMetric(
                    name="average_bbox_area",
                    value=avg_area,
                    threshold=self.thresholds['min_bbox_area'],
                    passed=avg_area >= self.thresholds['min_bbox_area'],
                    message=f"Average bbox area: {avg_area:.1f}"
                ),
                QualityMetric(
                    name="average_aspect_ratio",
                    value=avg_aspect_ratio,
                    threshold=self.thresholds['max_bbox_aspect_ratio'],
                    passed=avg_aspect_ratio <= self.thresholds['max_bbox_aspect_ratio'],
                    message=f"Average aspect ratio: {avg_aspect_ratio:.2f}"
                )
            ])
        
        return ValidationResult(
            check_name="bounding_box_validation",
            passed=len(issues) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Found {len(issues)} bounding box issues"
        )
    
    def _validate_frame_distribution(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate distribution of detections across frames."""
        issues = []
        
        # Count detections per frame
        frame_counts = Counter(d.frame_number for d in detections)
        
        # Check for frames with too many or too few detections
        for frame_number, count in frame_counts.items():
            if count < self.thresholds['min_detections_per_frame']:
                issues.append({
                    'frame_number': frame_number,
                    'issue': 'too_few_detections',
                    'details': f"{count} detections (minimum: {self.thresholds['min_detections_per_frame']})"
                })
            
            if count > self.thresholds['max_detections_per_frame']:
                issues.append({
                    'frame_number': frame_number,
                    'issue': 'too_many_detections',
                    'details': f"{count} detections (maximum: {self.thresholds['max_detections_per_frame']})"
                })
        
        # Calculate distribution metrics
        total_frames = len(frame_counts)
        counts = list(frame_counts.values())
        
        metrics = []
        if counts:
            avg_detections_per_frame = np.mean(counts)
            std_detections_per_frame = np.std(counts)
            max_detections = max(counts)
            min_detections = min(counts)
            
            metrics.extend([
                QualityMetric(
                    name="frames_with_detections",
                    value=total_frames,
                    threshold=1,
                    passed=total_frames >= 1,
                    message=f"{total_frames} frames with detections"
                ),
                QualityMetric(
                    name="avg_detections_per_frame",
                    value=avg_detections_per_frame,
                    threshold=1.0,
                    passed=avg_detections_per_frame >= 1.0,
                    message=f"Average: {avg_detections_per_frame:.1f} detections/frame"
                ),
                QualityMetric(
                    name="detection_distribution_std",
                    value=std_detections_per_frame,
                    threshold=10.0,
                    passed=std_detections_per_frame <= 10.0,
                    message=f"Distribution std: {std_detections_per_frame:.1f}"
                )
            ])
        
        return ValidationResult(
            check_name="frame_distribution",
            passed=len(issues) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Analyzed {total_frames} frames with detections"
        )
    
    def _validate_confidence_consistency(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate confidence score consistency across ROI templates."""
        issues = []
        
        # Group by ROI template
        roi_groups = defaultdict(list)
        for detection in detections:
            roi_id = detection.matching_session.roi_template.id
            roi_groups[roi_id].append(detection.confidence_score)
        
        metrics = []
        
        for roi_id, scores in roi_groups.items():
            if len(scores) > 1:
                std_score = np.std(scores)
                avg_score = np.mean(scores)
                
                if std_score > self.thresholds['confidence_std_threshold']:
                    issues.append({
                        'roi_template_id': roi_id,
                        'issue': 'high_confidence_variance',
                        'details': f"Confidence std: {std_score:.3f}, avg: {avg_score:.3f}"
                    })
                
                metrics.append(
                    QualityMetric(
                        name=f"roi_{roi_id}_confidence_consistency",
                        value=std_score,
                        threshold=self.thresholds['confidence_std_threshold'],
                        passed=std_score <= self.thresholds['confidence_std_threshold'],
                        message=f"ROI {roi_id}: std={std_score:.3f}, avg={avg_score:.3f}"
                    )
                )
        
        return ValidationResult(
            check_name="confidence_consistency",
            passed=len(issues) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Analyzed confidence consistency for {len(roi_groups)} ROI templates"
        )
    
    def _validate_temporal_consistency(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate temporal consistency of detections."""
        issues = []
        
        # Sort detections by frame
        sorted_detections = sorted(detections, key=lambda d: d.frame_number)
        
        # Check for large gaps in frame numbers
        frame_numbers = [d.frame_number for d in sorted_detections]
        gaps = []
        
        for i in range(1, len(frame_numbers)):
            gap = frame_numbers[i] - frame_numbers[i-1]
            if gap > 100:  # Arbitrary threshold for large gaps
                gaps.append({
                    'gap_size': gap,
                    'before_frame': frame_numbers[i-1],
                    'after_frame': frame_numbers[i]
                })
        
        if gaps:
            issues.extend([
                {
                    'issue': 'large_temporal_gap',
                    'details': f"Gap of {gap['gap_size']} frames between {gap['before_frame']} and {gap['after_frame']}"
                }
                for gap in gaps
            ])
        
        # Calculate temporal distribution metrics
        if len(frame_numbers) > 1:
            frame_range = max(frame_numbers) - min(frame_numbers)
            frame_density = len(set(frame_numbers)) / (frame_range + 1) if frame_range > 0 else 1.0
            
            metrics = [
                QualityMetric(
                    name="temporal_coverage",
                    value=frame_density,
                    threshold=self.thresholds['frame_coverage_threshold'],
                    passed=frame_density >= self.thresholds['frame_coverage_threshold'],
                    message=f"Frame coverage: {frame_density:.2%}"
                ),
                QualityMetric(
                    name="temporal_gaps",
                    value=len(gaps),
                    threshold=5,
                    passed=len(gaps) <= 5,
                    message=f"{len(gaps)} large temporal gaps found"
                )
            ]
        else:
            metrics = []
        
        return ValidationResult(
            check_name="temporal_consistency",
            passed=len(gaps) <= 5,  # Allow some gaps
            issues=issues,
            metrics=metrics,
            message=f"Found {len(gaps)} temporal inconsistencies"
        )
    
    def _validate_roi_distribution(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate distribution of detections across ROI templates."""
        issues = []
        
        # Count detections per ROI template
        roi_counts = Counter(
            d.matching_session.roi_template.name for d in detections
        )
        
        total_detections = len(detections)
        
        # Check for imbalanced distribution
        for roi_name, count in roi_counts.items():
            percentage = count / total_detections * 100
            
            if percentage < 5:  # Less than 5% of total detections
                issues.append({
                    'roi_template_name': roi_name,
                    'issue': 'low_detection_rate',
                    'details': f"Only {count} detections ({percentage:.1f}% of total)"
                })
            elif percentage > 80:  # More than 80% of total detections
                issues.append({
                    'roi_template_name': roi_name,
                    'issue': 'high_detection_rate',
                    'details': f"{count} detections ({percentage:.1f}% of total)"
                })
        
        # Calculate distribution metrics
        counts = list(roi_counts.values())
        
        metrics = []
        if counts:
            std_counts = np.std(counts)
            avg_counts = np.mean(counts)
            
            metrics.extend([
                QualityMetric(
                    name="roi_template_count",
                    value=len(roi_counts),
                    threshold=1,
                    passed=len(roi_counts) >= 1,
                    message=f"{len(roi_counts)} ROI templates have detections"
                ),
                QualityMetric(
                    name="roi_distribution_balance",
                    value=std_counts / avg_counts if avg_counts > 0 else 0,
                    threshold=2.0,
                    passed=(std_counts / avg_counts if avg_counts > 0 else 0) <= 2.0,
                    message=f"Distribution coefficient of variation: {std_counts / avg_counts:.2f}" if avg_counts > 0 else "No variation"
                )
            ])
        
        return ValidationResult(
            check_name="roi_distribution",
            passed=len(issues) == 0,
            issues=issues,
            metrics=metrics,
            message=f"Analyzed distribution across {len(roi_counts)} ROI templates"
        )
    
    def _validate_data_completeness(self, detections: List[DetectionResult]) -> ValidationResult:
        """Validate completeness of detection data."""
        issues = []
        
        total_detections = len(detections)
        complete_detections = 0
        
        for detection in detections:
            missing_fields = []
            
            # Check required fields
            if not hasattr(detection, 'confidence_score') or detection.confidence_score is None:
                missing_fields.append('confidence_score')
            
            if not detection.coordinates:
                missing_fields.append('coordinates')
            
            if not hasattr(detection, 'matching_session') or not detection.matching_session:
                missing_fields.append('matching_session')
            
            if missing_fields:
                issues.append({
                    'detection_id': detection.id,
                    'frame_number': detection.frame_number,
                    'issue': 'incomplete_data',
                    'details': f"Missing fields: {missing_fields}"
                })
            else:
                complete_detections += 1
        
        completeness_rate = complete_detections / total_detections if total_detections > 0 else 0
        
        metrics = [
            QualityMetric(
                name="data_completeness_rate",
                value=completeness_rate,
                threshold=0.95,
                passed=completeness_rate >= 0.95,
                message=f"{complete_detections}/{total_detections} detections are complete"
            )
        ]
        
        return ValidationResult(
            check_name="data_completeness",
            passed=completeness_rate >= 0.95,
            issues=issues,
            metrics=metrics,
            message=f"Data completeness: {completeness_rate:.1%}"
        )
    
    def _detect_statistical_anomalies(self, detections: List[DetectionResult]) -> ValidationResult:
        """Detect statistical anomalies in the detection data."""
        issues = []
        
        # Collect numerical features
        confidence_scores = [d.confidence_score for d in detections if d.confidence_score is not None]
        bbox_areas = []
        aspect_ratios = []
        
        for detection in detections:
            coords = detection.coordinates
            try:
                w, h = float(coords['width']), float(coords['height'])
                bbox_areas.append(w * h)
                aspect_ratios.append(max(w, h) / min(w, h))
            except (KeyError, ValueError, ZeroDivisionError):
                continue
        
        # Detect outliers using IQR method
        anomaly_detections = []
        
        for feature_name, values in [
            ('confidence_score', confidence_scores),
            ('bbox_area', bbox_areas),
            ('aspect_ratio', aspect_ratios)
        ]:
            if len(values) > 10:  # Need sufficient data
                outliers = self._detect_outliers_iqr(values)
                if outliers:
                    anomaly_detections.extend(outliers)
                    issues.append({
                        'feature': feature_name,
                        'issue': 'statistical_anomaly',
                        'details': f"{len(outliers)} outliers detected"
                    })
        
        metrics = [
            QualityMetric(
                name="statistical_anomalies",
                value=len(anomaly_detections),
                threshold=len(detections) * 0.05,  # 5% threshold
                passed=len(anomaly_detections) <= len(detections) * 0.05,
                message=f"{len(anomaly_detections)} statistical anomalies detected"
            )
        ]
        
        return ValidationResult(
            check_name="statistical_anomalies",
            passed=len(anomaly_detections) <= len(detections) * 0.05,
            issues=issues,
            metrics=metrics,
            message=f"Statistical analysis completed, {len(anomaly_detections)} anomalies found"
        )
    
    def _calculate_iou(self, coords1: Dict[str, Any], coords2: Dict[str, Any]) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
        try:
            x1_min, y1_min = coords1['x'], coords1['y']
            x1_max = x1_min + coords1['width']
            y1_max = y1_min + coords1['height']
            
            x2_min, y2_min = coords2['x'], coords2['y']
            x2_max = x2_min + coords2['width']
            y2_max = y2_min + coords2['height']
            
            # Calculate intersection
            inter_x_min = max(x1_min, x2_min)
            inter_y_min = max(y1_min, y2_min)
            inter_x_max = min(x1_max, x2_max)
            inter_y_max = min(y1_max, y2_max)
            
            if inter_x_max <= inter_x_min or inter_y_max <= inter_y_min:
                return 0.0
            
            inter_area = (inter_x_max - inter_x_min) * (inter_y_max - inter_y_min)
            
            # Calculate union
            area1 = coords1['width'] * coords1['height']
            area2 = coords2['width'] * coords2['height']
            union_area = area1 + area2 - inter_area
            
            return inter_area / union_area if union_area > 0 else 0.0
            
        except (KeyError, ValueError, TypeError):
            return 0.0
    
    def _detect_outliers_iqr(self, values: List[float], k: float = 1.5) -> List[int]:
        """Detect outliers using the IQR method."""
        if len(values) < 4:
            return []
        
        np_values = np.array(values)
        q1 = np.percentile(np_values, 25)
        q3 = np.percentile(np_values, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - k * iqr
        upper_bound = q3 + k * iqr
        
        outlier_indices = []
        for i, value in enumerate(values):
            if value < lower_bound or value > upper_bound:
                outlier_indices.append(i)
        
        return outlier_indices
    
    def generate_quality_report(self, detections: List[DetectionResult]) -> Dict[str, Any]:
        """Generate comprehensive quality report."""
        validation_results = self.run_comprehensive_validation(detections)
        
        # Aggregate results
        total_checks = len(validation_results)
        passed_checks = sum(1 for result in validation_results.values() if result.passed)
        total_issues = sum(len(result.issues) for result in validation_results.values())
        
        # Categorize issues by severity
        critical_issues = []
        warnings = []
        info_items = []
        
        for check_name, result in validation_results.items():
            for issue in result.issues:
                issue_copy = issue.copy()
                issue_copy['check'] = check_name
                
                if check_name in ['coordinates', 'confidence', 'completeness']:
                    critical_issues.append(issue_copy)
                elif check_name in ['duplicates', 'bounding_boxes']:
                    warnings.append(issue_copy)
                else:
                    info_items.append(issue_copy)
        
        # Calculate overall quality score
        quality_score = self._calculate_quality_score(validation_results)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(validation_results)
        
        report = {
            'task_id': self.task_id,
            'timestamp': timezone.now().isoformat(),
            'summary': {
                'total_detections': len(detections),
                'total_checks': total_checks,
                'passed_checks': passed_checks,
                'total_issues': total_issues,
                'quality_score': quality_score,
                'grade': self._get_quality_grade(quality_score)
            },
            'issues': {
                'critical': critical_issues,
                'warnings': warnings,
                'info': info_items
            },
            'validation_results': {
                check_name: {
                    'passed': result.passed,
                    'issue_count': len(result.issues),
                    'metrics': [
                        {
                            'name': metric.name,
                            'value': metric.value,
                            'threshold': metric.threshold,
                            'passed': metric.passed,
                            'message': metric.message
                        }
                        for metric in result.metrics
                    ],
                    'message': result.message
                }
                for check_name, result in validation_results.items()
            },
            'recommendations': recommendations,
            'thresholds_used': self.thresholds
        }
        
        return report
    
    def _calculate_quality_score(self, validation_results: Dict[str, ValidationResult]) -> float:
        """Calculate overall quality score (0-100)."""
        if not validation_results:
            return 0.0
        
        # Weight different validation checks
        weights = {
            'coordinates': 0.2,
            'confidence': 0.15,
            'completeness': 0.15,
            'duplicates': 0.1,
            'bounding_boxes': 0.1,
            'frame_distribution': 0.1,
            'confidence_consistency': 0.08,
            'temporal_consistency': 0.07,
            'roi_distribution': 0.05
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for check_name, result in validation_results.items():
            weight = weights.get(check_name, 0.05)
            
            # Calculate check score based on passed status and metrics
            if result.passed:
                check_score = 100.0
            else:
                # Penalize based on number of issues
                total_detections = sum(
                    1 for metric in result.metrics 
                    if metric.name.endswith('_rate') or metric.name.endswith('_count')
                )
                if total_detections == 0:
                    total_detections = 1
                
                issue_penalty = min(len(result.issues) / total_detections * 50, 80)
                check_score = max(100.0 - issue_penalty, 20.0)
            
            total_score += check_score * weight
            total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _get_quality_grade(self, score: float) -> str:
        """Convert quality score to letter grade."""
        if score >= 95:
            return 'A+'
        elif score >= 90:
            return 'A'
        elif score >= 85:
            return 'B+'
        elif score >= 80:
            return 'B'
        elif score >= 75:
            return 'C+'
        elif score >= 70:
            return 'C'
        elif score >= 60:
            return 'D'
        else:
            return 'F'
    
    def _generate_recommendations(self, validation_results: Dict[str, ValidationResult]) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []
        
        for check_name, result in validation_results.items():
            if not result.passed:
                if check_name == 'coordinates':
                    recommendations.append(
                        "Review and fix invalid bounding box coordinates. "
                        "Ensure all coordinates are non-negative and dimensions are positive."
                    )
                elif check_name == 'confidence':
                    recommendations.append(
                        "Review confidence score calculation. Consider adjusting matching thresholds "
                        "or algorithm parameters to improve confidence consistency."
                    )
                elif check_name == 'duplicates':
                    recommendations.append(
                        "Remove or merge duplicate detections. Consider implementing "
                        "Non-Maximum Suppression (NMS) to reduce overlapping detections."
                    )
                elif check_name == 'bounding_boxes':
                    recommendations.append(
                        "Review bounding box dimensions. Very small or elongated boxes "
                        "may indicate detection errors or inappropriate ROI templates."
                    )
                elif check_name == 'frame_distribution':
                    recommendations.append(
                        "Review frame coverage and detection density. Consider adjusting "
                        "matching parameters or adding more ROI templates for better coverage."
                    )
                elif check_name == 'temporal_consistency':
                    recommendations.append(
                        "Large gaps in frame coverage detected. Consider running matching "
                        "on more frames or investigating why certain frames lack detections."
                    )
        
        # Add general recommendations
        if len([r for r in validation_results.values() if not r.passed]) > 3:
            recommendations.append(
                "Multiple validation issues detected. Consider reviewing the entire "
                "matching pipeline configuration and ROI template quality."
            )
        
        return recommendations


class ExportQualityController:
    """Quality control specifically for export operations."""
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.logger = logging.getLogger(f"{__name__}.ExportQualityController")
    
    def validate_for_export(
        self,
        detections: List[DetectionResult],
        export_format: str
    ) -> ValidationResult:
        """Validate detections specifically for export format requirements."""
        issues = []
        
        # Format-specific validations
        if export_format == 'coco':
            issues.extend(self._validate_for_coco(detections))
        elif export_format == 'yolo':
            issues.extend(self._validate_for_yolo(detections))
        elif export_format == 'pascal_voc':
            issues.extend(self._validate_for_pascal_voc(detections))
        
        return ValidationResult(
            check_name=f"export_validation_{export_format}",
            passed=len(issues) == 0,
            issues=issues,
            metrics=[],
            message=f"Format-specific validation for {export_format}: {len(issues)} issues"
        )
    
    def _validate_for_coco(self, detections: List[DetectionResult]) -> List[Dict[str, Any]]:
        """Validate for COCO format requirements."""
        issues = []
        
        # Check for required fields
        for detection in detections:
            if not detection.matching_session.roi_template.name:
                issues.append({
                    'detection_id': detection.id,
                    'issue': 'missing_category_name',
                    'details': 'ROI template name required for COCO categories'
                })
        
        return issues
    
    def _validate_for_yolo(self, detections: List[DetectionResult]) -> List[Dict[str, Any]]:
        """Validate for YOLO format requirements."""
        issues = []
        
        # YOLO requires positive coordinates and dimensions
        for detection in detections:
            coords = detection.coordinates
            try:
                if any(float(coords[k]) < 0 for k in ['x', 'y', 'width', 'height']):
                    issues.append({
                        'detection_id': detection.id,
                        'issue': 'negative_coordinates_for_yolo',
                        'details': 'YOLO format requires non-negative coordinates'
                    })
            except (KeyError, ValueError):
                issues.append({
                    'detection_id': detection.id,
                    'issue': 'invalid_coordinates_for_yolo',
                    'details': 'YOLO format requires valid numeric coordinates'
                })
        
        return issues
    
    def _validate_for_pascal_voc(self, detections: List[DetectionResult]) -> List[Dict[str, Any]]:
        """Validate for Pascal VOC format requirements."""
        issues = []
        
        # Pascal VOC requires integer coordinates
        for detection in detections:
            coords = detection.coordinates
            try:
                for key in ['x', 'y', 'width', 'height']:
                    val = float(coords[key])
                    if val != int(val):
                        issues.append({
                            'detection_id': detection.id,
                            'issue': 'non_integer_coordinates',
                            'details': f'Pascal VOC prefers integer coordinates, got {key}={val}'
                        })
                        break
            except (KeyError, ValueError):
                issues.append({
                    'detection_id': detection.id,
                    'issue': 'invalid_coordinates_for_pascal_voc',
                    'details': 'Pascal VOC requires valid numeric coordinates'
                })
        
        return issues