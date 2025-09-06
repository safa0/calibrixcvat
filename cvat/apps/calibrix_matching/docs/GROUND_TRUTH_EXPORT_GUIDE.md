# Ground Truth Export Agent - Comprehensive Guide

## Overview

The Ground Truth Export Agent is a comprehensive system for exporting confirmed detection results from the Calibrix Matching system into various standardized annotation formats. It supports multiple export formats, quality control validation, dataset splitting, incremental exports, and detailed history tracking.

## Features

### ✅ Supported Export Formats

- **COCO JSON** - Complete COCO-compliant format with images, annotations, and categories
- **YOLO** - Directory structure with label files and data.yaml configuration  
- **Pascal VOC XML** - XML annotation files with bounding box information
- **CVAT XML** - Native CVAT XML format with complete metadata
- **CSV** - Tabular format with configurable columns

### ✅ Core Capabilities

- **Quality Control** - Automatic validation of detection data and export formats
- **Dataset Splitting** - Train/validation/test splits with proper frame grouping
- **Incremental Exports** - Export only new detections since a previous export
- **History Tracking** - Complete audit trail of all export operations
- **Background Processing** - Asynchronous export jobs with progress tracking
- **Compression Support** - ZIP and TAR.GZ compression for exported files
- **Format Validation** - Schema compliance checking for all export formats

## Quick Start

### Basic Export

```python
from cvat.apps.calibrix_matching.services.enhanced_export_service import EnhancedGroundTruthExportService
from cvat.apps.calibrix_matching.services.ground_truth_export import ExportConfig

# Initialize the service
service = EnhancedGroundTruthExportService(task_id=123)

# Configure export
config = ExportConfig(
    export_format='coco',           # Export format
    confirmed_only=True,            # Only confirmed detections
    min_confidence=0.8,             # Minimum confidence threshold
    compression_format='zip'        # Compress output
)

# Perform export with history tracking
result = service.export_with_history(config=config, user=request.user)

print(f"Export completed: {result['export_path']}")
print(f"Export ID: {result['export_id']}")
```

### Dataset Splitting

```python
# Configure dataset splitting
config = ExportConfig(
    export_format='yolo',
    confirmed_only=True,
    dataset_split={
        'train': 0.7,
        'val': 0.2,
        'test': 0.1
    },
    compression_format='zip'
)

result = service.export_with_history(config=config, user=request.user)
```

### Incremental Export

```python
# Find base export for incremental update
history_service = ExportHistoryService(task_id=123)
base_exports = history_service.get_incremental_export_candidates()

if base_exports:
    # Export only new detections since base export
    result = service.export_incremental(
        config=config,
        base_export_id=base_exports[0].export_id,
        user=request.user
    )
    
    if result['status'] == 'no_changes':
        print("No new detections to export")
    else:
        print(f"Incremental export: {result['export_path']}")
```

## Export Configuration

### ExportConfig Parameters

```python
config = ExportConfig(
    # Required
    export_format='coco',                    # Format: coco, yolo, pascal_voc, cvat_xml, csv
    
    # Filtering
    confirmed_only=True,                     # Only export confirmed detections
    min_confidence=0.8,                      # Minimum confidence threshold (0.0-1.0)
    roi_template_id=456,                     # Filter by specific ROI template
    
    # Dataset options
    dataset_split={'train': 0.8, 'val': 0.2},  # Split dataset
    include_images=False,                    # Include image files in export
    normalize_coordinates=True,              # Normalize coordinates to [0,1]
    
    # Processing options
    compression_format='zip',                # Compression: zip, tar.gz, none
    streaming_export=False,                  # Enable for large datasets
    batch_size=100,                         # Processing batch size
    
    # Metadata
    include_metadata=True,                   # Include export metadata
    output_directory='/path/to/output'       # Custom output directory
)
```

### Format-Specific Options

#### COCO Export
```python
config = ExportConfig(
    export_format='coco',
    include_metadata=True,        # Include info section
    normalize_coordinates=False   # Use absolute coordinates
)
```

#### YOLO Export
```python
config = ExportConfig(
    export_format='yolo',
    normalize_coordinates=True,   # Required for YOLO
    compression_format='zip'      # Recommended for multiple files
)
```

#### Pascal VOC Export
```python
config = ExportConfig(
    export_format='pascal_voc',
    include_metadata=True,        # Include source and size info
    compression_format='tar.gz'
)
```

## Quality Control and Validation

### Automatic Quality Checks

```python
from cvat.apps.calibrix_matching.services.ground_truth_export import QualityControlValidator

validator = QualityControlValidator()

# Generate quality report
detections = service.get_detection_queryset(confirmed_only=False)
quality_report = validator.generate_quality_report(detections)

print(f"Total detections: {quality_report['total_detections']}")
print(f"Valid detections: {quality_report['valid_detections']}")
print(f"Duplicate detections: {len(quality_report['duplicate_detections'])}")
```

### Format Validation

```python
from cvat.apps.calibrix_matching.services.format_validators import FormatValidatorFactory

# Validate exported file
result = FormatValidatorFactory.validate_file('/path/to/export.json', 'coco')

if result.is_valid:
    print("Export format is valid")
    print(f"Statistics: {result.format_specific_data}")
else:
    print("Validation errors found:")
    for error in result.errors:
        print(f"- {error['message']}")
```

### Export Configuration Validation

```python
# Validate configuration before export
validation_result = service.validate_export_config(config)

if not validation_result['is_valid']:
    print("Configuration errors:")
    for error in validation_result['errors']:
        print(f"- {error['message']}")
```

## Export History and Tracking

### Viewing Export History

```python
from cvat.apps.calibrix_matching.services.export_history_service import ExportHistoryService

history_service = ExportHistoryService(task_id=123)

# Get recent exports
recent_exports = history_service.get_export_history(
    limit=10,
    format_filter='coco',
    status_filter='COMPLETED'
)

for export in recent_exports:
    print(f"Export {export.export_id}: {export.export_format} - {export.status}")
    print(f"  Created: {export.created_at}")
    print(f"  Detections: {export.total_detections}")
    print(f"  File size: {export.file_size_mb:.1f} MB")
```

### Export Statistics

```python
# Get comprehensive statistics
stats = history_service.get_export_statistics()

print(f"Total exports: {stats['total_exports']}")
print(f"Success rate: {stats['success_rate']:.1f}%")
print(f"Format distribution: {stats['format_distribution']}")
print(f"Performance: {stats['performance_statistics']}")
```

### Tracking Downloads

```python
# Record download event
download = history_service.record_download(
    export_id=export_uuid,
    user=request.user,
    ip_address=request.META.get('REMOTE_ADDR'),
    user_agent=request.META.get('HTTP_USER_AGENT'),
    bytes_served=file_size,
    completed=True
)

# Get download statistics
download_stats = history_service.get_download_statistics(export_id)
print(f"Total downloads: {download_stats['total_downloads']}")
print(f"Unique users: {download_stats['unique_users']}")
```

## Advanced Features

### Export Recommendations

```python
# Get recommendations for optimizing export
recommendations = service.get_export_recommendations(config)

print("Configuration suggestions:")
for suggestion in recommendations['config_suggestions']:
    print(f"- {suggestion['message']}")

print("Performance tips:")
for tip in recommendations['performance_tips']:
    print(f"- {tip['message']}")

if recommendations['similar_exports']:
    print("Similar recent exports found - consider reusing")
```

### Progress Tracking

```python
# Monitor export progress
export_record = history_service.create_export_record('coco', config, user)
export_id = export_record.export_id

# Check progress
progress = service.get_export_progress(export_id)
print(f"Status: {progress['status']}")
if 'estimated_remaining_seconds' in progress:
    print(f"ETA: {progress['estimated_remaining_seconds']} seconds")
```

### Export Cancellation

```python
# Cancel running export
success = service.cancel_export(export_id, user)
if success:
    print("Export cancelled successfully")
```

## Background Processing

### Asynchronous Exports

```python
# Start background export job
job_id = service.export_async(config)
print(f"Started background job: {job_id}")

# Check job status (if using RQ)
try:
    from rq import Queue
    from django_rq import get_queue
    
    queue = get_queue('default')
    job = queue.get_job(job_id)
    
    print(f"Job status: {job.get_status()}")
    if job.meta:
        print(f"Progress: {job.meta.get('progress', 0)}%")
        print(f"Message: {job.meta.get('message', '')}")
except ImportError:
    print("RQ not available - using synchronous processing")
```

## Format Specifications

### COCO Format

```json
{
  "info": {
    "description": "CVAT Calibrix Matching Export",
    "version": "1.0",
    "year": 2024
  },
  "images": [
    {
      "id": 1,
      "width": 1920,
      "height": 1080,
      "file_name": "frame_000000.jpg",
      "frame_number": 0
    }
  ],
  "annotations": [
    {
      "id": 1,
      "image_id": 1,
      "category_id": 1,
      "bbox": [100, 100, 200, 150],
      "area": 30000,
      "confidence_score": 0.85,
      "is_confirmed": true
    }
  ],
  "categories": [
    {
      "id": 1,
      "name": "roi_template_name",
      "supercategory": "detection"
    }
  ]
}
```

### YOLO Format

Directory structure:
```
yolo_export/
├── images/          # Optional - image files
├── labels/          # Label files (.txt)
│   ├── frame_000000.txt
│   └── frame_000005.txt
└── data.yaml        # Configuration file
```

Label file format (normalized coordinates):
```
0 0.5 0.5 0.2 0.3    # class_id center_x center_y width height
1 0.7 0.2 0.1 0.4
```

data.yaml:
```yaml
nc: 2
names: ['class0', 'class1']
path: /path/to/dataset
train: images
val: images
```

### Pascal VOC Format

```xml
<?xml version="1.0" encoding="UTF-8"?>
<annotation>
    <filename>frame_000000.jpg</filename>
    <source>
        <database>CVAT Calibrix</database>
    </source>
    <size>
        <width>1920</width>
        <height>1080</height>
        <depth>3</depth>
    </size>
    <object>
        <name>roi_template_name</name>
        <pose>Unspecified</pose>
        <truncated>0</truncated>
        <difficult>0</difficult>
        <confidence>0.85</confidence>
        <confirmed>true</confirmed>
        <bndbox>
            <xmin>100</xmin>
            <ymin>100</ymin>
            <xmax>300</xmax>
            <ymax>250</ymax>
        </bndbox>
    </object>
</annotation>
```

### CSV Format

```csv
detection_id,frame_number,confidence_score,is_confirmed,bbox_x,bbox_y,bbox_width,bbox_height,roi_template_name,task_name
1,0,0.85,True,100,100,200,150,template1,test_task
2,5,0.92,True,200,150,180,120,template1,test_task
```

## Error Handling

### Common Errors and Solutions

#### No Detections Found
```python
if result['total_detections'] == 0:
    print("No detections match the criteria")
    print("Try adjusting filters:")
    print("- Set confirmed_only=False")  
    print("- Lower min_confidence threshold")
    print("- Remove roi_template_id filter")
```

#### Validation Errors
```python
try:
    result = service.export_with_history(config, user)
except ValueError as e:
    print(f"Configuration error: {e}")
    # Check validation_result for details
```

#### Format-Specific Issues
```python
# YOLO: Coordinates must be normalized
if config.export_format == 'yolo':
    config.normalize_coordinates = True

# Large datasets: Enable streaming
if detection_count > 10000:
    config.streaming_export = True
    config.batch_size = 500
```

## Performance Optimization

### Large Datasets

```python
# For datasets with >10,000 detections
config = ExportConfig(
    export_format='csv',
    streaming_export=True,        # Process in batches
    batch_size=1000,             # Larger batch size
    include_images=False,        # Skip images for speed
    compression_format='none'    # Skip compression
)
```

### Memory Management

```python
# Monitor memory usage
import tracemalloc

tracemalloc.start()
result = service.export_with_history(config, user)
current, peak = tracemalloc.get_traced_memory()
print(f"Memory usage: {peak / 1024 / 1024:.1f} MB peak")
tracemalloc.stop()
```

### Caching and Reuse

```python
# Check for similar recent exports
similar = history_service.find_similar_exports(config, time_window_hours=24)
if similar:
    print(f"Similar export available: {similar[0].export_path}")
    # Consider reusing instead of re-exporting
```

## Maintenance and Cleanup

### Automatic Cleanup

```python
# Archive old exports
archived_count = history_service.archive_old_exports(days_old=30)
print(f"Archived {archived_count} old exports")

# Delete expired exports
deleted_records, deleted_files = history_service.cleanup_expired_exports()
print(f"Cleaned up {deleted_records} records and {deleted_files} files")
```

### Manual Cleanup

```python
# Set custom auto-delete dates
export_record.auto_delete_at = timezone.now() + timedelta(days=7)
export_record.save()

# Archive specific export
export_record.is_archived = True
export_record.archived_at = timezone.now()
export_record.save()
```

## Troubleshooting

### Debug Mode

```python
import logging
logging.getLogger('cvat.apps.calibrix_matching.services').setLevel(logging.DEBUG)
```

### Common Issues

1. **Export appears empty**: Check filter settings (confirmed_only, min_confidence)
2. **Format validation fails**: Verify output format compliance
3. **Large file sizes**: Enable compression or exclude images
4. **Slow performance**: Use streaming export and adjust batch size
5. **Memory errors**: Reduce batch size or use incremental exports

## API Integration

### REST API Usage

```python
# Export via API
import requests

response = requests.post('/api/calibrix/ground-truth/export/', {
    'task_id': 123,
    'export_format': 'coco',
    'confirmed_only': True,
    'min_confidence': 0.8,
    'compression_format': 'zip'
})

export_data = response.json()
download_url = export_data['download_url']
```

### Webhook Integration

```python
# Set up export completion webhook
webhook_config = {
    'url': 'https://your-app.com/export-complete',
    'events': ['export.completed', 'export.failed']
}

# The webhook will receive:
# {
#   'event': 'export.completed',
#   'export_id': 'uuid',
#   'task_id': 123,
#   'export_path': '/path/to/file',
#   'total_detections': 150,
#   'duration_seconds': 12.5
# }
```

## Best Practices

### Export Configuration
- Always validate configuration before export
- Use appropriate compression for multi-file formats (YOLO, Pascal VOC)
- Consider dataset splitting for machine learning workflows
- Set reasonable confidence thresholds based on your use case

### Performance
- Use streaming export for large datasets (>10,000 detections)
- Avoid including images unless necessary
- Monitor memory usage during export
- Consider incremental exports for frequently updated datasets

### Quality Assurance
- Run quality control validation before export
- Validate export format compliance after export
- Check export statistics for completeness
- Maintain export history for audit trails

### Maintenance
- Set up automatic cleanup of old exports
- Monitor export failure rates
- Archive historical exports periodically
- Keep export configurations consistent across environments