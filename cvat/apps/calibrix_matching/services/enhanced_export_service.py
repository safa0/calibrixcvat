# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import logging
import os
import time
from typing import Dict, Any, Optional, List
from uuid import UUID
from django.contrib.auth.models import User
from django.utils import timezone
from pathlib import Path

from .ground_truth_export import (
    GroundTruthExportService, ExportConfig, ExportJob,
    QualityControlValidator, DatasetSplitter
)
from .export_history_service import ExportHistoryService
from ..models import ExportHistory

logger = logging.getLogger(__name__)


class EnhancedGroundTruthExportService(GroundTruthExportService):
    """
    Enhanced Ground Truth Export Service with history tracking, 
    incremental exports, and advanced features.
    """
    
    def __init__(self, task_id: int):
        super().__init__(task_id)
        self.history_service = ExportHistoryService(task_id)
        self.logger = logging.getLogger(f"{__name__}.EnhancedGroundTruthExportService")
    
    def export_with_history(
        self, 
        config: ExportConfig, 
        user: Optional[User] = None,
        check_duplicates: bool = True
    ) -> Dict[str, Any]:
        """
        Export with full history tracking and duplicate checking.
        
        Args:
            config: Export configuration
            user: User initiating the export
            check_duplicates: Whether to check for recent similar exports
            
        Returns:
            Dictionary with export results and history information
        """
        start_time = time.time()
        
        # Check for similar recent exports if requested
        if check_duplicates:
            similar_exports = self.history_service.find_similar_exports(config)
            if similar_exports:
                self.logger.info(f"Found {len(similar_exports)} similar recent exports")
                return {
                    'status': 'duplicate_found',
                    'message': 'Similar export found recently',
                    'similar_exports': [export.get_export_summary() for export in similar_exports[:3]],
                    'duration_seconds': time.time() - start_time
                }
        
        # Create export history record
        export_record = self.history_service.create_export_record(
            export_format=config.export_format,
            config=config,
            user=user
        )
        
        try:
            # Mark as started
            export_record.mark_as_started()
            
            # Perform the actual export
            result = self.export(config)
            
            # Update history with results
            file_size = None
            if result.get('export_path') and os.path.exists(result['export_path']):
                if os.path.isfile(result['export_path']):
                    file_size = os.path.getsize(result['export_path'])
                else:
                    # Calculate directory size
                    file_size = sum(
                        os.path.getsize(os.path.join(dirpath, filename))
                        for dirpath, dirnames, filenames in os.walk(result['export_path'])
                        for filename in filenames
                    )
            
            export_record.mark_as_completed(
                export_path=result.get('export_path', ''),
                file_size=file_size
            )
            
            # Add history information to result
            result.update({
                'export_id': str(export_record.export_id),
                'export_history': export_record.get_export_summary(),
                'history_tracked': True
            })
            
            return result
            
        except Exception as e:
            # Mark as failed in history
            export_record.mark_as_failed(
                error_message=str(e),
                error_details={'exception_type': type(e).__name__}
            )
            
            duration = time.time() - start_time
            self.logger.error(f"Enhanced export failed after {duration:.1f}s: {e}")
            raise
    
    def export_incremental(
        self,
        config: ExportConfig,
        base_export_id: UUID,
        user: Optional[User] = None
    ) -> Dict[str, Any]:
        """
        Perform incremental export based on a previous export.
        
        Args:
            config: Export configuration
            base_export_id: Base export to build upon
            user: User initiating the export
            
        Returns:
            Dictionary with incremental export results
        """
        start_time = time.time()
        
        # Calculate what would be different
        diff_info = self.history_service.calculate_export_diff(base_export_id, config)
        
        if diff_info['new_detections_since_base'] == 0:
            return {
                'status': 'no_changes',
                'message': 'No new detections since base export',
                'base_export_id': str(base_export_id),
                'diff_info': diff_info,
                'duration_seconds': time.time() - start_time
            }
        
        # Create incremental export record
        export_record = self.history_service.create_export_record(
            export_format=config.export_format,
            config=config,
            user=user,
            parent_export_id=base_export_id
        )
        
        try:
            export_record.mark_as_started()
            
            # Perform export with only new data
            incremental_config = ExportConfig.from_dict(config.to_dict())
            
            # Get base export creation time to filter new detections
            base_export = ExportHistory.objects.get(export_id=base_export_id)
            
            # Modify queryset to only include new detections
            # This would require extending the base service to support date filtering
            result = self._export_new_detections_since(incremental_config, base_export.created_at)
            
            # Update history
            file_size = None
            if result.get('export_path') and os.path.exists(result['export_path']):
                file_size = os.path.getsize(result['export_path'])
            
            export_record.mark_as_completed(
                export_path=result.get('export_path', ''),
                file_size=file_size
            )
            
            result.update({
                'export_id': str(export_record.export_id),
                'is_incremental': True,
                'base_export_id': str(base_export_id),
                'diff_info': diff_info,
                'export_history': export_record.get_export_summary()
            })
            
            return result
            
        except Exception as e:
            export_record.mark_as_failed(str(e))
            duration = time.time() - start_time
            self.logger.error(f"Incremental export failed after {duration:.1f}s: {e}")
            raise
    
    def _export_new_detections_since(
        self,
        config: ExportConfig,
        since_date
    ) -> Dict[str, Any]:
        """
        Export only detections created since a specific date.
        
        Args:
            config: Export configuration
            since_date: Only include detections created after this date
            
        Returns:
            Export result dictionary
        """
        # Get detections created since the specified date
        detections = self.get_detection_queryset(
            confirmed_only=config.confirmed_only,
            min_confidence=config.min_confidence,
            roi_template_id=config.roi_template_id
        )
        
        # Filter by creation date (this would need to be added to the base method)
        new_detections = [d for d in detections if d.created_at > since_date]
        
        if not new_detections:
            return {
                'status': 'completed',
                'total_detections': 0,
                'message': 'No new detections to export',
                'duration_seconds': 0
            }
        
        # Export the new detections
        return self._export_with_format(new_detections, config)
    
    def get_export_recommendations(self, config: ExportConfig) -> Dict[str, Any]:
        """
        Get recommendations for optimizing the export.
        
        Args:
            config: Proposed export configuration
            
        Returns:
            Dictionary with recommendations
        """
        recommendations = {
            'config_suggestions': [],
            'performance_tips': [],
            'similar_exports': [],
            'incremental_candidates': []
        }
        
        # Check for similar recent exports
        similar_exports = self.history_service.find_similar_exports(config, time_window_hours=168)  # 1 week
        if similar_exports:
            recommendations['similar_exports'] = [
                export.get_export_summary() for export in similar_exports[:5]
            ]
            recommendations['config_suggestions'].append({
                'type': 'duplicate_avoidance',
                'message': f'Found {len(similar_exports)} similar exports in the last week. Consider reusing existing export.',
                'severity': 'info'
            })
        
        # Check for incremental export opportunities
        incremental_candidates = self.history_service.get_incremental_export_candidates()
        if incremental_candidates:
            recommendations['incremental_candidates'] = [
                export.get_export_summary() for export in incremental_candidates[:3]
            ]
            
            # Calculate potential savings for each candidate
            for candidate in incremental_candidates[:3]:
                try:
                    diff_info = self.history_service.calculate_export_diff(
                        candidate.export_id, config
                    )
                    if diff_info['is_incremental_worthwhile']:
                        recommendations['config_suggestions'].append({
                            'type': 'incremental_opportunity',
                            'message': f'Incremental export could save {100 - diff_info["change_percentage"]:.1f}% processing time',
                            'base_export_id': str(candidate.export_id),
                            'severity': 'tip'
                        })
                except Exception:
                    continue
        
        # Performance recommendations based on detection count
        detection_count = len(self.get_detection_queryset(
            confirmed_only=config.confirmed_only,
            min_confidence=config.min_confidence,
            roi_template_id=config.roi_template_id
        ))
        
        if detection_count > 10000:
            recommendations['performance_tips'].append({
                'type': 'large_dataset',
                'message': 'Large dataset detected. Consider enabling streaming export or splitting the dataset.',
                'suggestion': 'Set streaming_export=True or use dataset_split configuration',
                'severity': 'tip'
            })
        
        if config.include_images and detection_count > 1000:
            recommendations['performance_tips'].append({
                'type': 'image_inclusion',
                'message': 'Including images with large datasets significantly increases export size and time.',
                'suggestion': 'Consider exporting without images for faster processing',
                'severity': 'warning'
            })
        
        # Format-specific recommendations
        if config.export_format == 'yolo' and config.compression_format == 'none':
            recommendations['config_suggestions'].append({
                'type': 'compression',
                'message': 'YOLO exports create many files. Compression recommended.',
                'suggestion': 'Set compression_format="zip"',
                'severity': 'tip'
            })
        
        return recommendations
    
    def validate_export_config(self, config: ExportConfig) -> Dict[str, Any]:
        """
        Validate export configuration and provide detailed feedback.
        
        Args:
            config: Export configuration to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'info': []
        }
        
        # Basic config validation
        try:
            config.validate()
        except ValueError as e:
            validation_result['is_valid'] = False
            validation_result['errors'].append({
                'field': 'configuration',
                'message': str(e)
            })
        
        # Check if any detections would be exported
        detection_count = len(self.get_detection_queryset(
            confirmed_only=config.confirmed_only,
            min_confidence=config.min_confidence,
            roi_template_id=config.roi_template_id
        ))
        
        if detection_count == 0:
            validation_result['warnings'].append({
                'field': 'filters',
                'message': 'No detections match the specified criteria. Export would be empty.'
            })
        else:
            validation_result['info'].append({
                'field': 'detections',
                'message': f'{detection_count} detections will be exported'
            })
        
        # Format-specific validation
        if config.export_format == 'yolo':
            # Check if we have class information
            templates_count = len(set(
                d.matching_session.roi_template for d in 
                self.get_detection_queryset(
                    confirmed_only=config.confirmed_only,
                    min_confidence=config.min_confidence,
                    roi_template_id=config.roi_template_id
                )
            ))
            
            validation_result['info'].append({
                'field': 'classes',
                'message': f'{templates_count} classes will be included in YOLO export'
            })
        
        # Dataset splitting validation
        if config.dataset_split:
            total_ratio = sum(config.dataset_split.values())
            if abs(total_ratio - 1.0) > 0.01:
                validation_result['errors'].append({
                    'field': 'dataset_split',
                    'message': f'Dataset split ratios sum to {total_ratio:.2f}, should be 1.0'
                })
                validation_result['is_valid'] = False
        
        return validation_result
    
    def get_export_progress(self, export_id: UUID) -> Dict[str, Any]:
        """
        Get progress information for an ongoing export.
        
        Args:
            export_id: Export ID to check progress for
            
        Returns:
            Dictionary with progress information
        """
        try:
            export_record = ExportHistory.objects.get(
                export_id=export_id,
                task=self.task
            )
            
            progress_info = export_record.get_export_summary()
            
            # Add estimated completion time if in progress
            if export_record.is_in_progress and export_record.started_at:
                elapsed = (timezone.now() - export_record.started_at).total_seconds()
                
                # Rough estimate based on typical processing rates
                if export_record.total_detections > 0:
                    estimated_rate = 50  # detections per second (conservative)
                    estimated_total_time = export_record.total_detections / estimated_rate
                    estimated_remaining = max(0, estimated_total_time - elapsed)
                    
                    progress_info.update({
                        'elapsed_seconds': elapsed,
                        'estimated_remaining_seconds': estimated_remaining,
                        'estimated_completion': (
                            timezone.now() + timezone.timedelta(seconds=estimated_remaining)
                        ).isoformat()
                    })
            
            return progress_info
            
        except ExportHistory.DoesNotExist:
            return {
                'error': f'Export {export_id} not found',
                'status': 'not_found'
            }
    
    def cancel_export(self, export_id: UUID, user: Optional[User] = None) -> bool:
        """
        Cancel an ongoing export.
        
        Args:
            export_id: Export ID to cancel
            user: User requesting cancellation
            
        Returns:
            True if successfully cancelled
        """
        try:
            export_record = ExportHistory.objects.get(
                export_id=export_id,
                task=self.task
            )
            
            if not export_record.is_in_progress:
                return False
            
            # Update status to cancelled
            self.history_service.update_export_progress(
                export_id=export_id,
                status=ExportHistory.ExportStatus.CANCELLED,
                error_message=f'Cancelled by user {user}' if user else 'Cancelled'
            )
            
            # TODO: Implement actual job cancellation if using background jobs
            self.logger.info(f"Export {export_id} cancelled by user {user}")
            return True
            
        except ExportHistory.DoesNotExist:
            return False