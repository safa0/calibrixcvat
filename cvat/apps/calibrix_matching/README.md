# Calibrix Matching Django App

This Django app provides computer vision feature matching functionality for the CVAT annotation platform. It allows users to create ROI templates with feature descriptors and perform automated matching across video frames.

## Models

### ROITemplate
Stores Region of Interest templates with feature descriptors for matching.

**Fields:**
- `name`: Template name (max 255 characters)
- `task`: Foreign key to CVAT Task model
- `coordinates`: JSON field with bounding box coordinates {x, y, width, height}
- `feature_descriptor`: JSON field with feature data (algorithm, keypoints, descriptors)
- `created_by`: Foreign key to User model (nullable)
- `created_at`: Auto-generated timestamp

### MatchingSession
Represents a matching session that uses an ROI template to find matches in video frames.

**Fields:**
- `roi_template`: Foreign key to ROITemplate
- `task`: Foreign key to CVAT Task model
- `algorithm_type`: Algorithm choice (SIFT, SURF, ORB, AKAZE)
- `threshold`: Matching threshold between 0.0 and 1.0
- `status`: Session status (PENDING, IN_PROGRESS, COMPLETED, FAILED)
- `created_at`: Auto-generated timestamp
- `updated_at`: Auto-updated timestamp

### DetectionResult
Stores detection results from matching sessions.

**Fields:**
- `matching_session`: Foreign key to MatchingSession
- `frame_number`: Positive integer for video frame number
- `coordinates`: JSON field with detected bounding box coordinates
- `confidence_score`: Score between 0.0 and 1.0
- `is_confirmed`: Boolean flag for user confirmation
- `created_at`: Auto-generated timestamp

**Constraints:**
- Unique constraint on (matching_session, frame_number)
- Default ordering by frame_number

## Admin Interface

The app includes comprehensive Django admin interfaces for all models with:
- List displays with relevant fields
- Filtering and search capabilities
- Custom actions (mark sessions as completed/failed, confirm/unconfirm detections)
- Optimized querysets with select_related

## Database Migrations

Run the following commands to apply the database schema:

```bash
python manage.py makemigrations calibrix_matching
python manage.py migrate calibrix_matching
```

## Testing

The app includes comprehensive unit tests covering:
- Model creation and validation
- Field constraints and relationships
- Cascade deletion behavior
- Custom validation methods
- Edge cases and error conditions

Run tests with:
```bash
python manage.py test cvat.apps.calibrix_matching.tests
```

## Usage Example

```python
from cvat.apps.calibrix_matching.models import ROITemplate, MatchingSession, DetectionResult
from cvat.apps.engine.models import Task
from django.contrib.auth.models import User

# Create ROI template
roi_template = ROITemplate.objects.create(
    name="Face Template",
    task=task,
    coordinates={"x": 100, "y": 100, "width": 200, "height": 200},
    feature_descriptor={
        "algorithm": "SIFT",
        "keypoints": [...],
        "descriptors": [...]
    },
    created_by=user
)

# Create matching session
session = MatchingSession.objects.create(
    roi_template=roi_template,
    task=task,
    algorithm_type="SIFT",
    threshold=0.8
)

# Store detection results
result = DetectionResult.objects.create(
    matching_session=session,
    frame_number=42,
    coordinates={"x": 150, "y": 150, "width": 180, "height": 180},
    confidence_score=0.85
)
```

## Integration Notes

- Models are properly integrated with CVAT's existing Task and User models
- Foreign key relationships use appropriate cascade behaviors
- All models follow CVAT's naming conventions and patterns
- Admin interfaces follow CVAT's admin patterns
- Comprehensive validation ensures data integrity