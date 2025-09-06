# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import csv
import json
import logging
import os
import shutil
import tarfile
import time
import xml.etree.ElementTree as ET
import yaml
import zipfile
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union
from uuid import uuid4

import numpy as np
from django.conf import settings
from django.db import models
from django.db.models import Q, Avg, Min, Max, Count
from django.utils import timezone
from PIL import Image

from ..models import ROITemplate, MatchingSession, DetectionResult
from cvat.apps.engine.models import Task, Data

logger = logging.getLogger(__name__)


class ExportConfig:
    """Configuration class for export operations."""
    
    SUPPORTED_FORMATS = ['coco', 'yolo', 'pascal_voc', 'cvat_xml', 'csv']
    COMPRESSION_FORMATS = ['zip', 'tar.gz', 'none']
    
    def __init__(
        self,
        export_format: str,
        include_images: bool = False,
        confirmed_only: bool = True,
        min_confidence: Optional[float] = None,
        roi_template_id: Optional[int] = None,
        dataset_split: Optional[Dict[str, float]] = None,
        compression_format: str = 'zip',
        output_directory: Optional[str] = None,
        streaming_export: bool = False,
        batch_size: int = 100,
        include_metadata: bool = True,
        normalize_coordinates: bool = True
    ):
        self.export_format = export_format
        self.include_images = include_images
        self.confirmed_only = confirmed_only
        self.min_confidence = min_confidence
        self.roi_template_id = roi_template_id
        self.dataset_split = dataset_split or {}
        self.compression_format = compression_format
        self.output_directory = output_directory
        self.streaming_export = streaming_export
        self.batch_size = batch_size
        self.include_metadata = include_metadata
        self.normalize_coordinates = normalize_coordinates
        
        self.validate()
    
    def validate(self):
        """Validate the export configuration."""
        if self.export_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported export format: {self.export_format}")
        
        if self.compression_format not in self.COMPRESSION_FORMATS:
            raise ValueError(f"Unsupported compression format: {self.compression_format}")
        
        if self.min_confidence is not None and not (0 <= self.min_confidence <= 1):
            raise ValueError("min_confidence must be between 0 and 1")
        
        if self.dataset_split:
            total = sum(self.dataset_split.values())
            if not (0.99 <= total <= 1.01):  # Allow small floating point errors
                raise ValueError("Dataset split ratios must sum to 1.0")
        
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
    
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        try:
            self.validate()
            return True
        except ValueError:
            return False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'export_format': self.export_format,
            'include_images': self.include_images,
            'confirmed_only': self.confirmed_only,
            'min_confidence': self.min_confidence,
            'roi_template_id': self.roi_template_id,
            'dataset_split': self.dataset_split,
            'compression_format': self.compression_format,
            'output_directory': self.output_directory,
            'streaming_export': self.streaming_export,
            'batch_size': self.batch_size,
            'include_metadata': self.include_metadata,
            'normalize_coordinates': self.normalize_coordinates
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ExportConfig':
        """Create configuration from dictionary."""
        return cls(**config_dict)


class DatasetSplitter:
    """Handles splitting dataset into train/validation/test sets."""
    
    def __init__(self, train_ratio: float = 0.7, val_ratio: float = 0.2, test_ratio: float = 0.1):
        if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
            raise ValueError("Split ratios must sum to 1.0")
        
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio
    
    def split_detections(self, detections: List[DetectionResult]) -> Dict[str, List[DetectionResult]]:
        """Split detections into train/val/test sets."""
        # Group by frame to ensure consistent splits
        frame_groups = defaultdict(list)
        for detection in detections:
            frame_groups[detection.frame_number].append(detection)
        
        # Sort frames for consistent splitting
        sorted_frames = sorted(frame_groups.keys())
        
        # Calculate split indices
        total_frames = len(sorted_frames)
        train_end = int(total_frames * self.train_ratio)
        val_end = train_end + int(total_frames * self.val_ratio)
        
        # Split frames
        train_frames = sorted_frames[:train_end]
        val_frames = sorted_frames[train_end:val_end]
        test_frames = sorted_frames[val_end:]
        
        # Collect detections for each split
        splits = {
            'train': [],
            'val': [],
            'test': []
        }
        
        for frame in train_frames:
            splits['train'].extend(frame_groups[frame])
        
        for frame in val_frames:
            splits['val'].extend(frame_groups[frame])
        
        for frame in test_frames:
            splits['test'].extend(frame_groups[frame])
        
        return splits


class QualityControlValidator:
    """Validates detection data quality and performs quality control checks."""
    
    def validate_coordinates(self, coordinates: Dict[str, Any]) -> bool:
        """Validate bounding box coordinates."""
        required_fields = {'x', 'y', 'width', 'height'}
        
        # Check all required fields are present
        if not all(field in coordinates for field in required_fields):
            return False
        
        # Check all values are numeric
        try:
            x, y, width, height = (
                float(coordinates['x']),
                float(coordinates['y']),
                float(coordinates['width']),
                float(coordinates['height'])
            )
        except (ValueError, TypeError):
            return False
        
        # Check for valid dimensions
        if width <= 0 or height <= 0:
            return False
        
        # Check for reasonable coordinates (not negative)
        if x < 0 or y < 0:
            return False
        
        return True
    
    def validate_confidence_score(self, score: Optional[float]) -> bool:
        """Validate confidence score."""
        if score is None:
            return False
        
        try:
            float_score = float(score)
            return 0.0 <= float_score <= 1.0
        except (ValueError, TypeError):
            return False
    
    def find_duplicate_detections(
        self,
        detections: List[DetectionResult],
        tolerance: float = 0.1
    ) -> List[Tuple[DetectionResult, DetectionResult]]:
        """Find duplicate detections within the same frame."""
        duplicates = []
        
        # Group by frame
        frame_groups = defaultdict(list)
        for detection in detections:
            frame_groups[detection.frame_number].append(detection)
        
        # Check for duplicates within each frame
        for frame_number, frame_detections in frame_groups.items():
            for i, det1 in enumerate(frame_detections):
                for j, det2 in enumerate(frame_detections[i + 1:], i + 1):
                    if self._are_detections_duplicate(det1, det2, tolerance):
                        duplicates.append((det1, det2))
        
        return duplicates
    
    def _are_detections_duplicate(
        self,
        det1: DetectionResult,
        det2: DetectionResult,
        tolerance: float
    ) -> bool:
        """Check if two detections are duplicates based on IoU threshold."""
        coords1 = det1.coordinates
        coords2 = det2.coordinates
        
        # Calculate IoU
        iou = self._calculate_iou(coords1, coords2)
        return iou > (1.0 - tolerance)
    
    def _calculate_iou(self, coords1: Dict[str, Any], coords2: Dict[str, Any]) -> float:
        """Calculate Intersection over Union (IoU) of two bounding boxes."""
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
    
    def generate_quality_report(
        self,
        detections: List[DetectionResult]
    ) -> Dict[str, Any]:
        """Generate a comprehensive quality control report."""
        report = {
            'total_detections': len(detections),
            'valid_detections': 0,
            'invalid_coordinates': [],
            'invalid_confidence_scores': [],
            'duplicate_detections': [],
            'confidence_distribution': {},
            'frame_coverage': {},
            'roi_template_distribution': {}
        }
        
        valid_count = 0
        confidence_scores = []
        frame_numbers = set()
        roi_template_counts = defaultdict(int)
        
        for detection in detections:
            # Validate coordinates
            if not self.validate_coordinates(detection.coordinates):
                report['invalid_coordinates'].append(detection.id)
            else:
                valid_count += 1
            
            # Validate confidence score
            if not self.validate_confidence_score(detection.confidence_score):
                report['invalid_confidence_scores'].append(detection.id)
            else:
                confidence_scores.append(detection.confidence_score)
            
            frame_numbers.add(detection.frame_number)
            roi_template_counts[detection.matching_session.roi_template.name] += 1
        
        report['valid_detections'] = valid_count
        
        # Find duplicates
        report['duplicate_detections'] = self.find_duplicate_detections(detections)
        
        # Confidence distribution
        if confidence_scores:
            report['confidence_distribution'] = {
                'min': min(confidence_scores),
                'max': max(confidence_scores),
                'mean': np.mean(confidence_scores),
                'std': np.std(confidence_scores),
                'quartiles': np.percentile(confidence_scores, [25, 50, 75]).tolist()
            }
        
        # Frame coverage
        report['frame_coverage'] = {
            'total_frames_with_detections': len(frame_numbers),
            'min_frame': min(frame_numbers) if frame_numbers else None,
            'max_frame': max(frame_numbers) if frame_numbers else None
        }
        
        # ROI template distribution
        report['roi_template_distribution'] = dict(roi_template_counts)
        
        return report


class BaseExporter(ABC):
    """Base class for all export format implementations."""
    
    def __init__(self, task_id: int, output_dir: str, config: ExportConfig):
        self.task_id = task_id
        self.output_dir = Path(output_dir)
        self.config = config
        self.task = Task.objects.get(id=task_id)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to the specified format."""
        pass
    
    def get_image_dimensions(self, frame_number: int) -> Tuple[int, int]:
        """Get image dimensions for a specific frame."""
        try:
            # Try to get dimensions from task data
            data = self.task.data
            frame_info = data.get_frame_info(frame_number)
            return frame_info['width'], frame_info['height']
        except Exception:
            # Default fallback dimensions
            return 1920, 1080
    
    def normalize_coordinates(
        self,
        coords: Dict[str, Any],
        img_width: int,
        img_height: int
    ) -> Dict[str, float]:
        """Normalize coordinates to [0, 1] range."""
        return {
            'x': coords['x'] / img_width,
            'y': coords['y'] / img_height,
            'width': coords['width'] / img_width,
            'height': coords['height'] / img_height
        }
    
    def create_compressed_archive(self, source_dir: str, archive_path: str) -> str:
        """Create compressed archive of the export directory."""
        if self.config.compression_format == 'zip':
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(source_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arc_name = os.path.relpath(file_path, source_dir)
                        zipf.write(file_path, arc_name)
        elif self.config.compression_format == 'tar.gz':
            with tarfile.open(archive_path, 'w:gz') as tarf:
                tarf.add(source_dir, arcname=os.path.basename(source_dir))
        
        return archive_path


class COCOExporter(BaseExporter):
    """COCO JSON format exporter."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to COCO JSON format."""
        output_path = self.output_dir / f"coco_export_{int(time.time())}.json"
        
        # Build COCO format structure
        coco_data = {
            "info": {
                "description": f"CVAT Calibrix Matching Export - Task {self.task.name}",
                "url": "https://cvat.ai",
                "version": "1.0",
                "year": datetime.now().year,
                "contributor": "Calibrix CVAT",
                "date_created": datetime.now().isoformat()
            },
            "licenses": [],
            "images": [],
            "annotations": [],
            "categories": []
        }
        
        # Create categories from ROI templates
        roi_templates = set(d.matching_session.roi_template for d in detections)
        category_map = {}
        for idx, roi_template in enumerate(roi_templates):
            category_id = idx + 1
            category_map[roi_template.id] = category_id
            coco_data["categories"].append({
                "id": category_id,
                "name": roi_template.name,
                "supercategory": "detection"
            })
        
        # Group detections by frame
        frame_detections = defaultdict(list)
        for detection in detections:
            frame_detections[detection.frame_number].append(detection)
        
        # Create images and annotations
        image_id = 1
        annotation_id = 1
        
        for frame_number in sorted(frame_detections.keys()):
            frame_dets = frame_detections[frame_number]
            
            # Get image dimensions
            img_width, img_height = self.get_image_dimensions(frame_number)
            
            # Create image entry
            image_entry = {
                "id": image_id,
                "width": img_width,
                "height": img_height,
                "file_name": f"frame_{frame_number:06d}.jpg",
                "frame_number": frame_number
            }
            coco_data["images"].append(image_entry)
            
            # Create annotations for this frame
            for detection in frame_dets:
                coords = detection.coordinates
                bbox = [coords['x'], coords['y'], coords['width'], coords['height']]
                area = coords['width'] * coords['height']
                
                category_id = category_map[detection.matching_session.roi_template.id]
                
                annotation = {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": category_id,
                    "bbox": bbox,
                    "area": area,
                    "iscrowd": 0,
                    "confidence_score": detection.confidence_score,
                    "is_confirmed": detection.is_confirmed
                }
                coco_data["annotations"].append(annotation)
                annotation_id += 1
            
            image_id += 1
        
        # Write COCO JSON file
        with open(output_path, 'w') as f:
            json.dump(coco_data, f, indent=2)
        
        self.logger.info(f"COCO export completed: {len(detections)} detections -> {output_path}")
        return str(output_path)


class YOLOExporter(BaseExporter):
    """YOLO format exporter."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to YOLO format."""
        export_dir = self.output_dir / f"yolo_export_{int(time.time())}"
        export_dir.mkdir(exist_ok=True)
        
        # Create YOLO directory structure
        images_dir = export_dir / "images"
        labels_dir = export_dir / "labels"
        images_dir.mkdir(exist_ok=True)
        labels_dir.mkdir(exist_ok=True)
        
        # Create class mapping from ROI templates
        roi_templates = list(set(d.matching_session.roi_template for d in detections))
        roi_templates.sort(key=lambda x: x.id)
        class_map = {roi_template.id: idx for idx, roi_template in enumerate(roi_templates)}
        class_names = [roi_template.name for roi_template in roi_templates]
        
        # Group detections by frame
        frame_detections = defaultdict(list)
        for detection in detections:
            frame_detections[detection.frame_number].append(detection)
        
        # Create label files
        for frame_number in sorted(frame_detections.keys()):
            frame_dets = frame_detections[frame_number]
            
            # Get image dimensions for normalization
            img_width, img_height = self.get_image_dimensions(frame_number)
            
            # Create label file
            label_file = labels_dir / f"frame_{frame_number:06d}.txt"
            with open(label_file, 'w') as f:
                for detection in frame_dets:
                    coords = detection.coordinates
                    roi_template_id = detection.matching_session.roi_template.id
                    class_id = class_map[roi_template_id]
                    
                    # Convert to YOLO format (normalized center coordinates)
                    center_x = (coords['x'] + coords['width'] / 2) / img_width
                    center_y = (coords['y'] + coords['height'] / 2) / img_height
                    width = coords['width'] / img_width
                    height = coords['height'] / img_height
                    
                    # Write YOLO annotation line
                    f.write(f"{class_id} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}\n")
        
        # Create data.yaml file
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
        
        # Create archive
        if self.config.compression_format != 'none':
            archive_path = str(export_dir) + ('.zip' if self.config.compression_format == 'zip' else '.tar.gz')
            self.create_compressed_archive(str(export_dir), archive_path)
            shutil.rmtree(export_dir)
            result_path = archive_path
        else:
            result_path = str(export_dir)
        
        self.logger.info(f"YOLO export completed: {len(detections)} detections -> {result_path}")
        return result_path


class PascalVOCExporter(BaseExporter):
    """Pascal VOC XML format exporter."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to Pascal VOC XML format."""
        export_dir = self.output_dir / f"pascal_voc_export_{int(time.time())}"
        export_dir.mkdir(exist_ok=True)
        
        # Create Pascal VOC directory structure
        annotations_dir = export_dir / "Annotations"
        imagesets_dir = export_dir / "ImageSets" / "Main"
        annotations_dir.mkdir(exist_ok=True)
        imagesets_dir.mkdir(parents=True, exist_ok=True)
        
        # Group detections by frame
        frame_detections = defaultdict(list)
        for detection in detections:
            frame_detections[detection.frame_number].append(detection)
        
        # Create XML files and collect filenames
        filenames = []
        
        for frame_number in sorted(frame_detections.keys()):
            frame_dets = frame_detections[frame_number]
            filename = f"frame_{frame_number:06d}"
            filenames.append(filename)
            
            # Get image dimensions
            img_width, img_height = self.get_image_dimensions(frame_number)
            
            # Create XML annotation
            annotation = ET.Element("annotation")
            
            # Add filename
            ET.SubElement(annotation, "filename").text = f"{filename}.jpg"
            
            # Add source
            source = ET.SubElement(annotation, "source")
            ET.SubElement(source, "database").text = "CVAT Calibrix"
            
            # Add size
            size = ET.SubElement(annotation, "size")
            ET.SubElement(size, "width").text = str(img_width)
            ET.SubElement(size, "height").text = str(img_height)
            ET.SubElement(size, "depth").text = "3"
            
            # Add segmented
            ET.SubElement(annotation, "segmented").text = "0"
            
            # Add objects
            for detection in frame_dets:
                obj = ET.SubElement(annotation, "object")
                ET.SubElement(obj, "name").text = detection.matching_session.roi_template.name
                ET.SubElement(obj, "pose").text = "Unspecified"
                ET.SubElement(obj, "truncated").text = "0"
                ET.SubElement(obj, "difficult").text = "0"
                
                # Add confidence as attribute
                confidence = ET.SubElement(obj, "confidence")
                confidence.text = str(detection.confidence_score)
                
                # Add confirmed status
                confirmed = ET.SubElement(obj, "confirmed")
                confirmed.text = str(detection.is_confirmed).lower()
                
                # Add bounding box
                bndbox = ET.SubElement(obj, "bndbox")
                coords = detection.coordinates
                ET.SubElement(bndbox, "xmin").text = str(int(coords['x']))
                ET.SubElement(bndbox, "ymin").text = str(int(coords['y']))
                ET.SubElement(bndbox, "xmax").text = str(int(coords['x'] + coords['width']))
                ET.SubElement(bndbox, "ymax").text = str(int(coords['y'] + coords['height']))
            
            # Write XML file
            xml_file = annotations_dir / f"{filename}.xml"
            tree = ET.ElementTree(annotation)
            tree.write(xml_file, encoding='utf-8', xml_declaration=True)
        
        # Create ImageSets files
        with open(imagesets_dir / "trainval.txt", 'w') as f:
            f.write('\n'.join(filenames))
        
        with open(imagesets_dir / "test.txt", 'w') as f:
            f.write('\n'.join(filenames))
        
        # Create archive
        if self.config.compression_format != 'none':
            archive_path = str(export_dir) + ('.zip' if self.config.compression_format == 'zip' else '.tar.gz')
            self.create_compressed_archive(str(export_dir), archive_path)
            shutil.rmtree(export_dir)
            result_path = archive_path
        else:
            result_path = str(export_dir)
        
        self.logger.info(f"Pascal VOC export completed: {len(detections)} detections -> {result_path}")
        return result_path


class CVATXMLExporter(BaseExporter):
    """CVAT XML format exporter."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to CVAT XML format."""
        output_path = self.output_dir / f"cvat_export_{int(time.time())}.xml"
        
        # Create root element
        annotations = ET.Element("annotations")
        
        # Add version
        version = ET.SubElement(annotations, "version")
        version.text = "1.1"
        
        # Add meta information
        meta = ET.SubElement(annotations, "meta")
        
        task_elem = ET.SubElement(meta, "task")
        ET.SubElement(task_elem, "id").text = str(self.task.id)
        ET.SubElement(task_elem, "name").text = self.task.name
        ET.SubElement(task_elem, "size").text = str(self.task.data.size)
        
        # Add labels
        labels_elem = ET.SubElement(meta, "labels")
        roi_templates = set(d.matching_session.roi_template for d in detections)
        for roi_template in roi_templates:
            label_elem = ET.SubElement(labels_elem, "label")
            ET.SubElement(label_elem, "name").text = roi_template.name
            ET.SubElement(label_elem, "color").text = "#ff0000"
        
        # Group detections by frame
        frame_detections = defaultdict(list)
        for detection in detections:
            frame_detections[detection.frame_number].append(detection)
        
        # Add images and annotations
        for frame_number in sorted(frame_detections.keys()):
            frame_dets = frame_detections[frame_number]
            
            image_elem = ET.SubElement(annotations, "image")
            image_elem.set("id", str(frame_number))
            image_elem.set("name", f"frame_{frame_number:06d}.jpg")
            
            # Get image dimensions
            img_width, img_height = self.get_image_dimensions(frame_number)
            image_elem.set("width", str(img_width))
            image_elem.set("height", str(img_height))
            
            # Add boxes
            for detection in frame_dets:
                box_elem = ET.SubElement(image_elem, "box")
                box_elem.set("label", detection.matching_session.roi_template.name)
                box_elem.set("source", "manual")
                box_elem.set("occluded", "0")
                
                coords = detection.coordinates
                box_elem.set("xtl", str(coords['x']))
                box_elem.set("ytl", str(coords['y']))
                box_elem.set("xbr", str(coords['x'] + coords['width']))
                box_elem.set("ybr", str(coords['y'] + coords['height']))
                
                # Add attributes
                confidence_attr = ET.SubElement(box_elem, "attribute")
                confidence_attr.set("name", "confidence")
                confidence_attr.text = str(detection.confidence_score)
                
                confirmed_attr = ET.SubElement(box_elem, "attribute")
                confirmed_attr.set("name", "confirmed")
                confirmed_attr.text = str(detection.is_confirmed)
        
        # Write XML file
        tree = ET.ElementTree(annotations)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        
        self.logger.info(f"CVAT XML export completed: {len(detections)} detections -> {output_path}")
        return str(output_path)


class CSVExporter(BaseExporter):
    """CSV format exporter."""
    
    def export(self, detections: List[DetectionResult]) -> str:
        """Export detections to CSV format."""
        output_path = self.output_dir / f"csv_export_{int(time.time())}.csv"
        
        # Define CSV columns
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
            
            for detection in detections:
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
                writer.writerow(row)
        
        self.logger.info(f"CSV export completed: {len(detections)} detections -> {output_path}")
        return str(output_path)


class ExportJob:
    """Handles background export job execution with progress tracking."""
    
    def __init__(self, task_id: int, config: ExportConfig, job_id: Optional[str] = None):
        self.task_id = task_id
        self.config = config
        self.job_id = job_id or str(uuid4())
        self.logger = logging.getLogger(f"{__name__}.ExportJob")
    
    def execute(self) -> Dict[str, Any]:
        """Execute the export job with progress tracking."""
        start_time = time.time()
        
        try:
            # Update job status
            self.update_progress(0, "Initializing export job")
            
            # Get detection data
            service = GroundTruthExportService(self.task_id)
            detections = service.get_detection_queryset(
                confirmed_only=self.config.confirmed_only,
                min_confidence=self.config.min_confidence,
                roi_template_id=self.config.roi_template_id
            )
            
            total_detections = len(detections)
            self.update_progress(20, f"Found {total_detections} detections")
            
            # Validate data quality if requested
            if hasattr(self.config, 'validate_quality') and self.config.validate_quality:
                validator = QualityControlValidator()
                quality_report = validator.generate_quality_report(detections)
                self.update_progress(30, "Quality validation completed")
            
            # Split dataset if requested
            if self.config.dataset_split:
                splitter = DatasetSplitter(**self.config.dataset_split)
                splits = splitter.split_detections(detections)
                self.update_progress(40, "Dataset splitting completed")
            else:
                splits = {'all': detections}
            
            # Export each split
            results = {}
            progress_step = 50 / len(splits)
            current_progress = 40
            
            for split_name, split_detections in splits.items():
                self.update_progress(
                    current_progress,
                    f"Exporting {split_name} split ({len(split_detections)} detections)"
                )
                
                # Create split-specific config
                split_config = ExportConfig.from_dict(self.config.to_dict())
                if len(splits) > 1:
                    split_output_dir = Path(self.config.output_directory) / split_name
                    split_output_dir.mkdir(exist_ok=True)
                    split_config.output_directory = str(split_output_dir)
                
                # Export split
                result_path = service._export_with_format(split_detections, split_config)
                results[split_name] = result_path
                
                current_progress += progress_step
                self.update_progress(current_progress, f"{split_name} split exported")
            
            self.update_progress(90, "Finalizing export")
            
            # Create final result
            duration = time.time() - start_time
            result = {
                'status': 'completed',
                'job_id': self.job_id,
                'task_id': self.task_id,
                'export_paths': results,
                'total_detections': total_detections,
                'duration_seconds': duration,
                'config': self.config.to_dict(),
                'timestamp': timezone.now().isoformat()
            }
            
            if hasattr(self.config, 'validate_quality') and self.config.validate_quality:
                result['quality_report'] = quality_report
            
            self.update_progress(100, "Export completed successfully")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            error_result = {
                'status': 'failed',
                'job_id': self.job_id,
                'task_id': self.task_id,
                'error': str(e),
                'duration_seconds': duration,
                'timestamp': timezone.now().isoformat()
            }
            
            self.update_progress(-1, f"Export failed: {str(e)}")
            self.logger.error(f"Export job {self.job_id} failed: {e}")
            return error_result
    
    def update_progress(self, percentage: int, message: str):
        """Update job progress (to be implemented with RQ/Redis)."""
        # This would integrate with RQ job progress tracking
        try:
            from rq import get_current_job
            job = get_current_job()
            if job:
                job.meta['progress'] = percentage
                job.meta['message'] = message
                job.save_meta()
        except ImportError:
            pass  # RQ not available
        
        self.logger.info(f"Job {self.job_id}: {percentage}% - {message}")


class GroundTruthExportService:
    """Main service class for ground truth export operations."""
    
    EXPORTER_CLASSES = {
        'coco': COCOExporter,
        'yolo': YOLOExporter,
        'pascal_voc': PascalVOCExporter,
        'cvat_xml': CVATXMLExporter,
        'csv': CSVExporter
    }
    
    def __init__(self, task_id: int):
        self.task_id = task_id
        self.task = Task.objects.get(id=task_id)
        self.logger = logging.getLogger(f"{__name__}.GroundTruthExportService")
        
        # Create export directory
        self.base_export_dir = Path(settings.EXPORT_CACHE_ROOT) / 'calibrix_ground_truth'
        self.base_export_dir.mkdir(parents=True, exist_ok=True)
    
    def get_supported_formats(self) -> List[str]:
        """Get list of supported export formats."""
        return list(self.EXPORTER_CLASSES.keys())
    
    def get_detection_queryset(
        self,
        confirmed_only: bool = True,
        min_confidence: Optional[float] = None,
        roi_template_id: Optional[int] = None
    ) -> List[DetectionResult]:
        """Get queryset of detection results for export."""
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
        
        return list(queryset)
    
    def export(self, config: ExportConfig) -> Dict[str, Any]:
        """Main export method."""
        start_time = time.time()
        
        try:
            # Get detections
            detections = self.get_detection_queryset(
                confirmed_only=config.confirmed_only,
                min_confidence=config.min_confidence,
                roi_template_id=config.roi_template_id
            )
            
            if not detections:
                return {
                    'status': 'completed',
                    'total_detections': 0,
                    'message': 'No detections found matching the specified criteria',
                    'duration_seconds': time.time() - start_time
                }
            
            # Export with specified format
            export_path = self._export_with_format(detections, config)
            
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
                'total_detections': len(detections),
                'file_size_bytes': file_size,
                'duration_seconds': duration,
                'export_format': config.export_format,
                'config': config.to_dict(),
                'timestamp': timezone.now().isoformat()
            }
            
            self.logger.info(f"Export completed: {len(detections)} detections in {duration:.1f}s")
            return result
            
        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Export failed after {duration:.1f}s: {e}")
            raise
    
    def _export_with_format(self, detections: List[DetectionResult], config: ExportConfig) -> str:
        """Export detections with the specified format."""
        if config.export_format not in self.EXPORTER_CLASSES:
            raise ValueError(f"Unsupported export format: {config.export_format}")
        
        # Create output directory
        if config.output_directory:
            output_dir = Path(config.output_directory)
        else:
            output_dir = self.base_export_dir / f"task_{self.task_id}_{int(time.time())}"
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create and use exporter
        exporter_class = self.EXPORTER_CLASSES[config.export_format]
        exporter = exporter_class(self.task_id, output_dir, config)
        
        return exporter.export(detections)
    
    def export_async(self, config: ExportConfig) -> str:
        """Start asynchronous export job."""
        try:
            from rq import Queue
            from django_rq import get_queue
            
            queue = get_queue('default')
            job = queue.enqueue(
                'cvat.apps.calibrix_matching.services.ground_truth_export.export_ground_truth_task',
                self.task_id,
                config.to_dict(),
                timeout='30m'
            )
            
            self.logger.info(f"Started async export job {job.id} for task {self.task_id}")
            return job.id
            
        except ImportError:
            # Fallback to synchronous export if RQ not available
            self.logger.warning("RQ not available, falling back to synchronous export")
            result = self.export(config)
            return result.get('export_path', '')
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about exportable detection data."""
        try:
            # Get all detection statistics
            all_detections = DetectionResult.objects.filter(
                matching_session__task_id=self.task_id
            )
            
            confirmed_detections = all_detections.filter(is_confirmed=True)
            
            # Get ROI template statistics
            roi_templates = ROITemplate.objects.filter(
                matching_sessions__task_id=self.task_id
            ).distinct()
            
            matching_sessions = MatchingSession.objects.filter(task_id=self.task_id)
            
            # Calculate confidence statistics
            confidence_stats = all_detections.aggregate(
                avg_confidence=Avg('confidence_score'),
                min_confidence=Min('confidence_score'),
                max_confidence=Max('confidence_score')
            )
            
            # Frame coverage statistics
            frame_stats = all_detections.aggregate(
                min_frame=Min('frame_number'),
                max_frame=Max('frame_number'),
                unique_frames=Count('frame_number', distinct=True)
            )
            
            # ROI template distribution
            roi_template_stats = list(
                all_detections.values('matching_session__roi_template__name')
                .annotate(detection_count=Count('id'))
                .order_by('-detection_count')
            )
            
            statistics = {
                'task_id': self.task_id,
                'task_name': self.task.name,
                'total_detections': all_detections.count(),
                'confirmed_detections': confirmed_detections.count(),
                'unconfirmed_detections': all_detections.filter(is_confirmed=False).count(),
                'roi_templates_count': roi_templates.count(),
                'matching_sessions_count': matching_sessions.count(),
                'completed_sessions_count': matching_sessions.filter(
                    status=MatchingSession.Status.COMPLETED
                ).count(),
                'confidence_statistics': confidence_stats,
                'frame_coverage': frame_stats,
                'roi_template_distribution': {
                    item['matching_session__roi_template__name']: item['detection_count']
                    for item in roi_template_stats
                },
                'supported_export_formats': self.get_supported_formats(),
                'last_updated': timezone.now().isoformat()
            }
            
            return statistics
            
        except Exception as e:
            self.logger.error(f"Error generating export statistics: {e}")
            raise


# RQ task functions for async processing
def export_ground_truth_task(task_id: int, config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """RQ task function for exporting ground truth data."""
    try:
        config = ExportConfig.from_dict(config_dict)
        job = ExportJob(task_id, config)
        return job.execute()
    except Exception as e:
        logger.error(f"Export job failed for task {task_id}: {e}")
        raise


def cleanup_old_exports(days_old: int = 7):
    """Clean up old export files."""
    try:
        export_dir = Path(settings.EXPORT_CACHE_ROOT) / 'calibrix_ground_truth'
        if not export_dir.exists():
            return
        
        cutoff_time = time.time() - (days_old * 24 * 60 * 60)
        deleted_count = 0
        
        for item in export_dir.iterdir():
            if item.is_file() or item.is_dir():
                item_mtime = item.stat().st_mtime
                if item_mtime < cutoff_time:
                    if item.is_file():
                        item.unlink()
                    else:
                        shutil.rmtree(item)
                    deleted_count += 1
                    logger.debug(f"Deleted old export: {item.name}")
        
        logger.info(f"Cleanup completed: deleted {deleted_count} old exports")
        
    except Exception as e:
        logger.error(f"Error during export cleanup: {e}")
        raise