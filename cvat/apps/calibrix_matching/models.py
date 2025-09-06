# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from cvat.apps.engine.models import Task

# Import additional models
from .models.export_history import ExportHistory, ExportDownload


class ROITemplate(models.Model):
    """
    Model to store Region of Interest (ROI) templates with their feature descriptors
    for matching against video frames.
    """
    name = models.CharField(max_length=255, null=False, blank=False)
    task = models.ForeignKey(
        Task, 
        on_delete=models.CASCADE, 
        related_name='roi_templates',
        null=False,
        blank=False
    )
    coordinates = models.JSONField(
        help_text="Bounding box coordinates: {x, y, width, height}",
        null=False,
        blank=False
    )
    feature_descriptor = models.JSONField(
        help_text="Feature descriptor data including keypoints and descriptors",
        null=False,
        blank=False
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roi_templates'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'calibrix_matching_roitemplate'
        verbose_name = 'ROI Template'
        verbose_name_plural = 'ROI Templates'
        ordering = ['-created_at']

    def __str__(self):
        return f"ROI Template: {self.name} (Task: {self.task.name})"

    def clean(self):
        """Validate the model fields."""
        super().clean()
        
        # Validate coordinates structure
        if self.coordinates:
            required_coord_fields = {'x', 'y', 'width', 'height'}
            if not all(field in self.coordinates for field in required_coord_fields):
                raise ValidationError(
                    "Coordinates must contain x, y, width, and height fields"
                )
            
            # Validate coordinate values are numeric
            for field in required_coord_fields:
                value = self.coordinates.get(field)
                if not isinstance(value, (int, float)):
                    raise ValidationError(f"Coordinate field '{field}' must be numeric")
        
        # Validate feature descriptor structure
        if self.feature_descriptor:
            required_descriptor_fields = {'algorithm', 'keypoints', 'descriptors'}
            if not all(field in self.feature_descriptor for field in required_descriptor_fields):
                raise ValidationError(
                    "Feature descriptor must contain algorithm, keypoints, and descriptors fields"
                )


class MatchingSession(models.Model):
    """
    Model to store matching sessions that use ROI templates to find matches in video frames.
    """
    
    class AlgorithmType(models.TextChoices):
        SIFT = 'SIFT', 'Scale-Invariant Feature Transform'
        SURF = 'SURF', 'Speeded-Up Robust Features'
        ORB = 'ORB', 'Oriented FAST and Rotated BRIEF'
        AKAZE = 'AKAZE', 'Accelerated-KAZE'
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
    
    roi_template = models.ForeignKey(
        ROITemplate,
        on_delete=models.CASCADE,
        related_name='matching_sessions',
        null=False,
        blank=False
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='matching_sessions',
        null=False,
        blank=False
    )
    algorithm_type = models.CharField(
        max_length=20,
        choices=AlgorithmType.choices,
        default=AlgorithmType.SIFT
    )
    threshold = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Matching threshold between 0.0 and 1.0"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'calibrix_matching_matchingsession'
        verbose_name = 'Matching Session'
        verbose_name_plural = 'Matching Sessions'
        ordering = ['-created_at']

    def __str__(self):
        return f"Matching Session: {self.id} (ROI: {self.roi_template.name}, Status: {self.status})"


class DetectionResult(models.Model):
    """
    Model to store detection results from matching sessions.
    """
    matching_session = models.ForeignKey(
        MatchingSession,
        on_delete=models.CASCADE,
        related_name='detection_results',
        null=False,
        blank=False
    )
    frame_number = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text="Frame number in the video sequence"
    )
    coordinates = models.JSONField(
        help_text="Detected bounding box coordinates: {x, y, width, height}",
        null=False,
        blank=False
    )
    confidence_score = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence score between 0.0 and 1.0"
    )
    is_confirmed = models.BooleanField(
        default=False,
        help_text="Whether this detection has been confirmed by a user"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'calibrix_matching_detectionresult'
        verbose_name = 'Detection Result'
        verbose_name_plural = 'Detection Results'
        ordering = ['frame_number']
        unique_together = ['matching_session', 'frame_number']

    def __str__(self):
        return f"Detection Result: Frame {self.frame_number}, Score: {self.confidence_score:.2f}"

    def clean(self):
        """Validate the model fields."""
        super().clean()
        
        # Validate coordinates structure
        if self.coordinates:
            required_coord_fields = {'x', 'y', 'width', 'height'}
            if not all(field in self.coordinates for field in required_coord_fields):
                raise ValidationError(
                    "Coordinates must contain x, y, width, and height fields"
                )
            
            # Validate coordinate values are numeric
            for field in required_coord_fields:
                value = self.coordinates.get(field)
                if not isinstance(value, (int, float)):
                    raise ValidationError(f"Coordinate field '{field}' must be numeric")