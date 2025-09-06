# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Q, Count, Sum, Avg, Min, Max
from django.utils import timezone
from pathlib import Path

from ..models import ExportHistory, ExportDownload, DetectionResult, MatchingSession
from .ground_truth_export import ExportConfig, GroundTruthExportService
from cvat.apps.engine.models import Task

logger = logging.getLogger(__name__)


class ExportHistoryService:
    """
    Service class for managing export history, versioning, and incremental exports.
    """
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task = Task.objects.get(id=task_id)
        self.logger = logging.getLogger(f"{__name__}.ExportHistoryService")
    
    def create_export_record(
        self,
        export_format: str,
        config: ExportConfig,
        user: Optional[User] = None,
        parent_export_id: Optional[UUID] = None
    ) -> ExportHistory:
        """
        Create a new export history record.
        
        Args:
            export_format: The export format being used
            config: Export configuration
            user: User initiating the export
            parent_export_id: Parent export ID for incremental exports
            
        Returns:
            Created ExportHistory instance
        """
        # Determine if this is an incremental export
        parent_export = None
        is_incremental = False
        if parent_export_id:
            try:
                parent_export = ExportHistory.objects.get(
                    export_id=parent_export_id,
                    task=self.task
                )
                is_incremental = True
            except ExportHistory.DoesNotExist:
                self.logger.warning(f"Parent export {parent_export_id} not found")
        
        # Count total detections that will be exported
        service = GroundTruthExportService(self.task_id)
        detection_count = len(service.get_detection_queryset(
            confirmed_only=config.confirmed_only,
            min_confidence=config.min_confidence,
            roi_template_id=config.roi_template_id
        ))
        
        # Set auto-delete date (default 30 days from now)
        auto_delete_at = timezone.now() + timedelta(days=30)
        
        export_record = ExportHistory.objects.create(
            task=self.task,
            created_by=user,
            export_format=export_format,
            export_config=config.to_dict(),
            total_detections=detection_count,
            confirmed_detections_only=config.confirmed_only,
            min_confidence_threshold=config.min_confidence,
            roi_template_filter=str(config.roi_template_id) if config.roi_template_id else None,
            dataset_split_used=bool(config.dataset_split),
            dataset_splits=config.dataset_split,
            compression_format=config.compression_format,
            parent_export=parent_export,
            is_incremental=is_incremental,
            auto_delete_at=auto_delete_at,
        )
        
        self.logger.info(f"Created export record {export_record.export_id} for task {self.task_id}")
        return export_record
    
    def update_export_progress(
        self,
        export_id: UUID,
        status: str,
        export_path: Optional[str] = None,
        file_size: Optional[int] = None,
        quality_report: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ):
        """
        Update export progress and results.
        
        Args:
            export_id: Export ID to update
            status: New status
            export_path: Path to exported file(s)
            file_size: Size of exported file(s) in bytes
            quality_report: Quality control report
            error_message: Error message if failed
            error_details: Detailed error information
        """
        try:
            with transaction.atomic():
                export_record = ExportHistory.objects.select_for_update().get(
                    export_id=export_id,
                    task=self.task
                )
                
                export_record.status = status
                
                if export_path:
                    export_record.export_path = export_path
                
                if file_size is not None:
                    export_record.file_size_bytes = file_size
                
                if quality_report:
                    export_record.quality_report = quality_report
                
                if error_message:
                    export_record.error_message = error_message
                
                if error_details:
                    export_record.error_details = error_details
                
                export_record.save()
                
        except ExportHistory.DoesNotExist:
            self.logger.error(f"Export record {export_id} not found for task {self.task_id}")
            raise
    
    def get_export_history(
        self,
        limit: int = 50,
        format_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        user_filter: Optional[User] = None,
        include_archived: bool = False
    ) -> List[ExportHistory]:
        """
        Get export history for the task.
        
        Args:
            limit: Maximum number of records to return
            format_filter: Filter by export format
            status_filter: Filter by status
            user_filter: Filter by user
            include_archived: Whether to include archived exports
            
        Returns:
            List of ExportHistory records
        """
        queryset = ExportHistory.objects.filter(task=self.task)
        
        if not include_archived:
            queryset = queryset.filter(is_archived=False)
        
        if format_filter:
            queryset = queryset.filter(export_format=format_filter)
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if user_filter:
            queryset = queryset.filter(created_by=user_filter)
        
        return list(queryset.order_by('-created_at')[:limit])
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about export history.
        
        Returns:
            Dictionary with export statistics
        """
        exports = ExportHistory.objects.filter(task=self.task)
        
        # Basic counts
        total_exports = exports.count()
        successful_exports = exports.filter(status=ExportHistory.ExportStatus.COMPLETED).count()
        failed_exports = exports.filter(status=ExportHistory.ExportStatus.FAILED).count()
        in_progress_exports = exports.filter(status=ExportHistory.ExportStatus.IN_PROGRESS).count()
        
        # Format distribution
        format_stats = dict(exports.values_list('export_format').annotate(Count('id')))
        
        # User activity
        user_stats = dict(
            exports.filter(created_by__isnull=False)
            .values_list('created_by__username')
            .annotate(Count('id'))
        )
        
        # Performance statistics
        completed_exports = exports.filter(
            status=ExportHistory.ExportStatus.COMPLETED,
            duration_seconds__isnull=False
        )
        
        perf_stats = completed_exports.aggregate(
            avg_duration=Avg('duration_seconds'),
            min_duration=Min('duration_seconds'),
            max_duration=Max('duration_seconds'),
            avg_processing_rate=Avg('processing_rate'),
            total_detections_exported=Sum('total_detections'),
            total_files_size=Sum('file_size_bytes')
        )
        
        # Recent activity
        last_24h = timezone.now() - timedelta(hours=24)
        last_week = timezone.now() - timedelta(days=7)
        
        recent_stats = {
            'exports_last_24h': exports.filter(created_at__gte=last_24h).count(),
            'exports_last_week': exports.filter(created_at__gte=last_week).count(),
            'successful_last_week': exports.filter(
                created_at__gte=last_week,
                status=ExportHistory.ExportStatus.COMPLETED
            ).count(),
        }
        
        return {
            'task_id': self.task_id,
            'task_name': self.task.name,
            'total_exports': total_exports,
            'successful_exports': successful_exports,
            'failed_exports': failed_exports,
            'in_progress_exports': in_progress_exports,
            'success_rate': (successful_exports / total_exports * 100) if total_exports > 0 else 0,
            'format_distribution': format_stats,
            'user_activity': user_stats,
            'performance_statistics': perf_stats,
            'recent_activity': recent_stats,
            'last_updated': timezone.now().isoformat()
        }
    
    def find_similar_exports(
        self,
        config: ExportConfig,
        time_window_hours: int = 24
    ) -> List[ExportHistory]:
        """
        Find similar recent exports to avoid duplicates.
        
        Args:
            config: Export configuration to match
            time_window_hours: Time window to search in hours
            
        Returns:
            List of similar export records
        """
        cutoff_time = timezone.now() - timedelta(hours=time_window_hours)
        
        similar_exports = ExportHistory.objects.filter(
            task=self.task,
            created_at__gte=cutoff_time,
            export_format=config.export_format,
            confirmed_detections_only=config.confirmed_only,
            status=ExportHistory.ExportStatus.COMPLETED
        )
        
        # Filter by confidence threshold if specified
        if config.min_confidence is not None:
            similar_exports = similar_exports.filter(
                min_confidence_threshold=config.min_confidence
            )
        
        # Filter by ROI template if specified
        if config.roi_template_id:
            similar_exports = similar_exports.filter(
                roi_template_filter=str(config.roi_template_id)
            )
        
        return list(similar_exports.order_by('-created_at'))
    
    def get_incremental_export_candidates(self) -> List[ExportHistory]:
        """
        Get exports that can be used as base for incremental exports.
        
        Returns:
            List of suitable base export records
        """
        base_exports = ExportHistory.objects.filter(
            task=self.task,
            status=ExportHistory.ExportStatus.COMPLETED,
            is_incremental=False,
            export_path__isnull=False
        ).order_by('-created_at')[:10]
        
        return list(base_exports)
    
    def calculate_export_diff(
        self,
        base_export_id: UUID,
        current_config: ExportConfig
    ) -> Dict[str, Any]:
        """
        Calculate what would be different in a new export compared to a base export.
        
        Args:
            base_export_id: Base export to compare against
            current_config: Current export configuration
            
        Returns:
            Dictionary with diff information
        """
        try:
            base_export = ExportHistory.objects.get(
                export_id=base_export_id,
                task=self.task
            )
        except ExportHistory.DoesNotExist:
            raise ValueError(f"Base export {base_export_id} not found")
        
        # Get current detection count
        service = GroundTruthExportService(self.task_id)
        current_detections = service.get_detection_queryset(
            confirmed_only=current_config.confirmed_only,
            min_confidence=current_config.min_confidence,
            roi_template_id=current_config.roi_template_id
        )
        current_count = len(current_detections)
        
        # Calculate changes since base export
        new_detections = DetectionResult.objects.filter(
            matching_session__task=self.task,
            created_at__gt=base_export.created_at
        )
        
        if current_config.confirmed_only:
            new_detections = new_detections.filter(is_confirmed=True)
        
        if current_config.min_confidence:
            new_detections = new_detections.filter(
                confidence_score__gte=current_config.min_confidence
            )
        
        if current_config.roi_template_id:
            new_detections = new_detections.filter(
                matching_session__roi_template_id=current_config.roi_template_id
            )
        
        new_count = new_detections.count()
        
        return {
            'base_export_id': str(base_export_id),
            'base_export_date': base_export.created_at,
            'base_detection_count': base_export.total_detections,
            'current_detection_count': current_count,
            'new_detections_since_base': new_count,
            'change_percentage': ((current_count - base_export.total_detections) / 
                                base_export.total_detections * 100) if base_export.total_detections > 0 else 0,
            'is_incremental_worthwhile': new_count > 0 and new_count < (current_count * 0.5),
            'config_changes': self._compare_configs(base_export.export_config, current_config.to_dict())
        }
    
    def _compare_configs(self, base_config: Dict[str, Any], current_config: Dict[str, Any]) -> Dict[str, Any]:
        """Compare two export configurations."""
        changes = {}
        
        for key in set(base_config.keys()) | set(current_config.keys()):
            base_value = base_config.get(key)
            current_value = current_config.get(key)
            
            if base_value != current_value:
                changes[key] = {
                    'old': base_value,
                    'new': current_value
                }
        
        return changes
    
    def archive_old_exports(self, days_old: int = 30) -> int:
        """
        Archive old export records.
        
        Args:
            days_old: Archive exports older than this many days
            
        Returns:
            Number of exports archived
        """
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        old_exports = ExportHistory.objects.filter(
            task=self.task,
            created_at__lt=cutoff_date,
            is_archived=False,
            status__in=[ExportHistory.ExportStatus.COMPLETED, ExportHistory.ExportStatus.FAILED]
        )
        
        archived_count = old_exports.update(
            is_archived=True,
            archived_at=timezone.now()
        )
        
        self.logger.info(f"Archived {archived_count} old exports for task {self.task_id}")
        return archived_count
    
    def cleanup_expired_exports(self) -> Tuple[int, int]:
        """
        Clean up exports that have passed their auto-delete date.
        
        Returns:
            Tuple of (records_deleted, files_deleted)
        """
        expired_exports = ExportHistory.objects.filter(
            task=self.task,
            auto_delete_at__lt=timezone.now(),
            status__in=[ExportHistory.ExportStatus.COMPLETED, ExportHistory.ExportStatus.FAILED]
        )
        
        records_deleted = 0
        files_deleted = 0
        
        for export in expired_exports:
            # Delete associated files
            if export.export_path and os.path.exists(export.export_path):
                try:
                    if os.path.isfile(export.export_path):
                        os.unlink(export.export_path)
                        files_deleted += 1
                    elif os.path.isdir(export.export_path):
                        import shutil
                        shutil.rmtree(export.export_path)
                        files_deleted += 1
                except Exception as e:
                    self.logger.error(f"Failed to delete export file {export.export_path}: {e}")
            
            # Delete the record
            export.delete()
            records_deleted += 1
        
        self.logger.info(f"Cleaned up {records_deleted} expired exports and {files_deleted} files")
        return records_deleted, files_deleted
    
    def record_download(
        self,
        export_id: UUID,
        user: Optional[User] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        bytes_served: Optional[int] = None,
        completed: bool = True
    ) -> ExportDownload:
        """
        Record a download of an exported file.
        
        Args:
            export_id: Export ID that was downloaded
            user: User who downloaded (if authenticated)
            ip_address: IP address of downloader
            user_agent: User agent string
            bytes_served: Number of bytes served
            completed: Whether download completed successfully
            
        Returns:
            Created ExportDownload record
        """
        try:
            export_record = ExportHistory.objects.get(
                export_id=export_id,
                task=self.task
            )
        except ExportHistory.DoesNotExist:
            raise ValueError(f"Export {export_id} not found for task {self.task_id}")
        
        download_record = ExportDownload.objects.create(
            export_history=export_record,
            downloaded_by=user,
            download_ip=ip_address,
            user_agent=user_agent,
            bytes_served=bytes_served,
            download_completed=completed
        )
        
        self.logger.info(f"Recorded download of export {export_id} by user {user}")
        return download_record
    
    def get_download_statistics(self, export_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get download statistics for exports.
        
        Args:
            export_id: Specific export ID to get stats for (optional)
            
        Returns:
            Dictionary with download statistics
        """
        downloads_qs = ExportDownload.objects.filter(export_history__task=self.task)
        
        if export_id:
            downloads_qs = downloads_qs.filter(export_history__export_id=export_id)
        
        total_downloads = downloads_qs.count()
        completed_downloads = downloads_qs.filter(download_completed=True).count()
        unique_users = downloads_qs.filter(downloaded_by__isnull=False).values('downloaded_by').distinct().count()
        
        # Bytes served statistics
        bytes_stats = downloads_qs.filter(bytes_served__isnull=False).aggregate(
            total_bytes=Sum('bytes_served'),
            avg_bytes=Avg('bytes_served')
        )
        
        # Recent download activity
        last_24h = timezone.now() - timedelta(hours=24)
        recent_downloads = downloads_qs.filter(download_timestamp__gte=last_24h).count()
        
        return {
            'total_downloads': total_downloads,
            'completed_downloads': completed_downloads,
            'completion_rate': (completed_downloads / total_downloads * 100) if total_downloads > 0 else 0,
            'unique_users': unique_users,
            'total_bytes_served': bytes_stats.get('total_bytes', 0),
            'average_download_size': bytes_stats.get('avg_bytes', 0),
            'recent_downloads_24h': recent_downloads,
        }