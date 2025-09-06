# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import os
import tempfile
import xml.etree.ElementTree as ET
import yaml
import zipfile
import csv
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import TestCase

from ..services.format_validators import (
    FormatValidationResult,
    COCOValidator,
    YOLOValidator,
    PascalVOCValidator,
    CSVValidator,
    FormatValidatorFactory
)


class FormatValidatorTestCase(TestCase):
    """Base test case for format validators."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(self._cleanup_temp_dir)
    
    def _cleanup_temp_dir(self):
        """Clean up temporary directory."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def create_temp_file(self, filename, content):
        """Create a temporary file with content."""
        filepath = os.path.join(self.temp_dir, filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if isinstance(content, (dict, list)):
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(content, f, indent=2)
        elif isinstance(content, str):
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        elif isinstance(content, bytes):
            with open(filepath, 'wb') as f:
                f.write(content)
        
        return filepath


class TestFormatValidationResult(TestCase):
    """Test FormatValidationResult functionality."""
    
    def test_validation_result_creation(self):
        """Test creating validation results."""
        result = FormatValidationResult()
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.warnings), 0)
        self.assertEqual(len(result.info), 0)
    
    def test_adding_errors_warnings_info(self):
        """Test adding different types of messages."""
        result = FormatValidationResult()
        
        # Add error (should make result invalid)
        result.add_error("Test error", "test_field", "TEST_CODE")
        self.assertFalse(result.is_valid)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0]['message'], "Test error")
        
        # Add warning (should not affect validity)
        result.add_warning("Test warning", "warn_field")
        self.assertEqual(len(result.warnings), 1)
        self.assertFalse(result.is_valid)  # Still invalid due to error
        
        # Add info
        result.add_info("Test info", data={'key': 'value'})
        self.assertEqual(len(result.info), 1)
    
    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        result = FormatValidationResult()
        result.add_error("Error message")
        result.add_warning("Warning message")
        result.add_info("Info message")
        result.schema_version = "1.0"
        result.format_specific_data = {'test': True}
        
        data = result.to_dict()
        
        required_keys = ['is_valid', 'errors', 'warnings', 'info', 'schema_version', 'format_specific_data']
        for key in required_keys:
            self.assertIn(key, data)
        
        self.assertFalse(data['is_valid'])
        self.assertEqual(len(data['errors']), 1)
        self.assertEqual(len(data['warnings']), 1)
        self.assertEqual(len(data['info']), 1)


class TestCOCOValidator(FormatValidatorTestCase):
    """Test COCO format validator."""
    
    def setUp(self):
        super().setUp()
        self.validator = COCOValidator()
    
    def test_valid_coco_format(self):
        """Test validation of valid COCO format."""
        valid_coco = {
            "info": {
                "description": "Test Dataset",
                "url": "https://test.com",
                "version": "1.0",
                "year": 2024,
                "contributor": "Test",
                "date_created": "2024-01-01"
            },
            "licenses": [],
            "images": [
                {
                    "id": 1,
                    "width": 640,
                    "height": 480,
                    "file_name": "test.jpg"
                }
            ],
            "annotations": [
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [100, 100, 50, 30],
                    "area": 1500,
                    "iscrowd": 0
                }
            ],
            "categories": [
                {
                    "id": 1,
                    "name": "test_class",
                    "supercategory": "object"
                }
            ]
        }
        
        filepath = self.create_temp_file("valid_coco.json", valid_coco)
        result = self.validator.validate(filepath)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.format_specific_data['image_count'], 1)
        self.assertEqual(result.format_specific_data['annotation_count'], 1)
        self.assertEqual(result.format_specific_data['category_count'], 1)
    
    def test_missing_required_fields(self):
        """Test validation with missing required fields."""
        invalid_coco = {
            "info": {},
            "images": [],
            # Missing annotations and categories
        }
        
        filepath = self.create_temp_file("invalid_coco.json", invalid_coco)
        result = self.validator.validate(filepath)
        
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        
        # Check for specific missing field errors
        error_messages = [error['message'] for error in result.errors]
        self.assertTrue(any('annotations' in msg for msg in error_messages))
        self.assertTrue(any('categories' in msg for msg in error_messages))
    
    def test_invalid_bbox_format(self):
        """Test validation of invalid bbox formats."""
        invalid_bbox_coco = {
            "info": {"description": "Test"},
            "images": [{"id": 1, "width": 640, "height": 480, "file_name": "test.jpg"}],
            "annotations": [
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [100, 100, -50, 30],  # Negative width
                    "area": 1500
                }
            ],
            "categories": [{"id": 1, "name": "test", "supercategory": "object"}]
        }
        
        filepath = self.create_temp_file("invalid_bbox_coco.json", invalid_bbox_coco)
        result = self.validator.validate(filepath)
        
        self.assertFalse(result.is_valid)
        bbox_errors = [error for error in result.errors if 'bbox' in error.get('message', '')]
        self.assertGreater(len(bbox_errors), 0)
    
    def test_duplicate_ids(self):
        """Test detection of duplicate IDs."""
        duplicate_id_coco = {
            "info": {"description": "Test"},
            "images": [
                {"id": 1, "width": 640, "height": 480, "file_name": "test1.jpg"},
                {"id": 1, "width": 640, "height": 480, "file_name": "test2.jpg"}  # Duplicate ID
            ],
            "annotations": [],
            "categories": [{"id": 1, "name": "test", "supercategory": "object"}]
        }
        
        filepath = self.create_temp_file("duplicate_id_coco.json", duplicate_id_coco)
        result = self.validator.validate(filepath)
        
        self.assertFalse(result.is_valid)
        duplicate_errors = [error for error in result.errors if 'Duplicate' in error.get('message', '')]
        self.assertGreater(len(duplicate_errors), 0)
    
    def test_cross_reference_validation(self):
        """Test validation of cross-references between sections."""
        invalid_ref_coco = {
            "info": {"description": "Test"},
            "images": [{"id": 1, "width": 640, "height": 480, "file_name": "test.jpg"}],
            "annotations": [
                {
                    "id": 1,
                    "image_id": 999,  # Non-existent image ID
                    "category_id": 888,  # Non-existent category ID
                    "bbox": [100, 100, 50, 30],
                    "area": 1500
                }
            ],
            "categories": [{"id": 1, "name": "test", "supercategory": "object"}]
        }
        
        filepath = self.create_temp_file("invalid_ref_coco.json", invalid_ref_coco)
        result = self.validator.validate(filepath)
        
        self.assertFalse(result.is_valid)
        ref_errors = [error for error in result.errors if 'non-existent' in error.get('message', '')]
        self.assertEqual(len(ref_errors), 2)  # Should find both invalid references
    
    def test_invalid_json(self):
        """Test handling of invalid JSON."""
        invalid_json_content = '{"info": {"description": "Test"'  # Incomplete JSON
        filepath = self.create_temp_file("invalid.json", invalid_json_content)
        
        result = self.validator.validate(filepath)
        
        self.assertFalse(result.is_valid)
        json_errors = [error for error in result.errors if 'JSON' in error.get('message', '')]
        self.assertGreater(len(json_errors), 0)


class TestYOLOValidator(FormatValidatorTestCase):
    """Test YOLO format validator."""
    
    def setUp(self):
        super().setUp()
        self.validator = YOLOValidator()
    
    def create_yolo_directory(self, with_data_yaml=True, with_labels=True):
        """Create a test YOLO directory structure."""
        yolo_dir = os.path.join(self.temp_dir, 'yolo_dataset')
        os.makedirs(yolo_dir, exist_ok=True)
        
        if with_labels:
            labels_dir = os.path.join(yolo_dir, 'labels')
            os.makedirs(labels_dir, exist_ok=True)
            
            # Create sample label files
            label_content = "0 0.5 0.5 0.2 0.3\n1 0.7 0.2 0.1 0.4\n"
            with open(os.path.join(labels_dir, 'image1.txt'), 'w') as f:
                f.write(label_content)
            
            with open(os.path.join(labels_dir, 'image2.txt'), 'w') as f:
                f.write("2 0.3 0.8 0.4 0.2\n")
        
        if with_data_yaml:
            data_yaml = {
                'nc': 3,
                'names': ['class0', 'class1', 'class2'],
                'path': str(yolo_dir),
                'train': 'images',
                'val': 'images'
            }
            
            with open(os.path.join(yolo_dir, 'data.yaml'), 'w') as f:
                yaml.dump(data_yaml, f)
        
        return yolo_dir
    
    def test_valid_yolo_directory(self):
        """Test validation of valid YOLO directory."""
        yolo_dir = self.create_yolo_directory()
        result = self.validator.validate(yolo_dir)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertGreater(result.format_specific_data['label_file_count'], 0)
        self.assertEqual(result.format_specific_data['class_count'], 3)
        self.assertEqual(result.format_specific_data['class_names'], ['class0', 'class1', 'class2'])
    
    def test_missing_labels_directory(self):
        """Test validation with missing labels directory."""
        yolo_dir = self.create_yolo_directory(with_labels=False)
        result = self.validator.validate(yolo_dir)
        
        self.assertFalse(result.is_valid)
        missing_dir_errors = [error for error in result.errors if 'labels' in error.get('message', '')]
        self.assertGreater(len(missing_dir_errors), 0)
    
    def test_missing_data_yaml(self):
        """Test validation with missing data.yaml."""
        yolo_dir = self.create_yolo_directory(with_data_yaml=False)
        result = self.validator.validate(yolo_dir)
        
        # Should still be valid but with warnings
        warning_messages = [warning['message'] for warning in result.warnings]
        self.assertTrue(any('data.yaml' in msg for msg in warning_messages))
    
    def test_invalid_label_format(self):
        """Test validation of invalid label file format."""
        yolo_dir = os.path.join(self.temp_dir, 'yolo_invalid')
        os.makedirs(yolo_dir)
        
        labels_dir = os.path.join(yolo_dir, 'labels')
        os.makedirs(labels_dir)
        
        # Create invalid label file (missing values)
        invalid_label_content = "0 0.5 0.5\n"  # Only 3 values instead of 5
        with open(os.path.join(labels_dir, 'invalid.txt'), 'w') as f:
            f.write(invalid_label_content)
        
        result = self.validator.validate(yolo_dir)
        
        self.assertFalse(result.is_valid)
        format_errors = [error for error in result.errors if 'Invalid YOLO format' in error.get('message', '')]
        self.assertGreater(len(format_errors), 0)
    
    def test_coordinates_out_of_range(self):
        """Test detection of coordinates outside valid range."""
        yolo_dir = os.path.join(self.temp_dir, 'yolo_coords')
        os.makedirs(yolo_dir)
        
        labels_dir = os.path.join(yolo_dir, 'labels')
        os.makedirs(labels_dir)
        
        # Create label with coordinates outside [0,1] range
        invalid_coords = "0 1.5 0.5 0.2 0.3\n"  # center_x = 1.5 > 1.0
        with open(os.path.join(labels_dir, 'invalid_coords.txt'), 'w') as f:
            f.write(invalid_coords)
        
        result = self.validator.validate(yolo_dir)
        
        coord_warnings = [warning for warning in result.warnings if 'out of range' in warning.get('message', '')]
        self.assertGreater(len(coord_warnings), 0)
    
    def test_yolo_zip_validation(self):
        """Test validation of YOLO dataset in ZIP format."""
        # Create YOLO directory
        yolo_dir = self.create_yolo_directory()
        
        # Create ZIP file
        zip_path = os.path.join(self.temp_dir, 'yolo_dataset.zip')
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for root, dirs, files in os.walk(yolo_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, yolo_dir)
                    zipf.write(file_path, arcname)
        
        result = self.validator.validate(zip_path)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)


class TestPascalVOCValidator(FormatValidatorTestCase):
    """Test Pascal VOC format validator."""
    
    def setUp(self):
        super().setUp()
        self.validator = PascalVOCValidator()
    
    def create_valid_voc_xml(self):
        """Create a valid Pascal VOC XML annotation."""
        annotation = ET.Element("annotation")
        
        # Add filename
        ET.SubElement(annotation, "filename").text = "test.jpg"
        
        # Add source
        source = ET.SubElement(annotation, "source")
        ET.SubElement(source, "database").text = "Test Database"
        
        # Add size
        size = ET.SubElement(annotation, "size")
        ET.SubElement(size, "width").text = "640"
        ET.SubElement(size, "height").text = "480"
        ET.SubElement(size, "depth").text = "3"
        
        # Add object
        obj = ET.SubElement(annotation, "object")
        ET.SubElement(obj, "name").text = "test_class"
        ET.SubElement(obj, "pose").text = "Unspecified"
        ET.SubElement(obj, "truncated").text = "0"
        ET.SubElement(obj, "difficult").text = "0"
        
        bndbox = ET.SubElement(obj, "bndbox")
        ET.SubElement(bndbox, "xmin").text = "100"
        ET.SubElement(bndbox, "ymin").text = "100"
        ET.SubElement(bndbox, "xmax").text = "200"
        ET.SubElement(bndbox, "ymax").text = "150"
        
        return annotation
    
    def test_valid_voc_xml(self):
        """Test validation of valid Pascal VOC XML."""
        annotation = self.create_valid_voc_xml()
        
        xml_path = os.path.join(self.temp_dir, "valid_voc.xml")
        tree = ET.ElementTree(annotation)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        
        result = self.validator.validate(xml_path)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.format_specific_data['object_count'], 1)
        self.assertIn('test_class', result.format_specific_data['classes'])
    
    def test_missing_required_elements(self):
        """Test validation with missing required elements."""
        annotation = ET.Element("annotation")
        # Only add filename, missing size and object
        ET.SubElement(annotation, "filename").text = "test.jpg"
        
        xml_path = os.path.join(self.temp_dir, "incomplete_voc.xml")
        tree = ET.ElementTree(annotation)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        
        result = self.validator.validate(xml_path)
        
        self.assertFalse(result.is_valid)
        missing_errors = [error for error in result.errors if 'Missing required element' in error.get('message', '')]
        self.assertGreater(len(missing_errors), 0)
    
    def test_invalid_bbox_coordinates(self):
        """Test validation of invalid bounding box coordinates."""
        annotation = self.create_valid_voc_xml()
        
        # Modify bounding box to have invalid coordinates (xmax <= xmin)
        obj = annotation.find("object")
        bndbox = obj.find("bndbox")
        bndbox.find("xmax").text = "50"  # xmax < xmin (100)
        
        xml_path = os.path.join(self.temp_dir, "invalid_bbox_voc.xml")
        tree = ET.ElementTree(annotation)
        tree.write(xml_path, encoding='utf-8', xml_declaration=True)
        
        result = self.validator.validate(xml_path)
        
        self.assertFalse(result.is_valid)
        bbox_errors = [error for error in result.errors if 'must be greater than' in error.get('message', '')]
        self.assertGreater(len(bbox_errors), 0)
    
    def test_invalid_xml_format(self):
        """Test handling of invalid XML format."""
        invalid_xml = "<annotation><filename>test.jpg</filename>"  # Incomplete XML
        xml_path = self.create_temp_file("invalid.xml", invalid_xml)
        
        result = self.validator.validate(xml_path)
        
        self.assertFalse(result.is_valid)
        xml_errors = [error for error in result.errors if 'XML parsing error' in error.get('message', '')]
        self.assertGreater(len(xml_errors), 0)


class TestCSVValidator(FormatValidatorTestCase):
    """Test CSV format validator."""
    
    def setUp(self):
        super().setUp()
        self.validator = CSVValidator()
    
    def create_valid_csv(self):
        """Create a valid CSV file."""
        csv_data = [
            ['detection_id', 'frame_number', 'confidence_score', 'is_confirmed', 
             'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height', 'roi_template_name'],
            ['1', '0', '0.85', 'True', '100', '100', '50', '30', 'test_template'],
            ['2', '5', '0.92', 'False', '200', '150', '60', '40', 'test_template'],
            ['3', '10', '0.78', 'True', '300', '200', '45', '35', 'another_template']
        ]
        
        csv_path = os.path.join(self.temp_dir, 'valid.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        return csv_path
    
    def test_valid_csv_format(self):
        """Test validation of valid CSV format."""
        csv_path = self.create_valid_csv()
        result = self.validator.validate(csv_path)
        
        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(result.format_specific_data['row_count'], 3)  # Excluding header
        self.assertGreater(result.format_specific_data['column_count'], 8)
    
    def test_missing_required_columns(self):
        """Test validation with missing required columns."""
        csv_data = [
            ['detection_id', 'frame_number'],  # Missing most required columns
            ['1', '0'],
            ['2', '5']
        ]
        
        csv_path = os.path.join(self.temp_dir, 'incomplete.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        result = self.validator.validate(csv_path)
        
        self.assertFalse(result.is_valid)
        column_errors = [error for error in result.errors if 'Missing required columns' in error.get('message', '')]
        self.assertGreater(len(column_errors), 0)
    
    def test_invalid_data_types(self):
        """Test validation of invalid data types."""
        csv_data = [
            ['detection_id', 'frame_number', 'confidence_score', 'is_confirmed',
             'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height'],
            ['not_a_number', '0', '1.5', 'maybe', '100', '100', '-50', '30'],  # Various invalid values
        ]
        
        csv_path = os.path.join(self.temp_dir, 'invalid_types.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        result = self.validator.validate(csv_path)
        
        self.assertFalse(result.is_valid)
        
        # Should have errors for invalid numeric values, confidence out of range, invalid bbox size
        type_errors = [error for error in result.errors if any(keyword in error.get('message', '') 
                      for keyword in ['must be numeric', 'between 0 and 1', 'must be positive', 'boolean'])]
        self.assertGreater(len(type_errors), 0)
    
    def test_empty_csv(self):
        """Test validation of empty CSV file."""
        csv_path = os.path.join(self.temp_dir, 'empty.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            pass  # Create empty file
        
        result = self.validator.validate(csv_path)
        
        # Should have errors for no headers
        header_errors = [error for error in result.errors if 'No column headers' in error.get('message', '')]
        self.assertGreater(len(header_errors), 0)
    
    def test_duplicate_columns(self):
        """Test detection of duplicate column headers."""
        csv_data = [
            ['detection_id', 'detection_id', 'frame_number', 'confidence_score', 
             'is_confirmed', 'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height'],  # Duplicate detection_id
            ['1', '1', '0', '0.85', 'True', '100', '100', '50', '30']
        ]
        
        csv_path = os.path.join(self.temp_dir, 'duplicate_headers.csv')
        with open(csv_path, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerows(csv_data)
        
        result = self.validator.validate(csv_path)
        
        self.assertFalse(result.is_valid)
        duplicate_errors = [error for error in result.errors if 'Duplicate columns' in error.get('message', '')]
        self.assertGreater(len(duplicate_errors), 0)


class TestFormatValidatorFactory(TestCase):
    """Test FormatValidatorFactory functionality."""
    
    def test_create_validator(self):
        """Test creating validators for different formats."""
        formats_and_classes = [
            ('coco', COCOValidator),
            ('yolo', YOLOValidator),
            ('pascal_voc', PascalVOCValidator),
            ('csv', CSVValidator)
        ]
        
        for format_name, expected_class in formats_and_classes:
            validator = FormatValidatorFactory.create_validator(format_name)
            self.assertIsInstance(validator, expected_class)
    
    def test_unsupported_format(self):
        """Test error handling for unsupported formats."""
        with self.assertRaises(ValueError) as context:
            FormatValidatorFactory.create_validator('unsupported_format')
        
        self.assertIn('Unsupported format', str(context.exception))
    
    def test_get_supported_formats(self):
        """Test getting list of supported formats."""
        supported_formats = FormatValidatorFactory.get_supported_formats()
        
        expected_formats = ['coco', 'yolo', 'pascal_voc', 'csv']
        for format_name in expected_formats:
            self.assertIn(format_name, supported_formats)
    
    @patch.object(COCOValidator, 'validate')
    def test_validate_file(self, mock_validate):
        """Test file validation through factory."""
        # Setup mock
        mock_result = FormatValidationResult()
        mock_result.is_valid = True
        mock_validate.return_value = mock_result
        
        # Test validation
        result = FormatValidatorFactory.validate_file('/tmp/test.json', 'coco')
        
        self.assertTrue(result.is_valid)
        mock_validate.assert_called_once_with('/tmp/test.json')


if __name__ == '__main__':
    pytest.main([__file__])