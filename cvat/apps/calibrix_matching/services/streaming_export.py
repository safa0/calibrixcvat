# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import logging
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Any, Optional, Iterator, Generator, IO
from xml.etree.ElementTree import Element, SubElement, ElementTree

import yaml
from django.db import connection
from django.db.models import QuerySet

from .ground_truth_export import (
    BaseExporter, ExportConfig, GroundTruthExportService
)
from ..models import DetectionResult

logger = logging.getLogger(__name__)


class StreamingExportMixin:
    """Mixin class for streaming export functionality."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_size = getattr(self.config, 'batch_size', 100)
        self.memory_limit_mb = getattr(self.config, 'memory_limit_mb', 500)
    
    def stream_detections(self, queryset: QuerySet) -> Generator[List[DetectionResult], None, None]:
        """Stream detections in batches to manage memory usage."""
        total_count = queryset.count()
        processed = 0
        
        self.logger.info(f"Starting streaming export of {total_count} detections")
        
        while processed < total_count:
            # Fetch batch with select_related to minimize queries
            batch = list(
                queryset.select_related(
                    'matching_session__roi_template',
                    'matching_session__task'
                )[processed:processed + self.batch_size]
            )
            
            if not batch:
                break
            
            yield batch
            processed += len(batch)
            
            # Log progress
            progress = (processed / total_count) * 100
            self.logger.debug(f"Processed {processed}/{total_count} detections ({progress:.1f}%)")
            
            # Force garbage collection for memory management
            if processed % (self.batch_size * 10) == 0:
                import gc
                gc.collect()
    
    @contextmanager
    def memory_monitor(self):
        """Context manager for monitoring memory usage."""
        import psutil
        import gc
        
        process = psutil.Process()
        start_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        try:
            yield
        finally:
            gc.collect()
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_delta = end_memory - start_memory
            
            self.logger.debug(f"Memory usage: {start_memory:.1f}MB -> {end_memory:.1f}MB (Δ{memory_delta:+.1f}MB)")
            
            if end_memory > self.memory_limit_mb:
                self.logger.warning(f"Memory usage {end_memory:.1f}MB exceeds limit {self.memory_limit_mb}MB")


class StreamingCOCOExporter(BaseExporter, StreamingExportMixin):
    """COCO format exporter with streaming support for large datasets."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to COCO JSON format using streaming."""
        if not self.config.streaming_export:
            # Use standard export for small datasets
            return super().export(detections)
        
        output_path = self.output_dir / f"coco_streaming_export_{int(time.time())}.json"
        
        with self.memory_monitor():
            self._write_streaming_coco(detections, output_path)
        
        self.logger.info(f"Streaming COCO export completed: {output_path}")
        return str(output_path)
    
    def _write_streaming_coco(self, detections: List[DetectionResult], output_path: Path):
        """Write COCO format in streaming mode."""
        # First pass: collect metadata
        roi_templates = {}
        frame_info = {}
        
        self.logger.info("Collecting metadata for streaming COCO export...")
        
        for detection in detections[:1000]:  # Sample for metadata
            roi_id = detection.matching_session.roi_template.id
            if roi_id not in roi_templates:
                roi_templates[roi_id] = detection.matching_session.roi_template
            
            frame_num = detection.frame_number
            if frame_num not in frame_info:
                img_width, img_height = self.get_image_dimensions(frame_num)
                frame_info[frame_num] = {
                    'width': img_width,
                    'height': img_height,
                    'filename': f"frame_{frame_num:06d}.jpg"
                }
        
        # Write COCO structure using streaming JSON writer
        with open(output_path, 'w') as f:
            self._stream_write_coco_json(f, detections, roi_templates, frame_info)
    
    def _stream_write_coco_json(
        self, 
        file_obj: IO, 
        detections: List[DetectionResult],
        roi_templates: Dict[int, Any],
        frame_info: Dict[int, Dict[str, Any]]
    ):
        """Stream write COCO JSON to minimize memory usage."""
        
        # Write opening and info section
        file_obj.write('{\n')
        file_obj.write('  "info": {\n')
        file_obj.write(f'    "description": "CVAT Calibrix Streaming Export - Task {self.task.name}",\n')
        file_obj.write('    "url": "https://cvat.ai",\n')
        file_obj.write('    "version": "1.0",\n')
        file_obj.write(f'    "year": {time.localtime().tm_year},\n')
        file_obj.write('    "contributor": "Calibrix CVAT",\n')
        file_obj.write(f'    "date_created": "{time.strftime("%Y-%m-%dT%H:%M:%S")}"\n')
        file_obj.write('  },\n')
        file_obj.write('  "licenses": [],\n')
        
        # Write categories
        file_obj.write('  "categories": [\n')
        category_map = {}
        for idx, (roi_id, roi_template) in enumerate(roi_templates.items()):
            category_id = idx + 1
            category_map[roi_id] = category_id
            
            file_obj.write('    {\n')
            file_obj.write(f'      "id": {category_id},\n')
            file_obj.write(f'      "name": "{roi_template.name}",\n')
            file_obj.write('      "supercategory": "detection"\n')
            file_obj.write('    }')
            
            if idx < len(roi_templates) - 1:
                file_obj.write(',')
            file_obj.write('\n')
        
        file_obj.write('  ],\n')
        
        # Write images
        file_obj.write('  "images": [\n')
        sorted_frames = sorted(frame_info.keys())
        for idx, frame_num in enumerate(sorted_frames):
            frame_data = frame_info[frame_num]
            
            file_obj.write('    {\n')
            file_obj.write(f'      "id": {frame_num},\n')
            file_obj.write(f'      "width": {frame_data["width"]},\n')
            file_obj.write(f'      "height": {frame_data["height"]},\n')
            file_obj.write(f'      "file_name": "{frame_data["filename"]}",\n')
            file_obj.write(f'      "frame_number": {frame_num}\n')
            file_obj.write('    }')
            
            if idx < len(sorted_frames) - 1:
                file_obj.write(',')
            file_obj.write('\n')
        
        file_obj.write('  ],\n')
        
        # Stream write annotations
        file_obj.write('  "annotations": [\n')
        
        annotation_id = 1
        first_annotation = True
        
        # Process detections in batches
        batch_size = self.batch_size
        total_detections = len(detections)
        
        for i in range(0, total_detections, batch_size):
            batch = detections[i:i + batch_size]
            
            for detection in batch:
                if not first_annotation:
                    file_obj.write(',\n')
                first_annotation = False
                
                coords = detection.coordinates
                bbox = [coords['x'], coords['y'], coords['width'], coords['height']]
                area = coords['width'] * coords['height']
                roi_id = detection.matching_session.roi_template.id
                category_id = category_map[roi_id]
                
                file_obj.write('    {\n')
                file_obj.write(f'      "id": {annotation_id},\n')
                file_obj.write(f'      "image_id": {detection.frame_number},\n')
                file_obj.write(f'      "category_id": {category_id},\n')
                file_obj.write(f'      "bbox": {json.dumps(bbox)},\n')
                file_obj.write(f'      "area": {area},\n')
                file_obj.write('      "iscrowd": 0,\n')
                file_obj.write(f'      "confidence_score": {detection.confidence_score},\n')
                file_obj.write(f'      "is_confirmed": {str(detection.is_confirmed).lower()}\n')
                file_obj.write('    }')
                
                annotation_id += 1
            
            # Progress logging
            progress = min((i + batch_size) / total_detections * 100, 100)
            self.logger.debug(f"Streaming COCO: {progress:.1f}% complete")
        
        file_obj.write('\n  ]\n')
        file_obj.write('}\n')


class StreamingYOLOExporter(BaseExporter, StreamingExportMixin):
    """YOLO format exporter with streaming support."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to YOLO format using streaming."""
        export_dir = self.output_dir / f"yolo_streaming_export_{int(time.time())}"
        export_dir.mkdir(exist_ok=True)
        
        with self.memory_monitor():
            self._write_streaming_yolo(detections, export_dir)
        
        # Create archive if requested
        if self.config.compression_format != 'none':
            archive_path = str(export_dir) + ('.zip' if self.config.compression_format == 'zip' else '.tar.gz')
            self.create_compressed_archive(str(export_dir), archive_path)
            
            # Cleanup uncompressed directory
            import shutil
            shutil.rmtree(export_dir)
            result_path = archive_path
        else:
            result_path = str(export_dir)
        
        self.logger.info(f"Streaming YOLO export completed: {result_path}")
        return result_path
    
    def _write_streaming_yolo(self, detections: List[DetectionResult], export_dir: Path):
        """Write YOLO format in streaming mode."""
        # Create directory structure
        images_dir = export_dir / "images"
        labels_dir = export_dir / "labels"
        images_dir.mkdir(exist_ok=True)
        labels_dir.mkdir(exist_ok=True)
        
        # Collect ROI templates for class mapping
        roi_templates = list(set(d.matching_session.roi_template for d in detections[:1000]))
        roi_templates.sort(key=lambda x: x.id)
        class_map = {roi_template.id: idx for idx, roi_template in enumerate(roi_templates)}
        class_names = [roi_template.name for roi_template in roi_templates]
        
        # Group detections by frame for streaming processing
        current_frame = None
        current_frame_detections = []
        processed_frames = 0
        
        # Sort detections by frame for efficient processing
        sorted_detections = sorted(detections, key=lambda d: d.frame_number)
        
        for detection in sorted_detections:
            frame_number = detection.frame_number
            
            if current_frame != frame_number:
                # Process previous frame if exists
                if current_frame is not None and current_frame_detections:
                    self._write_frame_labels(
                        current_frame, 
                        current_frame_detections, 
                        labels_dir, 
                        class_map
                    )
                    processed_frames += 1
                    
                    if processed_frames % 100 == 0:
                        self.logger.debug(f"Processed {processed_frames} frames")
                
                # Start new frame
                current_frame = frame_number
                current_frame_detections = []
            
            current_frame_detections.append(detection)
        
        # Process final frame
        if current_frame is not None and current_frame_detections:
            self._write_frame_labels(current_frame, current_frame_detections, labels_dir, class_map)
            processed_frames += 1
        
        # Write data.yaml
        data_yaml = {
            'nc': len(class_names),
            'names': class_names,
            'path': str(export_dir),
            'train': 'images',
            'val': 'images',
            'test': 'images'
        }
        
        with open(export_dir / "data.yaml", 'w') as f:
            yaml.dump(data_yaml, f, default_flow_style=False)
        
        self.logger.info(f"Processed {processed_frames} frames for YOLO export")
    
    def _write_frame_labels(
        self, 
        frame_number: int, 
        frame_detections: List[DetectionResult], 
        labels_dir: Path, 
        class_map: Dict[int, int]
    ):
        """Write label file for a single frame."""
        label_file = labels_dir / f"frame_{frame_number:06d}.txt"
        
        # Get image dimensions (cached for efficiency)
        img_width, img_height = self.get_image_dimensions(frame_number)
        
        with open(label_file, 'w') as f:
            for detection in frame_detections:
                coords = detection.coordinates
                roi_template_id = detection.matching_session.roi_template.id
                class_id = class_map[roi_template_id]
                
                # Convert to YOLO format (normalized center coordinates)
                center_x = (coords['x'] + coords['width'] / 2) / img_width
                center_y = (coords['y'] + coords['height'] / 2) / img_height
                width = coords['width'] / img_width
                height = coords['height'] / img_height
                
                # Ensure values are within [0, 1] range
                center_x = max(0, min(1, center_x))
                center_y = max(0, min(1, center_y))
                width = max(0, min(1, width))
                height = max(0, min(1, height))
                
                f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}\n")


class StreamingCSVExporter(BaseExporter, StreamingExportMixin):
    """CSV format exporter with streaming support."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to CSV format using streaming."""
        output_path = self.output_dir / f"csv_streaming_export_{int(time.time())}.csv"
        
        with self.memory_monitor():
            self._write_streaming_csv(detections, output_path)
        
        self.logger.info(f"Streaming CSV export completed: {output_path}")
        return str(output_path)
    
    def _write_streaming_csv(self, detections: List[DetectionResult], output_path: Path):
        """Write CSV format in streaming mode."""
        import csv
        
        fieldnames = [
            'detection_id', 'frame_number', 'confidence_score', 'is_confirmed',
            'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height',
            'roi_template_id', 'roi_template_name', 'roi_template_algorithm',
            'matching_session_id', 'matching_algorithm', 'matching_threshold',
            'session_status', 'task_id', 'task_name', 'created_at'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Process in batches
            batch_size = self.batch_size
            total_detections = len(detections)
            
            for i in range(0, total_detections, batch_size):
                batch = detections[i:i + batch_size]
                rows = []
                
                for detection in batch:
                    row = {
                        'detection_id': detection.id,
                        'frame_number': detection.frame_number,
                        'confidence_score': detection.confidence_score,
                        'is_confirmed': detection.is_confirmed,
                        'bbox_x': detection.coordinates['x'],
                        'bbox_y': detection.coordinates['y'],
                        'bbox_width': detection.coordinates['width'],
                        'bbox_height': detection.coordinates['height'],
                        'roi_template_id': detection.matching_session.roi_template.id,
                        'roi_template_name': detection.matching_session.roi_template.name,
                        'roi_template_algorithm': detection.matching_session.roi_template.feature_descriptor.get('algorithm', ''),
                        'matching_session_id': detection.matching_session.id,
                        'matching_algorithm': detection.matching_session.algorithm_type,
                        'matching_threshold': detection.matching_session.threshold,
                        'session_status': detection.matching_session.status,
                        'task_id': detection.matching_session.task.id,
                        'task_name': detection.matching_session.task.name,
                        'created_at': detection.created_at.isoformat()
                    }
                    rows.append(row)
                
                writer.writerows(rows)
                
                # Progress logging
                progress = min((i + batch_size) / total_detections * 100, 100)
                if i % (batch_size * 10) == 0:  # Log every 1000 records
                    self.logger.debug(f"Streaming CSV: {progress:.1f}% complete")


class StreamingGroundTruthExportService(GroundTruthExportService):
    """Enhanced export service with streaming support for large datasets."""
    
    # Override exporter classes to use streaming versions
    EXPORTER_CLASSES = {
        'coco': StreamingCOCOExporter,
        'yolo': StreamingYOLOExporter,
        'pascal_voc': BaseExporter,  # Use base for Pascal VOC (typically smaller)
        'cvat_xml': BaseExporter,    # Use base for CVAT XML (typically smaller)
        'csv': StreamingCSVExporter
    }
    
    def get_detection_queryset_streaming(
        self,
        confirmed_only: bool = True,
        min_confidence: Optional[float] = None,
        roi_template_id: Optional[int] = None,
        batch_size: int = 1000
    ) -> Generator[List[DetectionResult], None, None]:
        """Get detection queryset in streaming batches."""
        
        queryset = DetectionResult.objects.select_related(
            'matching_session',
            'matching_session__roi_template',
            'matching_session__task'
        ).filter(
            matching_session__task_id=self.task_id
        ).order_by('frame_number', 'id')
        
        # Apply filters
        if confirmed_only:
            queryset = queryset.filter(is_confirmed=True)
        
        if min_confidence is not None:
            queryset = queryset.filter(confidence_score__gte=min_confidence)
        
        if roi_template_id:
            queryset = queryset.filter(matching_session__roi_template_id=roi_template_id)
        
        # Stream in batches
        total_count = queryset.count()
        processed = 0
        
        self.logger.info(f"Starting streaming query of {total_count} detections")
        
        while processed < total_count:
            batch = list(queryset[processed:processed + batch_size])
            
            if not batch:
                break
            
            yield batch
            processed += len(batch)
            
            self.logger.debug(f"Streamed {processed}/{total_count} detections")
    
    def export_streaming(self, config: ExportConfig) -> Dict[str, Any]:
        """Export with streaming support for large datasets."""
        start_time = time.time()
        
        try:
            # Enable streaming mode
            config.streaming_export = True
            
            # Get total count first
            all_detections = self.get_detection_queryset(
                confirmed_only=config.confirmed_only,
                min_confidence=config.min_confidence,
                roi_template_id=config.roi_template_id
            )
            
            total_count = len(all_detections)
            
            if total_count == 0:
                return {
                    'status': 'completed',
                    'total_detections': 0,
                    'message': 'No detections found matching the specified criteria',
                    'duration_seconds': time.time() - start_time
                }
            
            self.logger.info(f"Starting streaming export of {total_count} detections")
            
            # Use streaming export for large datasets
            if total_count > 10000:
                export_path = self._export_with_streaming(all_detections, config)
            else:
                # Use regular export for smaller datasets
                export_path = self._export_with_format(all_detections, config)
            
            # Calculate file size
            if os.path.isfile(export_path):
                file_size = os.path.getsize(export_path)
            else:
                file_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(export_path)
                    for filename in filenames
                )
            
            duration = time.time() - start_time
            
            result = {
                'status': 'completed',
                'export_path': export_path,
                'total_detections': total_count,
                'file_size_bytes': file_size,
                'duration_seconds': duration,
                'export_format': config.export_format,
                'streaming_used': total_count > 10000,
                'config': config.to_dict(),
                'timestamp': time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            
            self.logger.info(f"Streaming export completed: {total_count} detections in {duration:.1f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Streaming export failed after {duration:.1f}s: {e}")
            raise
    
    def _export_with_streaming(self, detections: List[DetectionResult], config: ExportConfig) -> str:
        """Export detections using streaming approach."""
        if config.export_format not in self.EXPORTER_CLASSES:
            raise ValueError(f"Unsupported export format: {config.export_format}")
        
        # Create output directory
        if config.output_directory:
            output_dir = Path(config.output_directory)
        else:
            output_dir = self.base_export_dir / f"streaming_task_{self.task_id}_{int(time.time())}"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create and use streaming exporter
        exporter_class = self.EXPORTER_CLASSES[config.export_format]
        exporter = exporter_class(self.task_id, output_dir, config)
        
        return exporter.export(detections)
    
    def estimate_memory_usage(self, detection_count: int, export_format: str) -> Dict[str, float]:
        """Estimate memory usage for different export scenarios."""
        
        # Base memory per detection (in KB)
        base_memory_per_detection = {
            'coco': 2.0,      # JSON structure overhead
            'yolo': 0.5,      # Simple text format
            'pascal_voc': 3.0, # XML overhead
            'cvat_xml': 3.5,   # More complex XML
            'csv': 1.0         # Simple tabular format
        }
        
        base_kb = base_memory_per_detection.get(export_format, 1.5)
        
        # Calculate estimates
        estimated_memory_mb = (detection_count * base_kb) / 1024
        
        # Add overhead for processing
        processing_overhead = estimated_memory_mb * 0.5
        total_estimated_mb = estimated_memory_mb + processing_overhead
        
        # Streaming memory (much lower)
        streaming_memory_mb = min(100, estimated_memory_mb * 0.1)  # Max 100MB or 10% of total
        
        return {
            'detection_count': detection_count,
            'base_memory_mb': estimated_memory_mb,
            'processing_overhead_mb': processing_overhead,
            'total_estimated_mb': total_estimated_mb,
            'streaming_memory_mb': streaming_memory_mb,
            'recommend_streaming': total_estimated_mb > 500,  # Recommend streaming for >500MB
            'export_format': export_format
        }


# Utility functions for memory optimization
def optimize_queryset_for_streaming(queryset: QuerySet) -> QuerySet:
    """Optimize queryset for streaming operations."""
    return queryset.select_related(
        'matching_session__roi_template',
        'matching_session__task'
    ).only(
        'id', 'frame_number', 'coordinates', 'confidence_score', 'is_confirmed', 'created_at',
        'matching_session__id', 'matching_session__algorithm_type', 'matching_session__threshold',
        'matching_session__status', 'matching_session__task__id', 'matching_session__task__name',
        'matching_session__roi_template__id', 'matching_session__roi_template__name',
        'matching_session__roi_template__feature_descriptor'
    ).iterator(chunk_size=1000)


@contextmanager
def memory_profiler():
    """Context manager for memory profiling."""
    try:
        import psutil
        import tracemalloc
        
        # Start memory tracking
        tracemalloc.start()
        process = psutil.Process()
        start_memory = process.memory_info().rss
        
        yield
        
        # Get memory statistics
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        end_memory = process.memory_info().rss
        
        logger.info(f"Memory usage: {start_memory / 1024 / 1024:.1f}MB -> {end_memory / 1024 / 1024:.1f}MB")
        logger.info(f"Peak traced memory: {peak / 1024 / 1024:.1f}MB")
        
    except ImportError:
        logger.warning("psutil not available for memory profiling")
        yield