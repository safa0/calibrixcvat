# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import csv
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from ..models import ROITemplate, MatchingSession, DetectionResult
from cvat.apps.engine.models import Task

logger = logging.getLogger(__name__)


class GroundTruthExporter:
    """
    Service class for exporting ground truth data from detection results.
    """
    
    SUPPORTED_FORMATS = ['csv', 'json', 'xml']
    
    def __init__(self, task_id: int, export_format: str = 'csv'):
        """
        Initialize the exporter.
        
        Args:
            task_id: ID of the task to export data for
            export_format: Format for export (csv, json, xml)
        """
        if export_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        try:
            self.task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            raise ValueError(f"Task {task_id} not found")
        
        self.task_id = task_id
        self.export_format = export_format
        self.export_dir = os.path.join(settings.EXPORT_CACHE_ROOT, 'calibrix_matching')
        os.makedirs(self.export_dir, exist_ok=True)
    
    def get_detection_queryset(
        self,
        confirmed_only: bool = True,
        min_confidence: Optional[float] = None,
        roi_template_id: Optional[int] = None
    ):
        """
        Get queryset of detection results to export.
        
        Args:
            confirmed_only: Only include confirmed detections
            min_confidence: Minimum confidence score
            roi_template_id: Filter by specific ROI template
            
        Returns:
            Queryset of DetectionResult objects
        """
        queryset = DetectionResult.objects.select_related(
            'matching_session',
            'matching_session__roi_template',
            'matching_session__task'
        ).filter(
            matching_session__task_id=self.task_id
        ).order_by('frame_number', '-confidence_score')
        
        if confirmed_only:
            queryset = queryset.filter(is_confirmed=True)
        
        if min_confidence is not None:
            queryset = queryset.filter(confidence_score__gte=min_confidence)
        
        if roi_template_id:
            queryset = queryset.filter(matching_session__roi_template_id=roi_template_id)
        
        return queryset
    
    def prepare_export_data(self, queryset) -> List[Dict[str, Any]]:
        """
        Prepare detection data for export.
        
        Args:
            queryset: Queryset of DetectionResult objects
            
        Returns:
            List of dictionaries containing export data
        """
        export_data = []
        
        for detection in queryset:
            data_row = {
                # Detection information
                'detection_id': detection.id,
                'frame_number': detection.frame_number,
                'confidence_score': detection.confidence_score,
                'is_confirmed': detection.is_confirmed,
                'detection_created_at': detection.created_at.isoformat(),
                
                # Bounding box coordinates
                'bbox_x': detection.coordinates.get('x', 0),
                'bbox_y': detection.coordinates.get('y', 0),
                'bbox_width': detection.coordinates.get('width', 0),
                'bbox_height': detection.coordinates.get('height', 0),
                
                # ROI template information
                'roi_template_id': detection.matching_session.roi_template.id,
                'roi_template_name': detection.matching_session.roi_template.name,
                'roi_template_algorithm': detection.matching_session.roi_template.feature_descriptor.get('algorithm', ''),
                
                # Matching session information
                'matching_session_id': detection.matching_session.id,
                'matching_algorithm': detection.matching_session.algorithm_type,
                'matching_threshold': detection.matching_session.threshold,
                'session_status': detection.matching_session.status,
                'session_created_at': detection.matching_session.created_at.isoformat(),
                
                # Task information
                'task_id': detection.matching_session.task.id,
                'task_name': detection.matching_session.task.name,
            }
            
            export_data.append(data_row)
        
        return export_data
    
    def export_to_csv(self, export_data: List[Dict[str, Any]], filepath: str):
        """
        Export data to CSV format.
        
        Args:
            export_data: List of data dictionaries
            filepath: Output file path
        """
        if not export_data:
            # Create empty CSV with headers
            fieldnames = [
                'detection_id', 'frame_number', 'confidence_score', 'is_confirmed',
                'detection_created_at', 'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height',
                'roi_template_id', 'roi_template_name', 'roi_template_algorithm',
                'matching_session_id', 'matching_algorithm', 'matching_threshold',
                'session_status', 'session_created_at', 'task_id', 'task_name'
            ]
        else:
            fieldnames = export_data[0].keys()
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_data)
        
        logger.info(f"Exported {len(export_data)} records to CSV: {filepath}")
    
    def export_to_json(self, export_data: List[Dict[str, Any]], filepath: str):
        """
        Export data to JSON format.
        
        Args:
            export_data: List of data dictionaries
            filepath: Output file path
        """
        export_package = {
            'metadata': {
                'task_id': self.task_id,
                'task_name': self.task.name,
                'export_format': 'json',
                'export_timestamp': timezone.now().isoformat(),
                'total_detections': len(export_data),
                'export_version': '1.0'
            },
            'detections': export_data
        }
        
        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_package, jsonfile, indent=2, ensure_ascii=False)
        
        logger.info(f"Exported {len(export_data)} records to JSON: {filepath}")
    
    def export_to_xml(self, export_data: List[Dict[str, Any]], filepath: str):
        """
        Export data to XML format.
        
        Args:
            export_data: List of data dictionaries
            filepath: Output file path
        """
        from xml.etree.ElementTree import Element, SubElement, ElementTree
        from xml.dom import minidom
        
        # Create root element
        root = Element('ground_truth_export')
        
        # Add metadata
        metadata = SubElement(root, 'metadata')
        SubElement(metadata, 'task_id').text = str(self.task_id)
        SubElement(metadata, 'task_name').text = self.task.name
        SubElement(metadata, 'export_format').text = 'xml'
        SubElement(metadata, 'export_timestamp').text = timezone.now().isoformat()
        SubElement(metadata, 'total_detections').text = str(len(export_data))
        SubElement(metadata, 'export_version').text = '1.0'
        
        # Add detections
        detections = SubElement(root, 'detections')
        
        for data_row in export_data:
            detection = SubElement(detections, 'detection')
            
            for key, value in data_row.items():
                element = SubElement(detection, key)
                element.text = str(value) if value is not None else ''
        
        # Pretty print XML
        rough_string = ElementTree.tostring(root, 'utf-8')
        reparsed = minidom.parseString(rough_string)
        pretty_xml = reparsed.toprettyxml(indent='  ')
        
        with open(filepath, 'w', encoding='utf-8') as xmlfile:
            xmlfile.write(pretty_xml)
        
        logger.info(f"Exported {len(export_data)} records to XML: {filepath}")
    
    def generate_filename(self, timestamp: Optional[datetime] = None) -> str:
        """
        Generate a filename for the export.
        
        Args:
            timestamp: Optional timestamp for filename
            
        Returns:
            Generated filename
        """
        if timestamp is None:
            timestamp = timezone.now()
        
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
        filename = f"calibrix_ground_truth_task_{self.task_id}_{timestamp_str}.{self.export_format}"
        
        return filename
    
    def export(
        self,
        confirmed_only: bool = True,
        min_confidence: Optional[float] = None,
        roi_template_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform the export operation.
        
        Args:
            confirmed_only: Only include confirmed detections
            min_confidence: Minimum confidence score
            roi_template_id: Filter by specific ROI template
            
        Returns:
            Dictionary with export results
        """
        start_time = time.time()
        
        try:
            # Get detection data
            queryset = self.get_detection_queryset(
                confirmed_only=confirmed_only,
                min_confidence=min_confidence,
                roi_template_id=roi_template_id
            )
            
            export_data = self.prepare_export_data(queryset)
            
            # Generate filename and filepath
            filename = self.generate_filename()
            filepath = os.path.join(self.export_dir, filename)
            
            # Export based on format
            if self.export_format == 'csv':
                self.export_to_csv(export_data, filepath)
            elif self.export_format == 'json':
                self.export_to_json(export_data, filepath)
            elif self.export_format == 'xml':
                self.export_to_xml(export_data, filepath)
            
            # Calculate file size
            file_size = os.path.getsize(filepath)
            
            duration = time.time() - start_time
            
            result = {
                'status': 'completed',
                'filepath': filepath,
                'filename': filename,
                'file_size': file_size,
                'total_detections': len(export_data),
                'export_format': self.export_format,
                'duration_seconds': duration,
                'download_url': f"/api/calibrix/ground-truth/download/{filename}",  # Placeholder URL
            }
            
            logger.info(f"Ground truth export completed for task {self.task_id}: "
                       f"{len(export_data)} detections exported to {filename} in {duration:.1f} seconds")
            
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Ground truth export failed for task {self.task_id} after {duration:.1f} seconds: {e}")
            raise


def export_ground_truth_task(
    task_id: int,
    export_format: str = 'csv',
    confirmed_only: bool = True,
    min_confidence: Optional[float] = None,
    roi_template_id: Optional[int] = None,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    RQ task function for exporting ground truth data.
    
    Args:
        task_id: ID of the task to export data for
        export_format: Format for export (csv, json, xml)
        confirmed_only: Only include confirmed detections
        min_confidence: Minimum confidence score
        roi_template_id: Filter by specific ROI template
        user_id: ID of the user requesting the export
        
    Returns:
        Dictionary with export results
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting ground truth export for task {task_id} (format: {export_format})")
        
        # Create exporter
        exporter = GroundTruthExporter(task_id, export_format)
        
        # Perform export
        result = exporter.export(
            confirmed_only=confirmed_only,
            min_confidence=min_confidence,
            roi_template_id=roi_template_id
        )
        
        # Add user information if provided
        if user_id:
            result['user_id'] = user_id
        
        # Add timing information
        duration = time.time() - start_time
        result['total_duration_seconds'] = duration
        result['task_id'] = task_id
        
        logger.info(f"Completed ground truth export for task {task_id} in {duration:.1f} seconds")
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Ground truth export failed for task {task_id} after {duration:.1f} seconds: {e}"
        logger.error(error_msg)
        raise Exception(error_msg)


def get_export_statistics(task_id: int) -> Dict[str, Any]:
    """
    Get statistics about available detection data for export.
    
    Args:
        task_id: ID of the task
        
    Returns:
        Dictionary with statistics
    """
    try:
        task = Task.objects.get(id=task_id)
        
        # Get detection statistics
        all_detections = DetectionResult.objects.filter(
            matching_session__task_id=task_id
        )
        
        confirmed_detections = all_detections.filter(is_confirmed=True)
        
        # Get ROI template statistics
        roi_templates = ROITemplate.objects.filter(task_id=task_id)
        matching_sessions = MatchingSession.objects.filter(task_id=task_id)
        
        # Calculate confidence statistics
        confidence_stats = all_detections.aggregate(
            avg_confidence=models.Avg('confidence_score'),
            min_confidence=models.Min('confidence_score'),
            max_confidence=models.Max('confidence_score')
        )
        
        statistics = {
            'task_id': task_id,
            'task_name': task.name,
            'total_detections': all_detections.count(),
            'confirmed_detections': confirmed_detections.count(),
            'unconfirmed_detections': all_detections.filter(is_confirmed=False).count(),
            'roi_templates_count': roi_templates.count(),
            'matching_sessions_count': matching_sessions.count(),
            'completed_sessions_count': matching_sessions.filter(
                status=MatchingSession.Status.COMPLETED
            ).count(),
            'confidence_statistics': confidence_stats,
            'frame_coverage': {
                'min_frame': all_detections.aggregate(min_frame=models.Min('frame_number'))['min_frame'],
                'max_frame': all_detections.aggregate(max_frame=models.Max('frame_number'))['max_frame'],
                'unique_frames_with_detections': all_detections.values('frame_number').distinct().count()
            }
        }
        
        return statistics
        
    except Task.DoesNotExist:
        raise ValueError(f"Task {task_id} not found")
    except Exception as e:
        logger.error(f"Error getting export statistics for task {task_id}: {e}")
        raise


def cleanup_old_exports(days_old: int = 7):
    """
    Clean up old export files.
    
    Args:
        days_old: Number of days after which to delete export files
    """
    try:
        export_dir = os.path.join(settings.EXPORT_CACHE_ROOT, 'calibrix_matching')
        if not os.path.exists(export_dir):
            return
        
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        deleted_count = 0
        
        for filename in os.listdir(export_dir):
            filepath = os.path.join(export_dir, filename)
            if os.path.isfile(filepath):
                file_mtime = os.path.getmtime(filepath)
                if file_mtime < cutoff_time:
                    os.remove(filepath)
                    deleted_count += 1
                    logger.debug(f"Deleted old export file: {filename}")
        
        logger.info(f"Cleanup completed: deleted {deleted_count} old export files")
        
    except Exception as e:
        logger.error(f"Error during export cleanup: {e}")
        raise