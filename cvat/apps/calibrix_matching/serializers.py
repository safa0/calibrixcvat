# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field, extend_schema_serializer
from django.contrib.auth.models import User

from cvat.apps.engine.models import Task
from .models import ROITemplate, MatchingSession, DetectionResult


@extend_schema_serializer(
    component_name="ROITemplate"
)
class ROITemplateSerializer(serializers.ModelSerializer):
    """Serializer for ROI Template model."""
    
    created_by = serializers.PrimaryKeyRelatedField(
        read_only=True,
        default=serializers.CurrentUserDefault()
    )
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True
    )
    task_name = serializers.CharField(
        source='task.name',
        read_only=True
    )
    
    class Meta:
        model = ROITemplate
        fields = [
            'id', 'name', 'task', 'task_name', 'coordinates',
            'feature_descriptor', 'created_by', 'created_by_username',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']

    def validate_coordinates(self, value):
        """Validate coordinates structure."""
        required_fields = {'x', 'y', 'width', 'height'}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Coordinates must be a dictionary")
        
        missing_fields = required_fields - set(value.keys())
        if missing_fields:
            raise serializers.ValidationError(
                f"Coordinates must contain fields: {', '.join(missing_fields)}"
            )
        
        # Validate coordinate values are numeric
        for field in required_fields:
            coord_value = value.get(field)
            if not isinstance(coord_value, (int, float)):
                raise serializers.ValidationError(
                    f"Coordinate field '{field}' must be numeric"
                )
            if coord_value < 0:
                raise serializers.ValidationError(
                    f"Coordinate field '{field}' must be non-negative"
                )
        
        # Validate width and height are positive
        if value['width'] <= 0 or value['height'] <= 0:
            raise serializers.ValidationError("Width and height must be positive")
        
        return value

    def validate_feature_descriptor(self, value):
        """Validate feature descriptor structure."""
        required_fields = {'algorithm', 'keypoints', 'descriptors'}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Feature descriptor must be a dictionary")
        
        missing_fields = required_fields - set(value.keys())
        if missing_fields:
            raise serializers.ValidationError(
                f"Feature descriptor must contain fields: {', '.join(missing_fields)}"
            )
        
        # Validate algorithm
        valid_algorithms = ['SIFT', 'SURF', 'ORB', 'AKAZE']
        if value['algorithm'] not in valid_algorithms:
            raise serializers.ValidationError(
                f"Algorithm must be one of: {', '.join(valid_algorithms)}"
            )
        
        # Validate keypoints is a list
        if not isinstance(value['keypoints'], list):
            raise serializers.ValidationError("Keypoints must be a list")
        
        # Validate descriptors is a list
        if not isinstance(value['descriptors'], list):
            raise serializers.ValidationError("Descriptors must be a list")
        
        # Validate keypoints and descriptors have same length
        if len(value['keypoints']) != len(value['descriptors']):
            raise serializers.ValidationError(
                "Keypoints and descriptors must have the same length"
            )
        
        return value

    def create(self, validated_data):
        """Create ROI template with current user as creator."""
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


@extend_schema_serializer(
    component_name="MatchingSession"
)
class MatchingSessionSerializer(serializers.ModelSerializer):
    """Serializer for Matching Session model."""
    
    roi_template_name = serializers.CharField(
        source='roi_template.name',
        read_only=True
    )
    task_name = serializers.CharField(
        source='task.name',
        read_only=True
    )
    detection_count = serializers.SerializerMethodField()
    confirmed_detection_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MatchingSession
        fields = [
            'id', 'roi_template', 'roi_template_name', 'task', 'task_name',
            'algorithm_type', 'threshold', 'status', 'detection_count',
            'confirmed_detection_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    @extend_schema_field(serializers.IntegerField)
    def get_detection_count(self, obj):
        """Get total number of detection results for this session."""
        return obj.detection_results.count()
    
    @extend_schema_field(serializers.IntegerField)
    def get_confirmed_detection_count(self, obj):
        """Get number of confirmed detection results for this session."""
        return obj.detection_results.filter(is_confirmed=True).count()

    def validate_threshold(self, value):
        """Validate threshold is between 0.0 and 1.0."""
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError(
                "Threshold must be between 0.0 and 1.0"
            )
        return value

    def validate(self, attrs):
        """Validate that ROI template and task are compatible."""
        roi_template = attrs.get('roi_template')
        task = attrs.get('task')
        
        if roi_template and task:
            if roi_template.task_id != task.id:
                raise serializers.ValidationError(
                    "ROI template must belong to the specified task"
                )
        
        return attrs


@extend_schema_serializer(
    component_name="MatchingSessionStart"
)
class MatchingSessionStartSerializer(serializers.Serializer):
    """Serializer for starting a matching session."""
    
    frame_range = serializers.ListField(
        child=serializers.IntegerField(min_value=0),
        min_length=2,
        max_length=2,
        required=False,
        help_text="Optional frame range [start, end] to process. If not provided, processes all frames."
    )
    
    def validate_frame_range(self, value):
        """Validate frame range format."""
        if len(value) == 2:
            start, end = value
            if start >= end:
                raise serializers.ValidationError(
                    "Frame range start must be less than end"
                )
        return value


@extend_schema_serializer(
    component_name="DetectionResult"
)
class DetectionResultSerializer(serializers.ModelSerializer):
    """Serializer for Detection Result model."""
    
    matching_session_info = serializers.SerializerMethodField()
    roi_template_name = serializers.CharField(
        source='matching_session.roi_template.name',
        read_only=True
    )
    task_id = serializers.IntegerField(
        source='matching_session.task.id',
        read_only=True
    )
    
    class Meta:
        model = DetectionResult
        fields = [
            'id', 'matching_session', 'matching_session_info', 'roi_template_name',
            'task_id', 'frame_number', 'coordinates', 'confidence_score',
            'is_confirmed', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    @extend_schema_field(serializers.DictField)
    def get_matching_session_info(self, obj):
        """Get basic information about the matching session."""
        return {
            'id': obj.matching_session.id,
            'algorithm_type': obj.matching_session.algorithm_type,
            'threshold': obj.matching_session.threshold,
            'status': obj.matching_session.status
        }

    def validate_coordinates(self, value):
        """Validate coordinates structure."""
        required_fields = {'x', 'y', 'width', 'height'}
        
        if not isinstance(value, dict):
            raise serializers.ValidationError("Coordinates must be a dictionary")
        
        missing_fields = required_fields - set(value.keys())
        if missing_fields:
            raise serializers.ValidationError(
                f"Coordinates must contain fields: {', '.join(missing_fields)}"
            )
        
        # Validate coordinate values are numeric
        for field in required_fields:
            coord_value = value.get(field)
            if not isinstance(coord_value, (int, float)):
                raise serializers.ValidationError(
                    f"Coordinate field '{field}' must be numeric"
                )
            if coord_value < 0:
                raise serializers.ValidationError(
                    f"Coordinate field '{field}' must be non-negative"
                )
        
        # Validate width and height are positive
        if value['width'] <= 0 or value['height'] <= 0:
            raise serializers.ValidationError("Width and height must be positive")
        
        return value

    def validate_confidence_score(self, value):
        """Validate confidence score is between 0.0 and 1.0."""
        if not (0.0 <= value <= 1.0):
            raise serializers.ValidationError(
                "Confidence score must be between 0.0 and 1.0"
            )
        return value


@extend_schema_serializer(
    component_name="DetectionConfirm"
)
class DetectionConfirmSerializer(serializers.Serializer):
    """Serializer for confirming detection results."""
    
    confirmed = serializers.BooleanField(
        default=True,
        help_text="Whether to confirm (True) or unconfirm (False) the detection"
    )


@extend_schema_serializer(
    component_name="BulkDetectionConfirm"
)
class BulkDetectionConfirmSerializer(serializers.Serializer):
    """Serializer for bulk confirming detection results."""
    
    detection_ids = serializers.ListField(
        child=serializers.IntegerField(),
        help_text="List of detection result IDs to confirm"
    )
    confirmed = serializers.BooleanField(
        default=True,
        help_text="Whether to confirm (True) or unconfirm (False) the detections"
    )

    def validate_detection_ids(self, value):
        """Validate that detection IDs exist."""
        if not value:
            raise serializers.ValidationError("At least one detection ID must be provided")
        
        existing_ids = DetectionResult.objects.filter(
            id__in=value
        ).values_list('id', flat=True)
        
        missing_ids = set(value) - set(existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f"Detection IDs do not exist: {', '.join(map(str, missing_ids))}"
            )
        
        return value


@extend_schema_serializer(
    component_name="GroundTruthExport"
)
class GroundTruthExportSerializer(serializers.Serializer):
    """Serializer for ground truth data export."""
    
    FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
        ('xml', 'XML'),
    ]
    
    task = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.all(),
        help_text="Task ID to export ground truth data for"
    )
    format = serializers.ChoiceField(
        choices=FORMAT_CHOICES,
        default='csv',
        help_text="Export format"
    )
    confirmed_only = serializers.BooleanField(
        default=True,
        help_text="Export only confirmed detections"
    )
    min_confidence = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        required=False,
        help_text="Minimum confidence score for exported detections"
    )
    roi_template = serializers.PrimaryKeyRelatedField(
        queryset=ROITemplate.objects.all(),
        required=False,
        help_text="Optional: Export only detections from this ROI template"
    )

    def validate(self, attrs):
        """Validate export parameters."""
        task = attrs.get('task')
        roi_template = attrs.get('roi_template')
        
        if roi_template and roi_template.task_id != task.id:
            raise serializers.ValidationError(
                "ROI template must belong to the specified task"
            )
        
        return attrs


@extend_schema_serializer(
    component_name="MatchingSessionCancel"
)
class MatchingSessionCancelSerializer(serializers.Serializer):
    """Serializer for canceling a matching session."""
    
    reason = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Optional reason for canceling the matching session"
    )


# Nested serializers for detailed views

class DetailedROITemplateSerializer(ROITemplateSerializer):
    """Detailed serializer for ROI Template with additional information."""
    
    matching_sessions = serializers.SerializerMethodField()
    
    class Meta(ROITemplateSerializer.Meta):
        fields = ROITemplateSerializer.Meta.fields + ['matching_sessions']
    
    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_matching_sessions(self, obj):
        """Get basic information about related matching sessions."""
        return [
            {
                'id': session.id,
                'algorithm_type': session.algorithm_type,
                'threshold': session.threshold,
                'status': session.status,
                'created_at': session.created_at
            }
            for session in obj.matching_sessions.all()
        ]


class DetailedMatchingSessionSerializer(MatchingSessionSerializer):
    """Detailed serializer for Matching Session with additional information."""
    
    roi_template_details = ROITemplateSerializer(
        source='roi_template',
        read_only=True
    )
    recent_detections = serializers.SerializerMethodField()
    
    class Meta(MatchingSessionSerializer.Meta):
        fields = MatchingSessionSerializer.Meta.fields + [
            'roi_template_details', 'recent_detections'
        ]
    
    @extend_schema_field(serializers.ListField(child=DetectionResultSerializer()))
    def get_recent_detections(self, obj):
        """Get the 5 most recent detection results."""
        recent_detections = obj.detection_results.order_by('-created_at')[:5]
        return DetectionResultSerializer(recent_detections, many=True).data


class DetailedDetectionResultSerializer(DetectionResultSerializer):
    """Detailed serializer for Detection Result with additional information."""
    
    matching_session_details = MatchingSessionSerializer(
        source='matching_session',
        read_only=True
    )
    
    class Meta(DetectionResultSerializer.Meta):
        fields = DetectionResultSerializer.Meta.fields + ['matching_session_details']