# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import json
import logging
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import yaml
import csv
import os
import zipfile
import tarfile

logger = logging.getLogger(__name__)


class FormatValidationResult:
    """Container for format validation results."""
    
    def __init__(self):
        self.is_valid = True
        self.errors = []
        self.warnings = []
        self.info = []
        self.schema_version = None
        self.format_specific_data = {}
    
    def add_error(self, message: str, field: Optional[str] = None, code: Optional[str] = None):
        """Add a validation error."""
        self.is_valid = False
        self.errors.append({
            'message': message,
            'field': field,
            'code': code,
            'severity': 'error'
        })
    
    def add_warning(self, message: str, field: Optional[str] = None, code: Optional[str] = None):
        """Add a validation warning."""
        self.warnings.append({
            'message': message,
            'field': field,
            'code': code,
            'severity': 'warning'
        })
    
    def add_info(self, message: str, field: Optional[str] = None, data: Any = None):
        """Add informational message."""
        self.info.append({
            'message': message,
            'field': field,
            'data': data,
            'severity': 'info'
        })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'is_valid': self.is_valid,
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
            'schema_version': self.schema_version,
            'format_specific_data': self.format_specific_data
        }


class BaseFormatValidator(ABC):
    """Base class for format-specific validators."""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    def validate(self, file_path: str) -> FormatValidationResult:
        """Validate a file against the format specification."""
        pass
    
    @abstractmethod
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        pass
    
    def _validate_file_exists(self, file_path: str) -> bool:
        """Check if file exists and is readable."""
        return os.path.exists(file_path) and os.path.isfile(file_path)
    
    def _get_file_size(self, file_path: str) -> int:
        """Get file size in bytes."""
        return os.path.getsize(file_path) if os.path.exists(file_path) else 0


class COCOValidator(BaseFormatValidator):
    """Validator for COCO JSON format."""
    
    REQUIRED_FIELDS = {
        'root': ['info', 'images', 'annotations', 'categories'],
        'info': ['description', 'url', 'version', 'year', 'contributor', 'date_created'],
        'image': ['id', 'width', 'height', 'file_name'],
        'annotation': ['id', 'image_id', 'category_id', 'bbox', 'area'],
        'category': ['id', 'name', 'supercategory']
    }
    
    def validate(self, file_path: str) -> FormatValidationResult:
        """Validate COCO JSON format."""
        result = FormatValidationResult()
        result.schema_version = "COCO 1.0"
        
        if not self._validate_file_exists(file_path):
            result.add_error("File does not exist or is not readable", "file", "FILE_NOT_FOUND")
            return result
        
        try:
            # Load and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result.add_info(f"JSON file loaded successfully", "file", {"size_bytes": self._get_file_size(file_path)})
            
            # Validate root structure
            self._validate_root_structure(data, result)
            
            # Validate sections
            if 'info' in data:
                self._validate_info_section(data['info'], result)
            
            if 'images' in data:
                self._validate_images_section(data['images'], result)
            
            if 'annotations' in data:
                self._validate_annotations_section(data['annotations'], result)
            
            if 'categories' in data:
                self._validate_categories_section(data['categories'], result)
            
            # Cross-validation
            self._validate_cross_references(data, result)
            
            # Format-specific statistics
            result.format_specific_data = {
                'image_count': len(data.get('images', [])),
                'annotation_count': len(data.get('annotations', [])),
                'category_count': len(data.get('categories', [])),
                'has_segmentation': any('segmentation' in ann for ann in data.get('annotations', [])),
                'has_keypoints': any('keypoints' in ann for ann in data.get('annotations', []))
            }
            
        except json.JSONDecodeError as e:
            result.add_error(f"Invalid JSON format: {e}", "json", "INVALID_JSON")
        except Exception as e:
            result.add_error(f"Validation error: {e}", "general", "VALIDATION_ERROR")
        
        return result
    
    def _validate_root_structure(self, data: Dict[str, Any], result: FormatValidationResult):
        """Validate root-level COCO structure."""
        for field in self.REQUIRED_FIELDS['root']:
            if field not in data:
                result.add_error(f"Missing required field: {field}", "root", "MISSING_FIELD")
            elif not isinstance(data[field], (list, dict)):
                result.add_error(f"Field {field} must be list or dict", field, "INVALID_TYPE")
    
    def _validate_info_section(self, info: Dict[str, Any], result: FormatValidationResult):
        """Validate COCO info section."""
        for field in self.REQUIRED_FIELDS['info']:
            if field not in info:
                result.add_warning(f"Missing recommended info field: {field}", "info", "MISSING_INFO_FIELD")
        
        # Validate specific fields
        if 'year' in info:
            try:
                year = int(info['year'])
                if year < 1900 or year > 2100:
                    result.add_warning("Year seems unrealistic", "info.year", "UNREALISTIC_YEAR")
            except (ValueError, TypeError):
                result.add_error("Year must be a valid integer", "info.year", "INVALID_YEAR")
    
    def _validate_images_section(self, images: List[Dict[str, Any]], result: FormatValidationResult):
        """Validate COCO images section."""
        if not images:
            result.add_warning("No images in dataset", "images", "EMPTY_IMAGES")
            return
        
        image_ids = set()
        for i, image in enumerate(images):
            # Check required fields
            for field in self.REQUIRED_FIELDS['image']:
                if field not in image:
                    result.add_error(f"Image {i}: missing field {field}", f"images[{i}].{field}", "MISSING_FIELD")
            
            # Check image ID uniqueness
            if 'id' in image:
                img_id = image['id']
                if img_id in image_ids:
                    result.add_error(f"Duplicate image ID: {img_id}", f"images[{i}].id", "DUPLICATE_ID")
                image_ids.add(img_id)
            
            # Validate dimensions
            if 'width' in image and 'height' in image:
                try:
                    width, height = int(image['width']), int(image['height'])
                    if width <= 0 or height <= 0:
                        result.add_error(f"Image {i}: invalid dimensions {width}x{height}", 
                                       f"images[{i}]", "INVALID_DIMENSIONS")
                except (ValueError, TypeError):
                    result.add_error(f"Image {i}: width and height must be integers", 
                                   f"images[{i}]", "INVALID_DIMENSION_TYPE")
        
        result.add_info(f"Validated {len(images)} images", "images")
    
    def _validate_annotations_section(self, annotations: List[Dict[str, Any]], result: FormatValidationResult):
        """Validate COCO annotations section."""
        if not annotations:
            result.add_warning("No annotations in dataset", "annotations", "EMPTY_ANNOTATIONS")
            return
        
        annotation_ids = set()
        for i, annotation in enumerate(annotations):
            # Check required fields
            for field in self.REQUIRED_FIELDS['annotation']:
                if field not in annotation:
                    result.add_error(f"Annotation {i}: missing field {field}", 
                                   f"annotations[{i}].{field}", "MISSING_FIELD")
            
            # Check annotation ID uniqueness
            if 'id' in annotation:
                ann_id = annotation['id']
                if ann_id in annotation_ids:
                    result.add_error(f"Duplicate annotation ID: {ann_id}", 
                                   f"annotations[{i}].id", "DUPLICATE_ID")
                annotation_ids.add(ann_id)
            
            # Validate bbox format
            if 'bbox' in annotation:
                bbox = annotation['bbox']
                if not isinstance(bbox, list) or len(bbox) != 4:
                    result.add_error(f"Annotation {i}: bbox must be list of 4 numbers", 
                                   f"annotations[{i}].bbox", "INVALID_BBOX_FORMAT")
                else:
                    try:
                        x, y, w, h = [float(v) for v in bbox]
                        if w <= 0 or h <= 0:
                            result.add_error(f"Annotation {i}: bbox width/height must be positive", 
                                           f"annotations[{i}].bbox", "INVALID_BBOX_SIZE")
                        if x < 0 or y < 0:
                            result.add_warning(f"Annotation {i}: negative bbox coordinates", 
                                             f"annotations[{i}].bbox", "NEGATIVE_COORDINATES")
                    except (ValueError, TypeError):
                        result.add_error(f"Annotation {i}: bbox values must be numeric", 
                                       f"annotations[{i}].bbox", "INVALID_BBOX_VALUES")
            
            # Validate area
            if 'area' in annotation:
                try:
                    area = float(annotation['area'])
                    if area <= 0:
                        result.add_error(f"Annotation {i}: area must be positive", 
                                       f"annotations[{i}].area", "INVALID_AREA")
                except (ValueError, TypeError):
                    result.add_error(f"Annotation {i}: area must be numeric", 
                                   f"annotations[{i}].area", "INVALID_AREA_TYPE")
        
        result.add_info(f"Validated {len(annotations)} annotations", "annotations")
    
    def _validate_categories_section(self, categories: List[Dict[str, Any]], result: FormatValidationResult):
        """Validate COCO categories section."""
        if not categories:
            result.add_error("No categories in dataset", "categories", "EMPTY_CATEGORIES")
            return
        
        category_ids = set()
        category_names = set()
        
        for i, category in enumerate(categories):
            # Check required fields
            for field in self.REQUIRED_FIELDS['category']:
                if field not in category:
                    result.add_error(f"Category {i}: missing field {field}", 
                                   f"categories[{i}].{field}", "MISSING_FIELD")
            
            # Check uniqueness
            if 'id' in category:
                cat_id = category['id']
                if cat_id in category_ids:
                    result.add_error(f"Duplicate category ID: {cat_id}", 
                                   f"categories[{i}].id", "DUPLICATE_ID")
                category_ids.add(cat_id)
            
            if 'name' in category:
                cat_name = category['name']
                if cat_name in category_names:
                    result.add_warning(f"Duplicate category name: {cat_name}", 
                                     f"categories[{i}].name", "DUPLICATE_NAME")
                category_names.add(cat_name)
        
        result.add_info(f"Validated {len(categories)} categories", "categories")
    
    def _validate_cross_references(self, data: Dict[str, Any], result: FormatValidationResult):
        """Validate cross-references between sections."""
        image_ids = {img['id'] for img in data.get('images', []) if 'id' in img}
        category_ids = {cat['id'] for cat in data.get('categories', []) if 'id' in cat}
        
        # Check annotation references
        for i, annotation in enumerate(data.get('annotations', [])):
            if 'image_id' in annotation:
                img_id = annotation['image_id']
                if img_id not in image_ids:
                    result.add_error(f"Annotation {i}: references non-existent image ID {img_id}", 
                                   f"annotations[{i}].image_id", "INVALID_REFERENCE")
            
            if 'category_id' in annotation:
                cat_id = annotation['category_id']
                if cat_id not in category_ids:
                    result.add_error(f"Annotation {i}: references non-existent category ID {cat_id}", 
                                   f"annotations[{i}].category_id", "INVALID_REFERENCE")
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.json']


class YOLOValidator(BaseFormatValidator):
    """Validator for YOLO format."""
    
    def validate(self, file_path: str) -> FormatValidationResult:
        """Validate YOLO format (directory or archive)."""
        result = FormatValidationResult()
        result.schema_version = "YOLO v8"
        
        # Handle both directory and archive inputs
        temp_dir = None
        yolo_dir = file_path
        
        if file_path.endswith(('.zip', '.tar.gz')):
            # Extract archive to temporary directory
            import tempfile
            temp_dir = tempfile.mkdtemp()
            
            try:
                if file_path.endswith('.zip'):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                elif file_path.endswith('.tar.gz'):
                    with tarfile.open(file_path, 'r:gz') as tar_ref:
                        tar_ref.extractall(temp_dir)
                
                # Find the actual YOLO directory
                extracted_items = os.listdir(temp_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_dir, extracted_items[0])):
                    yolo_dir = os.path.join(temp_dir, extracted_items[0])
                else:
                    yolo_dir = temp_dir
            
            except Exception as e:
                result.add_error(f"Failed to extract archive: {e}", "archive", "EXTRACTION_ERROR")
                return result
        
        try:
            if not os.path.isdir(yolo_dir):
                result.add_error("Path is not a directory", "directory", "NOT_DIRECTORY")
                return result
            
            # Check required YOLO structure
            self._validate_directory_structure(yolo_dir, result)
            
            # Validate data.yaml file
            data_yaml_path = os.path.join(yolo_dir, 'data.yaml')
            if os.path.exists(data_yaml_path):
                self._validate_data_yaml(data_yaml_path, result)
            
            # Validate label files
            labels_dir = os.path.join(yolo_dir, 'labels')
            if os.path.exists(labels_dir):
                self._validate_label_files(labels_dir, result)
            
        finally:
            # Cleanup temporary directory
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir)
        
        return result
    
    def _validate_directory_structure(self, yolo_dir: str, result: FormatValidationResult):
        """Validate YOLO directory structure."""
        required_items = ['labels']
        optional_items = ['images', 'data.yaml', 'dataset.yaml']
        
        contents = os.listdir(yolo_dir)
        
        # Check required directories
        for item in required_items:
            if item not in contents:
                result.add_error(f"Missing required directory: {item}", "structure", "MISSING_DIRECTORY")
            elif not os.path.isdir(os.path.join(yolo_dir, item)):
                result.add_error(f"{item} should be a directory", "structure", "NOT_DIRECTORY")
        
        # Check for data configuration file
        data_files = [f for f in ['data.yaml', 'dataset.yaml'] if f in contents]
        if not data_files:
            result.add_warning("No data configuration file (data.yaml) found", "structure", "NO_CONFIG_FILE")
        
        result.add_info(f"Directory contains: {', '.join(contents)}", "structure")
    
    def _validate_data_yaml(self, yaml_path: str, result: FormatValidationResult):
        """Validate YOLO data.yaml configuration file."""
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not isinstance(data, dict):
                result.add_error("data.yaml must contain a dictionary", "data_yaml", "INVALID_FORMAT")
                return
            
            # Check required fields
            required_fields = ['nc', 'names']
            for field in required_fields:
                if field not in data:
                    result.add_error(f"Missing required field in data.yaml: {field}", "data_yaml", "MISSING_FIELD")
            
            # Validate class count
            if 'nc' in data:
                try:
                    nc = int(data['nc'])
                    if nc <= 0:
                        result.add_error("nc (number of classes) must be positive", "data_yaml.nc", "INVALID_VALUE")
                except (ValueError, TypeError):
                    result.add_error("nc must be an integer", "data_yaml.nc", "INVALID_TYPE")
            
            # Validate class names
            if 'names' in data:
                names = data['names']
                if isinstance(names, list):
                    if 'nc' in data and len(names) != data.get('nc', 0):
                        result.add_warning(f"names list length ({len(names)}) doesn't match nc ({data.get('nc')})", 
                                         "data_yaml.names", "LENGTH_MISMATCH")
                    
                    # Check for duplicate names
                    if len(names) != len(set(names)):
                        result.add_warning("Duplicate class names found", "data_yaml.names", "DUPLICATE_NAMES")
                    
                    result.format_specific_data['class_names'] = names
                    result.format_specific_data['class_count'] = len(names)
                    
                elif isinstance(names, dict):
                    # Names as id->name mapping
                    if 'nc' in data and len(names) != data.get('nc', 0):
                        result.add_warning("names dict length doesn't match nc", "data_yaml.names", "LENGTH_MISMATCH")
                    
                    result.format_specific_data['class_names'] = list(names.values())
                    result.format_specific_data['class_count'] = len(names)
                else:
                    result.add_error("names must be list or dict", "data_yaml.names", "INVALID_TYPE")
            
            result.add_info("data.yaml file validated successfully", "data_yaml")
            
        except yaml.YAMLError as e:
            result.add_error(f"Invalid YAML format: {e}", "data_yaml", "INVALID_YAML")
        except Exception as e:
            result.add_error(f"Error reading data.yaml: {e}", "data_yaml", "READ_ERROR")
    
    def _validate_label_files(self, labels_dir: str, result: FormatValidationResult):
        """Validate YOLO label files."""
        label_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
        
        if not label_files:
            result.add_warning("No label files found in labels directory", "labels", "NO_LABELS")
            return
        
        total_annotations = 0
        max_class_id = -1
        
        for label_file in label_files[:100]:  # Sample first 100 files for performance
            label_path = os.path.join(labels_dir, label_file)
            
            try:
                with open(label_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                for line_num, line in enumerate(lines, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split()
                    
                    # YOLO format: class_id center_x center_y width height
                    if len(parts) < 5:
                        result.add_error(f"{label_file}:{line_num}: Invalid YOLO format (need 5 values)", 
                                       f"labels.{label_file}", "INVALID_FORMAT")
                        continue
                    
                    try:
                        class_id = int(parts[0])
                        coords = [float(x) for x in parts[1:5]]
                        
                        # Validate class ID
                        if class_id < 0:
                            result.add_error(f"{label_file}:{line_num}: Negative class ID", 
                                           f"labels.{label_file}", "NEGATIVE_CLASS_ID")
                        
                        max_class_id = max(max_class_id, class_id)
                        
                        # Validate coordinates (should be normalized 0-1)
                        for i, coord in enumerate(coords):
                            if not (0 <= coord <= 1):
                                coord_names = ['center_x', 'center_y', 'width', 'height']
                                result.add_warning(f"{label_file}:{line_num}: {coord_names[i]} out of range [0,1]", 
                                                 f"labels.{label_file}", "COORD_OUT_OF_RANGE")
                        
                        # Validate width and height are positive
                        if coords[2] <= 0 or coords[3] <= 0:
                            result.add_error(f"{label_file}:{line_num}: Width and height must be positive", 
                                           f"labels.{label_file}", "INVALID_SIZE")
                        
                        total_annotations += 1
                        
                    except ValueError as e:
                        result.add_error(f"{label_file}:{line_num}: Invalid numeric values", 
                                       f"labels.{label_file}", "INVALID_VALUES")
                
            except Exception as e:
                result.add_error(f"Error reading {label_file}: {e}", f"labels.{label_file}", "READ_ERROR")
        
        result.format_specific_data.update({
            'label_file_count': len(label_files),
            'total_annotations': total_annotations,
            'max_class_id': max_class_id
        })
        
        result.add_info(f"Validated {len(label_files)} label files with {total_annotations} annotations", "labels")
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.zip', '.tar.gz']  # YOLO is typically distributed as archives


class PascalVOCValidator(BaseFormatValidator):
    """Validator for Pascal VOC XML format."""
    
    def validate(self, file_path: str) -> FormatValidationResult:
        """Validate Pascal VOC format."""
        result = FormatValidationResult()
        result.schema_version = "Pascal VOC 2012"
        
        # Handle both single XML file and directory/archive
        if file_path.endswith('.xml'):
            self._validate_single_xml(file_path, result)
        else:
            self._validate_voc_dataset(file_path, result)
        
        return result
    
    def _validate_single_xml(self, xml_path: str, result: FormatValidationResult):
        """Validate a single Pascal VOC XML file."""
        if not self._validate_file_exists(xml_path):
            result.add_error("XML file does not exist", "file", "FILE_NOT_FOUND")
            return
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Validate root element
            if root.tag != 'annotation':
                result.add_error("Root element must be 'annotation'", "xml.root", "INVALID_ROOT")
                return
            
            # Check required elements
            required_elements = ['filename', 'size', 'object']
            for element in required_elements:
                if root.find(element) is None:
                    if element == 'object':
                        result.add_warning("No objects found in annotation", "xml.object", "NO_OBJECTS")
                    else:
                        result.add_error(f"Missing required element: {element}", f"xml.{element}", "MISSING_ELEMENT")
            
            # Validate size element
            size_elem = root.find('size')
            if size_elem is not None:
                self._validate_size_element(size_elem, result)
            
            # Validate object elements
            objects = root.findall('object')
            self._validate_object_elements(objects, result)
            
            result.format_specific_data = {
                'object_count': len(objects),
                'has_segmentation': any(obj.find('segmented') is not None for obj in objects),
                'classes': list(set(obj.find('name').text for obj in objects if obj.find('name') is not None))
            }
            
        except ET.ParseError as e:
            result.add_error(f"XML parsing error: {e}", "xml", "INVALID_XML")
        except Exception as e:
            result.add_error(f"Validation error: {e}", "xml", "VALIDATION_ERROR")
    
    def _validate_voc_dataset(self, path: str, result: FormatValidationResult):
        """Validate complete Pascal VOC dataset structure."""
        # Implementation for validating full VOC dataset structure
        # This would check Annotations/, ImageSets/, etc.
        result.add_info("VOC dataset structure validation not fully implemented", "structure")
    
    def _validate_size_element(self, size_elem: ET.Element, result: FormatValidationResult):
        """Validate Pascal VOC size element."""
        required_children = ['width', 'height', 'depth']
        
        for child in required_children:
            child_elem = size_elem.find(child)
            if child_elem is None:
                result.add_error(f"Missing size child: {child}", f"xml.size.{child}", "MISSING_SIZE_CHILD")
            else:
                try:
                    value = int(child_elem.text)
                    if value <= 0:
                        result.add_error(f"Size {child} must be positive", f"xml.size.{child}", "INVALID_SIZE_VALUE")
                except (ValueError, TypeError):
                    result.add_error(f"Size {child} must be integer", f"xml.size.{child}", "INVALID_SIZE_TYPE")
    
    def _validate_object_elements(self, objects: List[ET.Element], result: FormatValidationResult):
        """Validate Pascal VOC object elements."""
        for i, obj in enumerate(objects):
            # Check required object children
            required_children = ['name', 'bndbox']
            for child in required_children:
                if obj.find(child) is None:
                    result.add_error(f"Object {i}: missing {child}", f"xml.object[{i}].{child}", "MISSING_OBJECT_CHILD")
            
            # Validate bounding box
            bndbox = obj.find('bndbox')
            if bndbox is not None:
                self._validate_bndbox_element(bndbox, i, result)
    
    def _validate_bndbox_element(self, bndbox: ET.Element, obj_index: int, result: FormatValidationResult):
        """Validate Pascal VOC bounding box element."""
        required_coords = ['xmin', 'ymin', 'xmax', 'ymax']
        
        coords = {}
        for coord in required_coords:
            coord_elem = bndbox.find(coord)
            if coord_elem is None:
                result.add_error(f"Object {obj_index}: missing bndbox {coord}", 
                               f"xml.object[{obj_index}].bndbox.{coord}", "MISSING_COORD")
            else:
                try:
                    coords[coord] = float(coord_elem.text)
                except (ValueError, TypeError):
                    result.add_error(f"Object {obj_index}: {coord} must be numeric", 
                                   f"xml.object[{obj_index}].bndbox.{coord}", "INVALID_COORD_TYPE")
        
        # Validate coordinate relationships
        if len(coords) == 4:
            xmin, ymin, xmax, ymax = coords['xmin'], coords['ymin'], coords['xmax'], coords['ymax']
            
            if xmax <= xmin:
                result.add_error(f"Object {obj_index}: xmax must be greater than xmin", 
                               f"xml.object[{obj_index}].bndbox", "INVALID_BBOX")
            
            if ymax <= ymin:
                result.add_error(f"Object {obj_index}: ymax must be greater than ymin", 
                               f"xml.object[{obj_index}].bndbox", "INVALID_BBOX")
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.xml', '.zip', '.tar.gz']


class CSVValidator(BaseFormatValidator):
    """Validator for CSV export format."""
    
    REQUIRED_COLUMNS = [
        'detection_id', 'frame_number', 'confidence_score', 'is_confirmed',
        'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height'
    ]
    
    def validate(self, file_path: str) -> FormatValidationResult:
        """Validate CSV format."""
        result = FormatValidationResult()
        result.schema_version = "Calibrix CSV v1.0"
        
        if not self._validate_file_exists(file_path):
            result.add_error("CSV file does not exist", "file", "FILE_NOT_FOUND")
            return result
        
        try:
            with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
                # Detect delimiter
                sample = csvfile.read(1024)
                csvfile.seek(0)
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter
                
                reader = csv.DictReader(csvfile, delimiter=delimiter)
                
                # Validate headers
                self._validate_csv_headers(reader.fieldnames, result)
                
                # Validate rows
                rows = list(reader)
                self._validate_csv_rows(rows, result)
                
                result.format_specific_data = {
                    'row_count': len(rows),
                    'column_count': len(reader.fieldnames) if reader.fieldnames else 0,
                    'delimiter': delimiter,
                    'columns': reader.fieldnames
                }
                
        except Exception as e:
            result.add_error(f"CSV validation error: {e}", "csv", "VALIDATION_ERROR")
        
        return result
    
    def _validate_csv_headers(self, fieldnames: List[str], result: FormatValidationResult):
        """Validate CSV column headers."""
        if not fieldnames:
            result.add_error("No column headers found", "csv.headers", "NO_HEADERS")
            return
        
        # Check required columns
        missing_columns = []
        for required_col in self.REQUIRED_COLUMNS:
            if required_col not in fieldnames:
                missing_columns.append(required_col)
        
        if missing_columns:
            result.add_error(f"Missing required columns: {', '.join(missing_columns)}", 
                           "csv.headers", "MISSING_COLUMNS")
        
        # Check for duplicate columns
        if len(fieldnames) != len(set(fieldnames)):
            duplicates = [col for col in fieldnames if fieldnames.count(col) > 1]
            result.add_error(f"Duplicate columns: {', '.join(set(duplicates))}", 
                           "csv.headers", "DUPLICATE_COLUMNS")
    
    def _validate_csv_rows(self, rows: List[Dict[str, str]], result: FormatValidationResult):
        """Validate CSV data rows."""
        if not rows:
            result.add_warning("CSV file is empty", "csv.data", "EMPTY_DATA")
            return
        
        for i, row in enumerate(rows[:1000]):  # Sample first 1000 rows
            # Validate required fields are not empty
            for col in self.REQUIRED_COLUMNS:
                if col in row and not row[col].strip():
                    result.add_error(f"Row {i+1}: Empty value in required column {col}", 
                                   f"csv.data[{i+1}].{col}", "EMPTY_REQUIRED_FIELD")
            
            # Validate data types
            self._validate_row_data_types(row, i+1, result)
    
    def _validate_row_data_types(self, row: Dict[str, str], row_num: int, result: FormatValidationResult):
        """Validate data types in a CSV row."""
        # Validate numeric fields
        numeric_fields = ['detection_id', 'frame_number', 'confidence_score', 
                         'bbox_x', 'bbox_y', 'bbox_width', 'bbox_height']
        
        for field in numeric_fields:
            if field in row and row[field].strip():
                try:
                    value = float(row[field])
                    
                    # Specific validations
                    if field == 'confidence_score':
                        if not (0 <= value <= 1):
                            result.add_error(f"Row {row_num}: confidence_score must be between 0 and 1", 
                                           f"csv.data[{row_num}].{field}", "INVALID_CONFIDENCE")
                    
                    elif field in ['bbox_width', 'bbox_height']:
                        if value <= 0:
                            result.add_error(f"Row {row_num}: {field} must be positive", 
                                           f"csv.data[{row_num}].{field}", "INVALID_SIZE")
                    
                    elif field in ['detection_id', 'frame_number']:
                        if value < 0 or value != int(value):
                            result.add_error(f"Row {row_num}: {field} must be non-negative integer", 
                                           f"csv.data[{row_num}].{field}", "INVALID_ID")
                
                except ValueError:
                    result.add_error(f"Row {row_num}: {field} must be numeric", 
                                   f"csv.data[{row_num}].{field}", "INVALID_NUMERIC")
        
        # Validate boolean fields
        if 'is_confirmed' in row and row['is_confirmed'].strip():
            if row['is_confirmed'].lower() not in ['true', 'false', '1', '0', 'yes', 'no']:
                result.add_error(f"Row {row_num}: is_confirmed must be boolean", 
                               f"csv.data[{row_num}].is_confirmed", "INVALID_BOOLEAN")
    
    def get_supported_extensions(self) -> List[str]:
        """Get supported file extensions."""
        return ['.csv']


class FormatValidatorFactory:
    """Factory for creating format-specific validators."""
    
    VALIDATORS = {
        'coco': COCOValidator,
        'yolo': YOLOValidator,
        'pascal_voc': PascalVOCValidator,
        'csv': CSVValidator
    }
    
    @classmethod
    def create_validator(cls, format_name: str) -> BaseFormatValidator:
        """Create a validator for the specified format."""
        if format_name not in cls.VALIDATORS:
            raise ValueError(f"Unsupported format: {format_name}")
        
        return cls.VALIDATORS[format_name]()
    
    @classmethod
    def get_supported_formats(cls) -> List[str]:
        """Get list of supported formats."""
        return list(cls.VALIDATORS.keys())
    
    @classmethod
    def validate_file(cls, file_path: str, format_name: str) -> FormatValidationResult:
        """Validate a file with the appropriate validator."""
        validator = cls.create_validator(format_name)
        return validator.validate(file_path)