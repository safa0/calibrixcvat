# Ground Truth Export API Reference

## Overview

The Ground Truth Export API provides RESTful endpoints for exporting detection results from the Calibrix Matching system. It supports multiple formats, quality control, history tracking, and asynchronous processing.

## Base URL

```
/api/calibrix/ground-truth/
```

## Authentication

All endpoints require authentication. Use your CVAT session authentication or API token:

```bash
# Using session authentication
curl -H "X-CSRFToken: your-csrf-token" \
     -H "Cookie: sessionid=your-session-id" \
     -X POST "http://localhost:8080/api/calibrix/ground-truth/export/"

# Using API token (if implemented)
curl -H "Authorization: Token your-api-token" \
     -X POST "http://localhost:8080/api/calibrix/ground-truth/export/"
```

## Export Endpoints

### Create Export

Create a new ground truth export.

**POST** `/api/calibrix/ground-truth/export/`

#### Request Body

```json
{
  "task_id": 123,
  "export_format": "coco",
  "confirmed_only": true,
  "min_confidence": 0.8,
  "roi_template_id": 456,
  "dataset_split": {
    "train": 0.7,
    "val": 0.2,
    "test": 0.1
  },
  "compression_format": "zip",
  "include_images": false,
  "streaming_export": false,
  "batch_size": 100,
  "check_duplicates": true
}
```

#### Request Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `task_id` | integer | Yes | ID of the task to export |
| `export_format` | string | Yes | Export format: `coco`, `yolo`, `pascal_voc`, `cvat_xml`, `csv` |
| `confirmed_only` | boolean | No | Only export confirmed detections (default: true) |
| `min_confidence` | float | No | Minimum confidence threshold 0.0-1.0 |
| `roi_template_id` | integer | No | Filter by specific ROI template |
| `dataset_split` | object | No | Split configuration with train/val/test ratios |
| `compression_format` | string | No | Compression: `zip`, `tar.gz`, `none` (default: zip) |
| `include_images` | boolean | No | Include image files in export (default: false) |
| `streaming_export` | boolean | No | Enable for large datasets (default: false) |
| `batch_size` | integer | No | Processing batch size (default: 100) |
| `check_duplicates` | boolean | No | Check for recent similar exports (default: true) |

#### Response

```json
{
  "status": "completed",
  "export_id": "12345678-1234-5678-9abc-123456789abc",
  "export_path": "/exports/coco_export_1234567890.json",
  "download_url": "/api/calibrix/ground-truth/download/12345678-1234-5678-9abc-123456789abc/",
  "total_detections": 150,
  "file_size_bytes": 2048576,
  "duration_seconds": 12.5,
  "export_format": "coco",
  "history_tracked": true,
  "export_history": {
    "export_id": "12345678-1234-5678-9abc-123456789abc",
    "format": "coco",
    "status": "COMPLETED",
    "total_detections": 150,
    "file_size_mb": 1.95,
    "duration_seconds": 12.5,
    "created_at": "2024-01-15T10:30:00Z",
    "completed_at": "2024-01-15T10:30:12Z"
  }
}
```

#### Error Responses

```json
// Configuration error (400)
{
  "error": "Invalid export configuration",
  "details": {
    "is_valid": false,
    "errors": [
      {
        "field": "min_confidence",
        "message": "min_confidence must be between 0 and 1",
        "code": "INVALID_VALUE"
      }
    ]
  }
}

// Duplicate found (409)
{
  "status": "duplicate_found",
  "message": "Similar export found recently",
  "similar_exports": [
    {
      "export_id": "87654321-4321-8765-cba9-987654321cba",
      "format": "coco",
      "created_at": "2024-01-15T09:45:00Z",
      "total_detections": 150
    }
  ]
}

// No data (404)
{
  "error": "No detections found",
  "message": "No detections match the specified criteria",
  "suggestions": [
    "Set confirmed_only=false",
    "Lower min_confidence threshold",
    "Remove roi_template_id filter"
  ]
}
```

### Get Export Status

Check the status of an export operation.

**GET** `/api/calibrix/ground-truth/export/{export_id}/status/`

#### Response

```json
{
  "export_id": "12345678-1234-5678-9abc-123456789abc",
  "status": "IN_PROGRESS",
  "format": "coco",
  "total_detections": 150,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:02Z",
  "elapsed_seconds": 8.5,
  "estimated_remaining_seconds": 4.2,
  "estimated_completion": "2024-01-15T10:30:15Z"
}
```

### Download Export

Download the exported file.

**GET** `/api/calibrix/ground-truth/download/{export_id}/`

#### Response Headers

```
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="coco_export_1234567890.json"
Content-Length: 2048576
```

### Cancel Export

Cancel a running export operation.

**DELETE** `/api/calibrix/ground-truth/export/{export_id}/`

#### Response

```json
{
  "message": "Export cancelled successfully",
  "export_id": "12345678-1234-5678-9abc-123456789abc"
}
```

## History Endpoints

### Get Export History

Retrieve export history for a task.

**GET** `/api/calibrix/ground-truth/history/`

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | integer | Required. Filter by task ID |
| `limit` | integer | Number of records to return (default: 50, max: 200) |
| `format` | string | Filter by export format |
| `status` | string | Filter by status: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `user` | integer | Filter by user ID |
| `include_archived` | boolean | Include archived exports (default: false) |

#### Response

```json
{
  "count": 25,
  "next": "/api/calibrix/ground-truth/history/?task_id=123&limit=10&offset=10",
  "previous": null,
  "results": [
    {
      "export_id": "12345678-1234-5678-9abc-123456789abc",
      "format": "coco",
      "status": "COMPLETED",
      "total_detections": 150,
      "file_size_mb": 1.95,
      "duration_seconds": 12.5,
      "created_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:12Z",
      "created_by": "username",
      "is_incremental": false,
      "download_count": 3
    }
  ]
}
```

### Get Export Statistics

Get comprehensive statistics about exports for a task.

**GET** `/api/calibrix/ground-truth/statistics/`

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | integer | Required. Task ID to get statistics for |

#### Response

```json
{
  "task_id": 123,
  "task_name": "Sample Task",
  "total_exports": 25,
  "successful_exports": 23,
  "failed_exports": 1,
  "in_progress_exports": 1,
  "success_rate": 92.0,
  "format_distribution": {
    "coco": 12,
    "yolo": 8,
    "csv": 5
  },
  "user_activity": {
    "user1": 15,
    "user2": 8,
    "user3": 2
  },
  "performance_statistics": {
    "avg_duration": 8.5,
    "min_duration": 2.1,
    "max_duration": 45.2,
    "avg_processing_rate": 125.3,
    "total_detections_exported": 3750,
    "total_files_size": 52428800
  },
  "recent_activity": {
    "exports_last_24h": 3,
    "exports_last_week": 12,
    "successful_last_week": 11
  }
}
```

## Incremental Export Endpoints

### Create Incremental Export

Create an incremental export based on a previous export.

**POST** `/api/calibrix/ground-truth/export/incremental/`

#### Request Body

```json
{
  "task_id": 123,
  "base_export_id": "87654321-4321-8765-cba9-987654321cba",
  "export_format": "coco",
  "confirmed_only": true,
  "min_confidence": 0.8
}
```

#### Response

```json
{
  "status": "completed",
  "export_id": "12345678-1234-5678-9abc-123456789abc",
  "is_incremental": true,
  "base_export_id": "87654321-4321-8765-cba9-987654321cba",
  "diff_info": {
    "base_export_date": "2024-01-14T15:30:00Z",
    "base_detection_count": 120,
    "current_detection_count": 150,
    "new_detections_since_base": 30,
    "change_percentage": 25.0
  },
  "export_path": "/exports/incremental_coco_1234567890.json",
  "download_url": "/api/calibrix/ground-truth/download/12345678-1234-5678-9abc-123456789abc/"
}
```

### Get Incremental Candidates

Get exports that can be used as base for incremental exports.

**GET** `/api/calibrix/ground-truth/incremental-candidates/`

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | integer | Required. Task ID |

#### Response

```json
{
  "candidates": [
    {
      "export_id": "87654321-4321-8765-cba9-987654321cba",
      "format": "coco",
      "status": "COMPLETED",
      "total_detections": 120,
      "created_at": "2024-01-14T15:30:00Z",
      "is_suitable": true,
      "potential_savings": "75% of processing time"
    }
  ]
}
```

## Validation Endpoints

### Validate Configuration

Validate an export configuration before creating the export.

**POST** `/api/calibrix/ground-truth/validate-config/`

#### Request Body

```json
{
  "task_id": 123,
  "export_format": "coco",
  "confirmed_only": true,
  "min_confidence": 1.5
}
```

#### Response

```json
{
  "is_valid": false,
  "errors": [
    {
      "field": "min_confidence",
      "message": "min_confidence must be between 0 and 1",
      "code": "INVALID_VALUE"
    }
  ],
  "warnings": [],
  "info": [
    {
      "field": "detections",
      "message": "150 detections will be exported"
    }
  ]
}
```

### Validate Export File

Validate an exported file against format specifications.

**POST** `/api/calibrix/ground-truth/validate-file/`

#### Request (Multipart Form)

```
Content-Type: multipart/form-data

file: [exported file]
format: coco
```

#### Response

```json
{
  "is_valid": true,
  "schema_version": "COCO 1.0",
  "errors": [],
  "warnings": [],
  "info": [
    {
      "message": "JSON file loaded successfully",
      "data": {
        "size_bytes": 2048576
      }
    }
  ],
  "format_specific_data": {
    "image_count": 75,
    "annotation_count": 150,
    "category_count": 3,
    "has_segmentation": false,
    "has_keypoints": false
  }
}
```

## Recommendations Endpoint

### Get Export Recommendations

Get recommendations for optimizing an export configuration.

**POST** `/api/calibrix/ground-truth/recommendations/`

#### Request Body

```json
{
  "task_id": 123,
  "export_format": "yolo",
  "compression_format": "none",
  "include_images": true
}
```

#### Response

```json
{
  "config_suggestions": [
    {
      "type": "compression",
      "message": "YOLO exports create many files. Compression recommended.",
      "suggestion": "Set compression_format=\"zip\"",
      "severity": "tip"
    }
  ],
  "performance_tips": [
    {
      "type": "image_inclusion",
      "message": "Including images with large datasets significantly increases export size and time.",
      "suggestion": "Consider exporting without images for faster processing",
      "severity": "warning"
    }
  ],
  "similar_exports": [
    {
      "export_id": "87654321-4321-8765-cba9-987654321cba",
      "format": "yolo",
      "created_at": "2024-01-14T15:30:00Z"
    }
  ],
  "incremental_candidates": [
    {
      "export_id": "87654321-4321-8765-cba9-987654321cba",
      "potential_savings": "60% of processing time"
    }
  ]
}
```

## WebSocket API (Optional)

For real-time progress updates during export operations.

### Connect to Export Progress

```javascript
const ws = new WebSocket('ws://localhost:8080/ws/calibrix/export-progress/');

ws.onopen = function(event) {
    // Subscribe to export progress
    ws.send(JSON.stringify({
        'action': 'subscribe',
        'export_id': '12345678-1234-5678-9abc-123456789abc'
    }));
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Progress:', data);
    // {
    //   "export_id": "12345678-1234-5678-9abc-123456789abc",
    //   "progress": 65,
    //   "message": "Processing annotations...",
    //   "status": "IN_PROGRESS"
    // }
};
```

## SDK Examples

### Python SDK

```python
import requests
from typing import Optional, Dict, Any

class CalibriBGround TruthExportClient:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url.rstrip('/')
        self.headers = {'Authorization': f'Token {auth_token}'}
    
    def create_export(
        self,
        task_id: int,
        export_format: str,
        confirmed_only: bool = True,
        min_confidence: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Create a new export."""
        data = {
            'task_id': task_id,
            'export_format': export_format,
            'confirmed_only': confirmed_only,
            **kwargs
        }
        
        if min_confidence is not None:
            data['min_confidence'] = min_confidence
        
        response = requests.post(
            f'{self.base_url}/api/calibrix/ground-truth/export/',
            json=data,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_export_status(self, export_id: str) -> Dict[str, Any]:
        """Get export status."""
        response = requests.get(
            f'{self.base_url}/api/calibrix/ground-truth/export/{export_id}/status/',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def download_export(self, export_id: str, output_path: str):
        """Download export file."""
        response = requests.get(
            f'{self.base_url}/api/calibrix/ground-truth/download/{export_id}/',
            headers=self.headers,
            stream=True
        )
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

# Usage
client = GroundTruthExportClient('http://localhost:8080', 'your-token')

# Create export
result = client.create_export(
    task_id=123,
    export_format='coco',
    confirmed_only=True,
    min_confidence=0.8,
    compression_format='zip'
)

print(f"Export created: {result['export_id']}")

# Download when ready
if result['status'] == 'completed':
    client.download_export(result['export_id'], 'export.zip')
```

### JavaScript SDK

```javascript
class GroundTruthExportClient {
    constructor(baseUrl, authToken) {
        this.baseUrl = baseUrl.replace(/\/$/, '');
        this.headers = {
            'Authorization': `Token ${authToken}`,
            'Content-Type': 'application/json'
        };
    }

    async createExport(config) {
        const response = await fetch(`${this.baseUrl}/api/calibrix/ground-truth/export/`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }

    async getExportStatus(exportId) {
        const response = await fetch(`${this.baseUrl}/api/calibrix/ground-truth/export/${exportId}/status/`, {
            headers: this.headers
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    }

    async downloadExport(exportId) {
        const response = await fetch(`${this.baseUrl}/api/calibrix/ground-truth/download/${exportId}/`, {
            headers: { 'Authorization': this.headers.Authorization }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.blob();
    }

    async pollExportStatus(exportId, intervalMs = 2000) {
        return new Promise((resolve, reject) => {
            const poll = async () => {
                try {
                    const status = await this.getExportStatus(exportId);
                    
                    if (status.status === 'COMPLETED') {
                        resolve(status);
                    } else if (status.status === 'FAILED') {
                        reject(new Error(`Export failed: ${status.error_message}`));
                    } else {
                        setTimeout(poll, intervalMs);
                    }
                } catch (error) {
                    reject(error);
                }
            };
            
            poll();
        });
    }
}

// Usage
const client = new GroundTruthExportClient('http://localhost:8080', 'your-token');

async function exportAndDownload() {
    try {
        // Create export
        const result = await client.createExport({
            task_id: 123,
            export_format: 'coco',
            confirmed_only: true,
            min_confidence: 0.8
        });

        console.log(`Export started: ${result.export_id}`);

        // Poll for completion
        const finalStatus = await client.pollExportStatus(result.export_id);
        console.log('Export completed!');

        // Download
        const blob = await client.downloadExport(result.export_id);
        
        // Create download link
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'export.zip';
        a.click();
        window.URL.revokeObjectURL(url);
        
    } catch (error) {
        console.error('Export failed:', error);
    }
}
```

## Rate Limits

- **Export Creation**: 10 requests per minute per user
- **Status Checks**: 60 requests per minute per user  
- **Downloads**: 30 requests per minute per user
- **History/Statistics**: 30 requests per minute per user

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1642262400
```

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Authentication required |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource not found |
| 409 | Conflict - Duplicate export found |
| 413 | Payload Too Large - Export too large |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable - Export service overloaded |

## Webhook Configuration

Configure webhooks to receive notifications about export events:

```json
POST /api/calibrix/ground-truth/webhooks/

{
  "url": "https://your-app.com/webhooks/export-events",
  "events": ["export.completed", "export.failed"],
  "secret": "your-webhook-secret"
}
```

Webhook payload example:

```json
{
  "event": "export.completed",
  "timestamp": "2024-01-15T10:30:12Z",
  "export_id": "12345678-1234-5678-9abc-123456789abc",
  "task_id": 123,
  "export_format": "coco",
  "total_detections": 150,
  "file_size_bytes": 2048576,
  "duration_seconds": 12.5,
  "download_url": "https://your-cvat.com/api/calibrix/ground-truth/download/12345678-1234-5678-9abc-123456789abc/"
}
```