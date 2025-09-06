# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import logging
import os
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from uuid import uuid4

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import User

from .ground_truth_export import ExportConfig, GroundTruthExportService, ExportJob
from .quality_control import AdvancedQualityController
from ..models import DetectionResult, MatchingSession

logger = logging.getLogger(__name__)


class ExportJobStatus(models.TextChoices):
    """Export job status enumeration."""
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ExportJobPriority(models.TextChoices):
    """Export job priority enumeration."""
    LOW = 'LOW', 'Low'
    NORMAL = 'NORMAL', 'Normal'
    HIGH = 'HIGH', 'High'
    URGENT = 'URGENT', 'Urgent'


class ExportJobRecord(models.Model):
    """Database model for tracking export jobs."""
    
    id = models.CharField(max_length=36, primary_key=True, default=uuid4)
    task_id = models.IntegerField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Job configuration
    config = models.JSONField(help_text="Export configuration parameters")
    priority = models.CharField(
        max_length=10,
        choices=ExportJobPriority.choices,
        default=ExportJobPriority.NORMAL
    )
    
    # Job status and progress
    status = models.CharField(
        max_length=15,
        choices=ExportJobStatus.choices,
        default=ExportJobStatus.PENDING
    )
    progress_percentage = models.IntegerField(default=0)
    progress_message = models.TextField(blank=True)
    
    # Timing information
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)
    
    # Results
    result_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    export_paths = models.JSONField(null=True, blank=True)
    total_detections_processed = models.IntegerField(null=True, blank=True)
    
    # Background job information
    rq_job_id = models.CharField(max_length=36, null=True, blank=True)
    
    class Meta:
        db_table = 'calibrix_matching_exportjobrecord'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_id', 'status']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['priority', 'status']),
        ]
    
    def __str__(self):
        return f"Export Job {self.id} - Task {self.task_id} ({self.status})"
    
    def update_progress(self, percentage: int, message: str):
        """Update job progress."""
        self.progress_percentage = percentage
        self.progress_message = message
        self.save(update_fields=['progress_percentage', 'progress_message'])
    
    def mark_started(self):
        """Mark job as started."""
        self.status = ExportJobStatus.IN_PROGRESS
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])
    
    def mark_completed(self, result_data: Dict[str, Any]):
        """Mark job as completed."""
        self.status = ExportJobStatus.COMPLETED
        self.completed_at = timezone.now()
        self.result_data = result_data
        self.progress_percentage = 100
        
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        
        # Extract useful information from results
        if 'export_paths' in result_data:
            self.export_paths = result_data['export_paths']
        
        if 'total_detections' in result_data:
            self.total_detections_processed = result_data['total_detections']
        
        self.save(update_fields=[
            'status', 'completed_at', 'result_data', 'progress_percentage',
            'duration_seconds', 'export_paths', 'total_detections_processed'
        ])
    
    def mark_failed(self, error_message: str):
        """Mark job as failed."""
        self.status = ExportJobStatus.FAILED
        self.completed_at = timezone.now()
        self.error_message = error_message
        
        if self.started_at:
            self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
        
        self.save(update_fields=[
            'status', 'completed_at', 'error_message', 'duration_seconds'
        ])
    
    def can_be_cancelled(self) -> bool:
        """Check if job can be cancelled."""
        return self.status in [ExportJobStatus.PENDING, ExportJobStatus.IN_PROGRESS]
    
    def cancel(self):
        """Cancel the job."""
        if self.can_be_cancelled():
            self.status = ExportJobStatus.CANCELLED
            self.completed_at = timezone.now()
            
            if self.started_at:
                self.duration_seconds = (self.completed_at - self.started_at).total_seconds()
            
            self.save(update_fields=['status', 'completed_at', 'duration_seconds'])
            
            # Cancel RQ job if exists
            if self.rq_job_id:
                try:
                    from rq import Queue
                    from django_rq import get_queue
                    
                    queue = get_queue('default')
                    job = queue.fetch_job(self.rq_job_id)
                    if job and job.get_status() in ['queued', 'started']:
                        job.cancel()
                        logger.info(f"Cancelled RQ job {self.rq_job_id}")
                except Exception as e:
                    logger.warning(f"Failed to cancel RQ job {self.rq_job_id}: {e}")


class BatchExportManager:
    """Manages batch export operations with job queuing."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.BatchExportManager")
    
    def submit_export_job(
        self,
        task_id: int,
        config: ExportConfig,
        user: Optional[User] = None,
        priority: ExportJobPriority = ExportJobPriority.NORMAL,
        callback_url: Optional[str] = None
    ) -> str:
        """Submit an export job to the queue."""
        
        # Create job record
        job_record = ExportJobRecord.objects.create(
            task_id=task_id,
            user=user,
            config=config.to_dict(),
            priority=priority
        )
        
        try:
            # Submit to RQ queue
            rq_job_id = self._submit_to_queue(job_record, callback_url)
            
            if rq_job_id:
                job_record.rq_job_id = rq_job_id
                job_record.save(update_fields=['rq_job_id'])
                
                self.logger.info(
                    f"Submitted export job {job_record.id} to queue with RQ job {rq_job_id}"
                )
            else:
                # Fallback to synchronous execution
                self.logger.warning(
                    f"RQ not available, executing export job {job_record.id} synchronously"
                )
                self._execute_job_sync(job_record)
            
            return str(job_record.id)
            
        except Exception as e:
            job_record.mark_failed(f"Failed to submit job: {e}")
            self.logger.error(f"Failed to submit export job {job_record.id}: {e}")
            raise
    
    def _submit_to_queue(self, job_record: ExportJobRecord, callback_url: Optional[str]) -> Optional[str]:
        """Submit job to RQ queue."""
        try:
            from rq import Queue
            from django_rq import get_queue
            
            # Determine queue based on priority
            queue_name = self._get_queue_name(job_record.priority)
            queue = get_queue(queue_name)
            
            # Calculate timeout based on expected job size
            timeout = self._calculate_timeout(job_record)
            
            # Submit job
            rq_job = queue.enqueue(
                'cvat.apps.calibrix_matching.services.batch_export.execute_export_job_rq',
                job_record.id,
                callback_url,
                timeout=timeout,
                job_id=str(job_record.id)
            )
            
            return rq_job.id
            
        except ImportError:
            self.logger.warning("RQ not available for job queuing")
            return None
        except Exception as e:
            self.logger.error(f"Failed to submit job to RQ: {e}")
            raise
    
    def _get_queue_name(self, priority: ExportJobPriority) -> str:
        """Get queue name based on priority."""
        if priority == ExportJobPriority.URGENT:
            return 'high'
        elif priority == ExportJobPriority.HIGH:
            return 'high'
        elif priority == ExportJobPriority.LOW:
            return 'low'
        else:
            return 'default'
    
    def _calculate_timeout(self, job_record: ExportJobRecord) -> str:
        """Calculate job timeout based on configuration."""
        config = ExportConfig.from_dict(job_record.config)
        
        # Base timeout
        base_timeout = 600  # 10 minutes
        
        # Adjust based on format complexity
        if config.export_format in ['coco', 'pascal_voc']:
            base_timeout *= 2
        
        # Adjust based on dataset splitting
        if config.dataset_split:
            base_timeout *= 1.5
        
        # Adjust based on streaming
        if config.streaming_export:
            base_timeout *= 0.8  # Streaming is more efficient
        
        return f"{int(base_timeout)}s"
    
    def _execute_job_sync(self, job_record: ExportJobRecord):
        """Execute job synchronously as fallback."""
        job_record.mark_started()
        
        try:
            config = ExportConfig.from_dict(job_record.config)
            job = ExportJob(job_record.task_id, config, job_id=str(job_record.id))
            
            # Custom progress tracking
            def progress_callback(percentage: int, message: str):
                job_record.update_progress(percentage, message)
            
            # Execute with progress tracking
            result = self._execute_with_progress_tracking(job, progress_callback)
            job_record.mark_completed(result)
            
        except Exception as e:
            job_record.mark_failed(str(e))
            raise
    
    def _execute_with_progress_tracking(
        self, 
        job: ExportJob, 
        progress_callback: Callable[[int, str], None]
    ) -> Dict[str, Any]:
        """Execute job with custom progress tracking."""
        
        # Override the update_progress method
        original_update_progress = job.update_progress
        
        def tracked_update_progress(percentage: int, message: str):
            progress_callback(percentage, message)
            original_update_progress(percentage, message)
        
        job.update_progress = tracked_update_progress
        
        return job.execute()
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get status of an export job."""
        try:
            job_record = ExportJobRecord.objects.get(id=job_id)
            
            status_data = {
                'job_id': job_id,
                'status': job_record.status,
                'progress_percentage': job_record.progress_percentage,
                'progress_message': job_record.progress_message,
                'created_at': job_record.created_at.isoformat(),
                'started_at': job_record.started_at.isoformat() if job_record.started_at else None,
                'completed_at': job_record.completed_at.isoformat() if job_record.completed_at else None,
                'duration_seconds': job_record.duration_seconds,
                'total_detections_processed': job_record.total_detections_processed,
                'export_paths': job_record.export_paths,
                'error_message': job_record.error_message
            }
            
            # Add RQ job status if available
            if job_record.rq_job_id:
                try:
                    from django_rq import get_queue
                    queue = get_queue('default')
                    rq_job = queue.fetch_job(job_record.rq_job_id)
                    
                    if rq_job:
                        status_data['rq_status'] = rq_job.get_status()
                        status_data['rq_progress'] = rq_job.meta.get('progress', 0)
                except Exception:
                    pass
            
            return status_data
            
        except ExportJobRecord.DoesNotExist:
            raise ValueError(f"Export job {job_id} not found")
    
    def cancel_job(self, job_id: str, user: Optional[User] = None) -> bool:
        """Cancel an export job."""
        try:
            job_record = ExportJobRecord.objects.get(id=job_id)
            
            # Check permissions
            if user and job_record.user and job_record.user != user:
                raise PermissionError("Not authorized to cancel this job")
            
            if job_record.can_be_cancelled():
                job_record.cancel()
                self.logger.info(f"Cancelled export job {job_id}")
                return True
            else:
                self.logger.warning(f"Cannot cancel job {job_id} with status {job_record.status}")
                return False
                
        except ExportJobRecord.DoesNotExist:
            raise ValueError(f"Export job {job_id} not found")
    
    def list_jobs(
        self,
        user: Optional[User] = None,
        task_id: Optional[int] = None,
        status: Optional[ExportJobStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List export jobs with filtering."""
        
        queryset = ExportJobRecord.objects.all()
        
        # Apply filters
        if user:
            queryset = queryset.filter(user=user)
        
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        
        if status:
            queryset = queryset.filter(status=status)
        
        # Get total count
        total_count = queryset.count()
        
        # Apply pagination
        jobs = list(queryset[offset:offset + limit])
        
        # Convert to dict format
        job_data = []
        for job in jobs:
            job_data.append({
                'job_id': str(job.id),
                'task_id': job.task_id,
                'user_id': job.user.id if job.user else None,
                'status': job.status,
                'priority': job.priority,
                'progress_percentage': job.progress_percentage,
                'created_at': job.created_at.isoformat(),
                'duration_seconds': job.duration_seconds,
                'total_detections_processed': job.total_detections_processed,
                'export_format': job.config.get('export_format') if job.config else None
            })
        
        return {
            'jobs': job_data,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count
        }
    
    def cleanup_old_jobs(self, days_old: int = 30):
        """Clean up old completed jobs."""
        cutoff_date = timezone.now() - timedelta(days=days_old)
        
        old_jobs = ExportJobRecord.objects.filter(
            completed_at__lt=cutoff_date,
            status__in=[ExportJobStatus.COMPLETED, ExportJobStatus.FAILED, ExportJobStatus.CANCELLED]
        )
        
        deleted_count = 0
        
        for job in old_jobs:
            # Clean up export files if they exist
            if job.export_paths:
                self._cleanup_job_files(job.export_paths)
            
            job.delete()
            deleted_count += 1
        
        self.logger.info(f"Cleaned up {deleted_count} old export jobs")
        return deleted_count
    
    def _cleanup_job_files(self, export_paths: Dict[str, Any]):
        """Clean up files associated with a job."""
        try:
            if isinstance(export_paths, dict):
                for path in export_paths.values():
                    if isinstance(path, str) and os.path.exists(path):
                        if os.path.isfile(path):
                            os.remove(path)
                        elif os.path.isdir(path):
                            import shutil
                            shutil.rmtree(path)
            elif isinstance(export_paths, str) and os.path.exists(export_paths):
                if os.path.isfile(export_paths):
                    os.remove(export_paths)
                elif os.path.isdir(export_paths):
                    import shutil
                    shutil.rmtree(export_paths)
                    
        except Exception as e:
            self.logger.warning(f"Failed to cleanup export files: {e}")
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get statistics about job queues."""
        stats = {
            'total_jobs': ExportJobRecord.objects.count(),
            'jobs_by_status': {},
            'jobs_by_priority': {},
            'average_duration': 0,
            'queue_health': 'unknown'
        }
        
        # Job counts by status
        status_counts = ExportJobRecord.objects.values('status').annotate(count=models.Count('id'))
        for item in status_counts:
            stats['jobs_by_status'][item['status']] = item['count']
        
        # Job counts by priority
        priority_counts = ExportJobRecord.objects.values('priority').annotate(count=models.Count('id'))
        for item in priority_counts:
            stats['jobs_by_priority'][item['priority']] = item['count']
        
        # Average duration for completed jobs
        avg_duration = ExportJobRecord.objects.filter(
            status=ExportJobStatus.COMPLETED,
            duration_seconds__isnull=False
        ).aggregate(avg_duration=models.Avg('duration_seconds'))
        
        stats['average_duration'] = avg_duration['avg_duration'] or 0
        
        # RQ queue statistics if available
        try:
            from django_rq import get_queue
            
            queue_stats = {}
            for queue_name in ['default', 'high', 'low']:
                try:
                    queue = get_queue(queue_name)
                    queue_stats[queue_name] = {
                        'length': len(queue),
                        'failed_jobs': len(queue.failed_job_registry),
                        'scheduled_jobs': len(queue.scheduled_job_registry)
                    }
                except Exception:
                    queue_stats[queue_name] = {'error': 'unavailable'}
            
            stats['rq_queues'] = queue_stats
            stats['queue_health'] = 'healthy'
            
        except ImportError:
            stats['queue_health'] = 'rq_unavailable'
        
        return stats


class ExportJobMonitor:
    """Monitors and manages export job lifecycle."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.ExportJobMonitor")
    
    def check_stuck_jobs(self):
        """Check for and handle stuck jobs."""
        # Define timeout thresholds
        in_progress_timeout = timedelta(hours=2)
        pending_timeout = timedelta(hours=6)
        
        current_time = timezone.now()
        
        # Find jobs stuck in IN_PROGRESS
        stuck_in_progress = ExportJobRecord.objects.filter(
            status=ExportJobStatus.IN_PROGRESS,
            started_at__lt=current_time - in_progress_timeout
        )
        
        for job in stuck_in_progress:
            self.logger.warning(f"Found stuck job {job.id}, marking as failed")
            job.mark_failed("Job timed out - stuck in progress state")
        
        # Find jobs stuck in PENDING
        stuck_pending = ExportJobRecord.objects.filter(
            status=ExportJobStatus.PENDING,
            created_at__lt=current_time - pending_timeout
        )
        
        for job in stuck_pending:
            self.logger.warning(f"Found stuck pending job {job.id}, marking as failed")
            job.mark_failed("Job timed out - stuck in pending state")
        
        total_stuck = stuck_in_progress.count() + stuck_pending.count()
        if total_stuck > 0:
            self.logger.info(f"Handled {total_stuck} stuck jobs")
        
        return total_stuck
    
    def retry_failed_jobs(self, max_retries: int = 3):
        """Retry failed jobs that can be retried."""
        retryable_jobs = ExportJobRecord.objects.filter(
            status=ExportJobStatus.FAILED,
            result_data__retry_count__lt=max_retries
        ).exclude(
            error_message__icontains='timeout'
        )[:10]  # Limit retries
        
        batch_manager = BatchExportManager()
        retry_count = 0
        
        for job in retryable_jobs:
            try:
                # Update retry count
                retry_data = job.result_data or {}
                retry_data['retry_count'] = retry_data.get('retry_count', 0) + 1
                
                # Create new job with same config
                config = ExportConfig.from_dict(job.config)
                new_job_id = batch_manager.submit_export_job(
                    task_id=job.task_id,
                    config=config,
                    user=job.user,
                    priority=job.priority
                )
                
                # Mark original job as cancelled
                job.status = ExportJobStatus.CANCELLED
                job.result_data = retry_data
                job.error_message += f" [Retried as job {new_job_id}]"
                job.save()
                
                retry_count += 1
                self.logger.info(f"Retried failed job {job.id} as new job {new_job_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to retry job {job.id}: {e}")
        
        return retry_count


# RQ Task Functions
def execute_export_job_rq(job_id: str, callback_url: Optional[str] = None) -> Dict[str, Any]:
    """RQ task function for executing export jobs."""
    try:
        job_record = ExportJobRecord.objects.get(id=job_id)
        job_record.mark_started()
        
        # Create and execute job
        config = ExportConfig.from_dict(job_record.config)
        job = ExportJob(job_record.task_id, config, job_id=job_id)
        
        # Custom progress tracking for RQ
        def rq_progress_callback(percentage: int, message: str):
            job_record.update_progress(percentage, message)
            
            # Update RQ job meta
            try:
                from rq import get_current_job
                current_job = get_current_job()
                if current_job:
                    current_job.meta['progress'] = percentage
                    current_job.meta['message'] = message
                    current_job.save_meta()
            except Exception:
                pass
        
        # Override progress tracking
        original_update_progress = job.update_progress
        
        def combined_update_progress(percentage: int, message: str):
            rq_progress_callback(percentage, message)
            original_update_progress(percentage, message)
        
        job.update_progress = combined_update_progress
        
        # Execute job
        result = job.execute()
        
        # Mark as completed
        job_record.mark_completed(result)
        
        # Call webhook if provided
        if callback_url and result.get('status') == 'completed':
            try:
                import requests
                requests.post(
                    callback_url,
                    json={
                        'job_id': job_id,
                        'status': 'completed',
                        'result': result
                    },
                    timeout=30
                )
            except Exception as e:
                logger.warning(f"Failed to call webhook {callback_url}: {e}")
        
        return result
        
    except ExportJobRecord.DoesNotExist:
        error_msg = f"Export job {job_id} not found"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        try:
            job_record = ExportJobRecord.objects.get(id=job_id)
            job_record.mark_failed(str(e))
        except Exception:
            pass
        
        logger.error(f"Export job {job_id} failed: {e}")
        raise


def cleanup_export_jobs_task(days_old: int = 30) -> int:
    """RQ task for cleaning up old export jobs."""
    manager = BatchExportManager()
    return manager.cleanup_old_jobs(days_old)


def monitor_export_jobs_task() -> Dict[str, int]:
    """RQ task for monitoring export jobs."""
    monitor = ExportJobMonitor()
    
    stuck_jobs = monitor.check_stuck_jobs()
    retried_jobs = monitor.retry_failed_jobs()
    
    return {
        'stuck_jobs_handled': stuck_jobs,
        'jobs_retried': retried_jobs
    }