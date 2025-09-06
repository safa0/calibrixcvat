# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from cvat.apps.engine.models import Task
import uuid


class ExportHistory(models.Model):
    """
    Model to track export history and metadata for ground truth exports.
    """
    
    class ExportStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    class ExportFormat(models.TextChoices):
        COCO = 'coco', 'COCO JSON'
        YOLO = 'yolo', 'YOLO'
        PASCAL_VOC = 'pascal_voc', 'Pascal VOC XML'
        CVAT_XML = 'cvat_xml', 'CVAT XML'
        CSV = 'csv', 'CSV'
    
    # Primary identifiers
    export_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for this export"
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='export_history',
        help_text="Task this export was generated from"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='export_history',
        help_text="User who initiated the export"
    )
    
    # Export configuration
    export_format = models.CharField(
        max_length=20,
        choices=ExportFormat.choices,
        help_text="Format used for export"
    )
    export_config = models.JSONField(
        help_text="Complete export configuration used",
        default=dict
    )
    
    # Export metadata
    total_detections = models.PositiveIntegerField(
        help_text="Total number of detections exported"
    )
    confirmed_detections_only = models.BooleanField(
        default=True,
        help_text="Whether export included only confirmed detections"
    )
    min_confidence_threshold = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Minimum confidence threshold applied"
    )
    roi_template_filter = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ROI template filter applied (if any)"
    )
    
    # Dataset splitting information
    dataset_split_used = models.BooleanField(
        default=False,
        help_text="Whether dataset splitting was applied"
    )
    dataset_splits = models.JSONField(
        null=True,
        blank=True,
        help_text="Dataset split configuration (train/val/test ratios)"
    )
    
    # Export results
    status = models.CharField(
        max_length=20,
        choices=ExportStatus.choices,
        default=ExportStatus.PENDING,
        help_text="Current status of the export"
    )
    export_path = models.CharField(
        max_length=1000,
        null=True,
        blank=True,
        help_text="Path to the exported file(s)"
    )
    file_size_bytes = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Size of exported file(s) in bytes"
    )
    compression_format = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Compression format used (if any)"
    )
    
    # Quality control results
    quality_report = models.JSONField(
        null=True,
        blank=True,
        help_text="Quality control report generated during export"
    )
    validation_errors = models.JSONField(
        null=True,
        blank=True,
        help_text="Any validation errors encountered"
    )
    
    # Timing and performance
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the export was initiated"
    )
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When export processing actually started"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When export processing completed"
    )
    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Total duration of export in seconds"
    )
    processing_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="Processing rate in detections per second"
    )
    
    # Error information
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error message if export failed"
    )
    error_details = models.JSONField(
        null=True,
        blank=True,
        help_text="Detailed error information"
    )
    
    # Export versioning
    export_version = models.CharField(
        max_length=50,
        default='1.0',
        help_text="Version of the export format/schema used"
    )
    parent_export = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incremental_exports',
        help_text="Parent export for incremental exports"
    )
    is_incremental = models.BooleanField(
        default=False,
        help_text="Whether this is an incremental export"
    )
    
    # Archival and cleanup
    auto_delete_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this export should be automatically deleted"
    )
    is_archived = models.BooleanField(
        default=False,
        help_text="Whether this export has been archived"
    )
    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this export was archived"
    )

    class Meta:
        db_table = 'calibrix_matching_exporthistory'
        verbose_name = 'Export History'
        verbose_name_plural = 'Export Histories'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task', '-created_at']),
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['export_format', '-created_at']),
            models.Index(fields=['created_by', '-created_at']),
            models.Index(fields=['auto_delete_at']),
        ]

    def __str__(self):
        return f"Export {self.export_id} - {self.export_format} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Override save to update timing fields automatically."""
        # Set started_at when status changes to IN_PROGRESS
        if self.status == self.ExportStatus.IN_PROGRESS and not self.started_at:
            self.started_at = timezone.now()
        
        # Set completed_at and calculate duration when status changes to COMPLETED or FAILED
        if self.status in [self.ExportStatus.COMPLETED, self.ExportStatus.FAILED]:
            if not self.completed_at:
                self.completed_at = timezone.now()
            
            # Calculate duration if we have both start and completion times
            if self.started_at and self.completed_at:
                duration = (self.completed_at - self.started_at).total_seconds()
                self.duration_seconds = duration
                
                # Calculate processing rate
                if duration > 0 and self.total_detections:
                    self.processing_rate = self.total_detections / duration
        
        super().save(*args, **kwargs)
    
    @property
    def is_successful(self):
        """Check if the export completed successfully."""
        return self.status == self.ExportStatus.COMPLETED
    
    @property
    def is_in_progress(self):
        """Check if the export is currently in progress."""
        return self.status == self.ExportStatus.IN_PROGRESS
    
    @property
    def has_failed(self):
        """Check if the export has failed."""
        return self.status == self.ExportStatus.FAILED
    
    @property
    def file_size_mb(self):
        """Get file size in megabytes."""
        if self.file_size_bytes:
            return self.file_size_bytes / (1024 * 1024)
        return None
    
    @property
    def export_age_days(self):
        """Get the age of the export in days."""
        if self.completed_at:
            age = timezone.now() - self.completed_at
            return age.days
        return None
    
    def mark_as_started(self):
        """Mark export as started."""
        self.status = self.ExportStatus.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_as_completed(self, export_path: str, file_size: int = None):
        """Mark export as completed."""
        self.status = self.ExportStatus.COMPLETED
        self.export_path = export_path
        if file_size is not None:
            self.file_size_bytes = file_size
        self.save()
    
    def mark_as_failed(self, error_message: str, error_details: dict = None):
        """Mark export as failed."""
        self.status = self.ExportStatus.FAILED
        self.error_message = error_message
        if error_details:
            self.error_details = error_details
        self.save()
    
    def get_export_summary(self):
        """Get a summary of the export for display purposes."""
        return {
            'export_id': str(self.export_id),
            'format': self.export_format,
            'status': self.status,
            'total_detections': self.total_detections,
            'file_size_mb': self.file_size_mb,
            'duration_seconds': self.duration_seconds,
            'processing_rate': self.processing_rate,
            'created_at': self.created_at,
            'completed_at': self.completed_at,
            'is_incremental': self.is_incremental,
            'has_quality_report': bool(self.quality_report),
        }


class ExportDownload(models.Model):
    """
    Model to track download history for exported files.
    """
    
    export_history = models.ForeignKey(
        ExportHistory,
        on_delete=models.CASCADE,
        related_name='download_history',
        help_text="The export that was downloaded"
    )
    downloaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='export_downloads',
        help_text="User who downloaded the export"
    )
    download_timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When the download occurred"
    )
    download_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the downloader"
    )
    user_agent = models.CharField(
        max_length=500,
        null=True,
        blank=True,
        help_text="User agent string of the downloader"
    )
    bytes_served = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Number of bytes served in this download"
    )
    download_completed = models.BooleanField(
        default=True,
        help_text="Whether the download completed successfully"
    )

    class Meta:
        db_table = 'calibrix_matching_exportdownload'
        verbose_name = 'Export Download'
        verbose_name_plural = 'Export Downloads'
        ordering = ['-download_timestamp']
        indexes = [
            models.Index(fields=['export_history', '-download_timestamp']),
            models.Index(fields=['downloaded_by', '-download_timestamp']),
        ]

    def __str__(self):
        return f"Download of {self.export_history.export_id} by {self.downloaded_by}"