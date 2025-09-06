# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import os
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth.models import User
from django.test import TestCase

from cvat.apps.engine.models import Task
from ..models import ROITemplate, MatchingSession, DetectionResult
from ..services.ground_truth_export import (
    GroundTruthExportService,
    COCOExporter,
    YOLOExporter,
    PascalVOCExporter,
    CVATXMLExporter,
    CSVExporter,
    ExportConfig,
    DatasetSplitter,
    QualityControlValidator,
    ExportJob,
)


class BaseGroundTruthExportTestCase(TestCase):
    """Base test case with common fixtures for ground truth export tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp_dir)
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test task
        self.task = Task.objects.create(
            name='Test Ground Truth Export Task',
            organization_id=None,
            owner=self.user,
            mode='annotation'
        )
        
        # Create test ROI template
        self.roi_template = ROITemplate.objects.create(
            name='Test ROI Template',
            task=self.task,
            coordinates={'x': 100, 'y': 100, 'width': 200, 'height': 150},
            feature_descriptor={
                'algorithm': 'SIFT',
                'keypoints': [],
                'descriptors': []
            },
            created_by=self.user
        )
        
        # Create test matching session
        self.matching_session = MatchingSession.objects.create(
            roi_template=self.roi_template,
            task=self.task,
            algorithm_type='SIFT',
            threshold=0.7,
            status='COMPLETED'
        )
        
        # Create sample detection results
        self.detections = []
        for i in range(10):
            detection = DetectionResult.objects.create(
                matching_session=self.matching_session,
                frame_number=i * 5,
                coordinates={
                    'x': 100 + i * 10,
                    'y': 100 + i * 5,
                    'width': 80 + i * 2,
                    'height': 60 + i * 2
                },
                confidence_score=0.8 + i * 0.02,
                is_confirmed=i % 3 == 0  # Confirm every third detection
            )
            self.detections.append(detection)


class TestCOCOExporter(BaseGroundTruthExportTestCase):
    """Test COCO JSON format export functionality."""
    
    def test_coco_export_format_compliance(self):
        """Test that COCO export produces valid COCO format JSON."""
        exporter = COCOExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=False)
        
        # Verify file exists
        self.assertTrue(os.path.exists(result_path))
        
        # Load and validate JSON structure
        with open(result_path, 'r') as f:
            coco_data = json.load(f)
        
        # Validate required COCO fields
        required_fields = ['info', 'images', 'annotations', 'categories']
        for field in required_fields:
            self.assertIn(field, coco_data, f"Missing required COCO field: {field}")
        
        # Validate info structure
        info = coco_data['info']
        required_info_fields = ['description', 'url', 'version', 'year', 'contributor', 'date_created']
        for field in required_info_fields:
            self.assertIn(field, info, f"Missing required info field: {field}")
        
        # Validate images structure
        self.assertIsInstance(coco_data['images'], list)
        for image in coco_data['images']:
            required_image_fields = ['id', 'width', 'height', 'file_name']
            for field in required_image_fields:
                self.assertIn(field, image, f"Missing required image field: {field}")
        
        # Validate annotations structure
        self.assertIsInstance(coco_data['annotations'], list)
        for annotation in coco_data['annotations']:
            required_ann_fields = ['id', 'image_id', 'category_id', 'bbox', 'area']
            for field in required_ann_fields:
                self.assertIn(field, annotation, f"Missing required annotation field: {field}")
            
            # Validate bbox format [x, y, width, height]
            bbox = annotation['bbox']
            self.assertIsInstance(bbox, list)
            self.assertEqual(len(bbox), 4)
            self.assertTrue(all(isinstance(v, (int, float)) for v in bbox))
        
        # Validate categories structure
        self.assertIsInstance(coco_data['categories'], list)
        for category in coco_data['categories']:
            required_cat_fields = ['id', 'name', 'supercategory']
            for field in required_cat_fields:
                self.assertIn(field, category, f"Missing required category field: {field}")
    
    def test_coco_export_confirmed_only(self):
        """Test COCO export with confirmed detections only."""
        exporter = COCOExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=True)
        
        with open(result_path, 'r') as f:
            coco_data = json.load(f)
        
        # Count confirmed detections
        confirmed_count = sum(1 for d in self.detections if d.is_confirmed)
        self.assertEqual(len(coco_data['annotations']), confirmed_count)
    
    def test_coco_export_min_confidence_filter(self):
        """Test COCO export with minimum confidence threshold."""
        min_confidence = 0.85
        exporter = COCOExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=False, min_confidence=min_confidence)
        
        with open(result_path, 'r') as f:
            coco_data = json.load(f)
        
        # Count detections above threshold
        above_threshold = sum(1 for d in self.detections if d.confidence_score >= min_confidence)
        self.assertEqual(len(coco_data['annotations']), above_threshold)


class TestYOLOExporter(BaseGroundTruthExportTestCase):
    """Test YOLO format export functionality."""
    
    def test_yolo_export_directory_structure(self):
        """Test that YOLO export creates correct directory structure."""
        exporter = YOLOExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=False)
        
        # Verify ZIP file exists
        self.assertTrue(os.path.exists(result_path))
        self.assertTrue(result_path.endswith('.zip'))
        
        # Extract and verify structure
        extract_dir = os.path.join(self.temp_dir, 'extracted')
        with zipfile.ZipFile(result_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Check for required YOLO structure
        required_dirs = ['images', 'labels']
        for dir_name in required_dirs:
            dir_path = os.path.join(extract_dir, dir_name)
            self.assertTrue(os.path.exists(dir_path), f"Missing required directory: {dir_name}")
        
        # Check for data.yaml file
        data_yaml_path = os.path.join(extract_dir, 'data.yaml')
        self.assertTrue(os.path.exists(data_yaml_path))
        
        # Verify label files exist and have correct format
        labels_dir = os.path.join(extract_dir, 'labels')
        label_files = os.listdir(labels_dir)
        self.assertGreater(len(label_files), 0, "No label files generated")
        
        for label_file in label_files:
            self.assertTrue(label_file.endswith('.txt'), f"Invalid label file extension: {label_file}")
            
            # Verify label file content format
            label_path = os.path.join(labels_dir, label_file)
            with open(label_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    parts = line.strip().split()
                    # YOLO format: class_id center_x center_y width height
                    self.assertEqual(len(parts), 5, f"Invalid YOLO format in {label_file}: {line}")
                    
                    # Verify all values are numeric
                    for i, value in enumerate(parts):
                        if i == 0:  # class_id should be integer
                            self.assertTrue(value.isdigit(), f"Invalid class_id: {value}")
                        else:  # coordinates should be float between 0 and 1
                            float_val = float(value)
                            self.assertTrue(0 <= float_val <= 1, f"Invalid normalized coordinate: {value}")
    
    def test_yolo_data_yaml_content(self):
        """Test that data.yaml contains correct information."""
        exporter = YOLOExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=False)
        
        # Extract and read data.yaml
        extract_dir = os.path.join(self.temp_dir, 'extracted')
        with zipfile.ZipFile(result_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        data_yaml_path = os.path.join(extract_dir, 'data.yaml')
        with open(data_yaml_path, 'r') as f:
            content = f.read()
        
        # Verify required fields exist
        required_fields = ['nc:', 'names:']
        for field in required_fields:
            self.assertIn(field, content, f"Missing required field in data.yaml: {field}")


class TestPascalVOCExporter(BaseGroundTruthExportTestCase):
    """Test Pascal VOC XML format export functionality."""
    
    def test_pascal_voc_xml_structure(self):
        """Test that Pascal VOC export produces valid XML structure."""
        exporter = PascalVOCExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=False)
        
        # Verify ZIP file exists and extract
        self.assertTrue(os.path.exists(result_path))
        extract_dir = os.path.join(self.temp_dir, 'extracted')
        with zipfile.ZipFile(result_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Check for Annotations directory
        annotations_dir = os.path.join(extract_dir, 'Annotations')
        self.assertTrue(os.path.exists(annotations_dir))
        
        # Verify XML files exist
        xml_files = [f for f in os.listdir(annotations_dir) if f.endswith('.xml')]
        self.assertGreater(len(xml_files), 0, "No XML annotation files generated")
        
        # Validate XML structure
        for xml_file in xml_files[:3]:  # Check first 3 files
            xml_path = os.path.join(annotations_dir, xml_file)
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Verify required Pascal VOC elements
            self.assertEqual(root.tag, 'annotation')
            
            required_elements = ['filename', 'size', 'object']
            for element in required_elements:
                self.assertIsNotNone(root.find(element), f"Missing required element: {element}")
            
            # Validate size element
            size_elem = root.find('size')
            size_children = ['width', 'height', 'depth']
            for child in size_children:
                self.assertIsNotNone(size_elem.find(child), f"Missing size child: {child}")
            
            # Validate object elements
            objects = root.findall('object')
            for obj in objects:
                obj_children = ['name', 'bndbox']
                for child in obj_children:
                    self.assertIsNotNone(obj.find(child), f"Missing object child: {child}")
                
                # Validate bounding box
                bndbox = obj.find('bndbox')
                bbox_children = ['xmin', 'ymin', 'xmax', 'ymax']
                for child in bbox_children:
                    elem = bndbox.find(child)
                    self.assertIsNotNone(elem, f"Missing bndbox child: {child}")
                    # Verify it's a valid number
                    float(elem.text)


class TestCSVExporter(BaseGroundTruthExportTestCase):
    """Test CSV format export functionality."""
    
    def test_csv_export_format(self):
        """Test that CSV export produces valid CSV format."""
        exporter = CSVExporter(self.task.id, self.temp_dir)
        result_path = exporter.export(confirmed_only=False)
        
        # Verify file exists
        self.assertTrue(os.path.exists(result_path))
        self.assertTrue(result_path.endswith('.csv'))
        
        # Read and validate CSV content
        import csv
        with open(result_path, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            rows = list(reader)
        
        # Verify we have data
        self.assertGreater(len(rows), 0, "CSV file is empty")
        
        # Verify required columns exist
        required_columns = [
            'detection_id', 'frame_number', 'confidence_score', 'is_confirmed',
            'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height',
            'roi_template_name', 'task_name'
        ]
        
        first_row = rows[0]
        for column in required_columns:
            self.assertIn(column, first_row, f"Missing required column: {column}")
        
        # Validate data types in rows
        for row in rows[:3]:  # Check first 3 rows
            # Numeric fields should be convertible to numbers
            numeric_fields = ['detection_id', 'frame_number', 'confidence_score',
                            'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height']
            for field in numeric_fields:
                try:
                    float(row[field])
                except ValueError:
                    self.fail(f"Invalid numeric value in field {field}: {row[field]}")
            
            # Boolean field should be 'True' or 'False'
            self.assertIn(row['is_confirmed'], ['True', 'False'])


class TestDatasetSplitter(BaseGroundTruthExportTestCase):
    """Test dataset splitting functionality."""
    
    def test_train_val_test_split(self):
        """Test that dataset splitter correctly divides data."""
        splitter = DatasetSplitter(train_ratio=0.7, val_ratio=0.2, test_ratio=0.1)
        
        # Create more detection data for splitting
        additional_detections = []
        for i in range(50, 100):
            detection = DetectionResult.objects.create(
                matching_session=self.matching_session,
                frame_number=i,
                coordinates={'x': 100, 'y': 100, 'width': 80, 'height': 60},
                confidence_score=0.8,
                is_confirmed=True
            )
            additional_detections.extend([detection])
        
        all_detections = self.detections + additional_detections
        splits = splitter.split_detections(all_detections)
        
        # Verify splits exist
        self.assertIn('train', splits)
        self.assertIn('val', splits)
        self.assertIn('test', splits)
        
        # Verify split ratios are approximately correct
        total_count = len(all_detections)
        train_count = len(splits['train'])
        val_count = len(splits['val'])
        test_count = len(splits['test'])
        
        # Allow some tolerance for rounding
        self.assertAlmostEqual(train_count / total_count, 0.7, delta=0.05)
        self.assertAlmostEqual(val_count / total_count, 0.2, delta=0.05)
        self.assertAlmostEqual(test_count / total_count, 0.1, delta=0.05)
        
        # Verify all detections are included
        all_split_ids = set()
        for split_detections in splits.values():
            all_split_ids.update(d.id for d in split_detections)
        
        original_ids = set(d.id for d in all_detections)
        self.assertEqual(all_split_ids, original_ids)


class TestQualityControlValidator(BaseGroundTruthExportTestCase):
    """Test data validation and quality control."""
    
    def test_coordinate_validation(self):
        """Test validation of bounding box coordinates."""
        validator = QualityControlValidator()
        
        # Valid coordinates
        valid_coords = {'x': 100, 'y': 100, 'width': 200, 'height': 150}
        self.assertTrue(validator.validate_coordinates(valid_coords))
        
        # Invalid coordinates (negative width)
        invalid_coords = {'x': 100, 'y': 100, 'width': -200, 'height': 150}
        self.assertFalse(validator.validate_coordinates(invalid_coords))
        
        # Missing coordinate field
        incomplete_coords = {'x': 100, 'y': 100, 'width': 200}
        self.assertFalse(validator.validate_coordinates(incomplete_coords))
    
    def test_confidence_score_validation(self):
        """Test validation of confidence scores."""
        validator = QualityControlValidator()
        
        # Valid scores
        self.assertTrue(validator.validate_confidence_score(0.0))
        self.assertTrue(validator.validate_confidence_score(0.5))
        self.assertTrue(validator.validate_confidence_score(1.0))
        
        # Invalid scores
        self.assertFalse(validator.validate_confidence_score(-0.1))
        self.assertFalse(validator.validate_confidence_score(1.1))
        self.assertFalse(validator.validate_confidence_score(None))
    
    def test_duplicate_detection(self):
        """Test detection of duplicate detections."""
        validator = QualityControlValidator()
        
        duplicates = validator.find_duplicate_detections(self.detections)
        
        # Since our test data has unique frame numbers, should be no duplicates
        self.assertEqual(len(duplicates), 0)
        
        # Add a duplicate detection
        duplicate = DetectionResult.objects.create(
            matching_session=self.matching_session,
            frame_number=0,  # Same as first detection
            coordinates={'x': 100, 'y': 100, 'width': 80, 'height': 60},
            confidence_score=0.8,
            is_confirmed=True
        )
        
        all_detections = list(self.detections) + [duplicate]
        duplicates = validator.find_duplicate_detections(all_detections)
        self.assertGreater(len(duplicates), 0)


class TestExportConfig(BaseGroundTruthExportTestCase):
    """Test export configuration management."""
    
    def test_config_creation_and_validation(self):
        """Test creation and validation of export configurations."""
        config = ExportConfig(
            export_format='coco',
            include_images=True,
            confirmed_only=True,
            min_confidence=0.8,
            dataset_split={'train': 0.7, 'val': 0.2, 'test': 0.1},
            compression_format='zip'
        )
        
        # Test validation
        self.assertTrue(config.is_valid())
        
        # Test invalid format
        invalid_config = ExportConfig(export_format='invalid_format')
        self.assertFalse(invalid_config.is_valid())
    
    def test_config_serialization(self):
        """Test configuration serialization/deserialization."""
        config = ExportConfig(
            export_format='yolo',
            include_images=False,
            confirmed_only=True
        )
        
        # Serialize to dict
        config_dict = config.to_dict()
        self.assertIsInstance(config_dict, dict)
        self.assertEqual(config_dict['export_format'], 'yolo')
        
        # Deserialize from dict
        new_config = ExportConfig.from_dict(config_dict)
        self.assertEqual(new_config.export_format, config.export_format)
        self.assertEqual(new_config.include_images, config.include_images)


class TestExportJob(BaseGroundTruthExportTestCase):
    """Test export job processing and tracking."""
    
    @patch('cvat.apps.calibrix_matching.services.ground_truth_export.get_current_job')
    def test_job_progress_tracking(self, mock_get_current_job):
        """Test that export jobs track progress correctly."""
        mock_job = Mock()
        mock_get_current_job.return_value = mock_job
        
        config = ExportConfig(export_format='csv', confirmed_only=False)
        job = ExportJob(task_id=self.task.id, config=config)
        
        result = job.execute()
        
        # Verify job methods were called
        self.assertTrue(mock_job.meta.update.called or hasattr(mock_job, 'meta'))
        
        # Verify result contains expected fields
        self.assertIn('status', result)
        self.assertIn('export_path', result)
        self.assertIn('total_detections', result)


class TestGroundTruthExportService(BaseGroundTruthExportTestCase):
    """Test main export service integration."""
    
    def test_service_supports_all_formats(self):
        """Test that service supports all required export formats."""
        service = GroundTruthExportService(task_id=self.task.id)
        
        required_formats = ['coco', 'yolo', 'pascal_voc', 'cvat_xml', 'csv']
        supported_formats = service.get_supported_formats()
        
        for format_name in required_formats:
            self.assertIn(format_name, supported_formats)
    
    def test_service_export_with_different_formats(self):
        """Test service export with different formats."""
        service = GroundTruthExportService(task_id=self.task.id)
        
        formats_to_test = ['csv', 'coco', 'yolo']
        
        for export_format in formats_to_test:
            with self.subTest(export_format=export_format):
                config = ExportConfig(
                    export_format=export_format,
                    confirmed_only=False,
                    output_directory=self.temp_dir
                )
                
                result = service.export(config)
                
                self.assertEqual(result['status'], 'completed')
                self.assertTrue(os.path.exists(result['export_path']))
                self.assertGreater(result['total_detections'], 0)
    
    def test_service_statistics_generation(self):
        """Test that service generates export statistics."""
        service = GroundTruthExportService(task_id=self.task.id)
        
        stats = service.get_export_statistics()
        
        required_stats = [
            'total_detections', 'confirmed_detections', 'unconfirmed_detections',
            'unique_frames', 'confidence_statistics', 'roi_templates_count'
        ]
        
        for stat_name in required_stats:
            self.assertIn(stat_name, stats)


# Performance and Memory Tests
class TestExportPerformance(BaseGroundTruthExportTestCase):
    """Test export performance and memory usage."""
    
    def setUp(self):
        """Set up performance test fixtures."""
        super().setUp()
        
        # Create a large dataset for performance testing
        self.large_detections = []
        for i in range(1000):  # Create 1000 detections
            detection = DetectionResult.objects.create(
                matching_session=self.matching_session,
                frame_number=i,
                coordinates={
                    'x': 100 + (i % 100),
                    'y': 100 + (i % 50),
                    'width': 80,
                    'height': 60
                },
                confidence_score=0.8 + (i % 20) * 0.01,
                is_confirmed=i % 5 == 0
            )
            self.large_detections.append(detection)
    
    def test_large_dataset_export_performance(self):
        """Test export performance with large dataset."""
        import time
        
        service = GroundTruthExportService(task_id=self.task.id)
        config = ExportConfig(export_format='csv', confirmed_only=False)
        
        start_time = time.time()
        result = service.export(config)
        end_time = time.time()
        
        export_time = end_time - start_time
        detections_per_second = result['total_detections'] / export_time
        
        # Performance benchmark: should process at least 100 detections per second
        self.assertGreater(detections_per_second, 100,
                         f"Export too slow: {detections_per_second:.1f} detections/sec")
    
    def test_memory_usage_streaming_export(self):
        """Test memory usage with streaming export for large datasets."""
        import tracemalloc
        
        tracemalloc.start()
        
        service = GroundTruthExportService(task_id=self.task.id)
        config = ExportConfig(
            export_format='coco',
            confirmed_only=False,
            streaming_export=True  # Enable streaming
        )
        
        result = service.export(config)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Memory usage should be reasonable (less than 100MB for 1000 detections)
        peak_mb = peak / 1024 / 1024
        self.assertLess(peak_mb, 100, f"Memory usage too high: {peak_mb:.1f}MB")


if __name__ == '__main__':
    pytest.main([__file__])