# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import django_filters
from django.db import models
from django_filters.rest_framework import FilterSet

from .models import ROITemplate, MatchingSession, DetectionResult


class ROITemplateFilter(FilterSet):
    """Filter set for ROI Template model."""
    
    task = django_filters.NumberFilter(field_name='task__id')
    task_name = django_filters.CharFilter(
        field_name='task__name', 
        lookup_expr='icontains'
    )
    created_by = django_filters.NumberFilter(field_name='created_by__id')
    created_by_username = django_filters.CharFilter(
        field_name='created_by__username', 
        lookup_expr='icontains'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='lte'
    )
    algorithm = django_filters.CharFilter(
        field_name='feature_descriptor__algorithm',
        lookup_expr='iexact',
        help_text="Filter by feature extraction algorithm"
    )
    
    class Meta:
        model = ROITemplate
        fields = [
            'task', 'task_name', 'created_by', 'created_by_username',
            'created_after', 'created_before', 'algorithm'
        ]


class MatchingSessionFilter(FilterSet):
    """Filter set for Matching Session model."""
    
    roi_template = django_filters.NumberFilter(field_name='roi_template__id')
    roi_template_name = django_filters.CharFilter(
        field_name='roi_template__name', 
        lookup_expr='icontains'
    )
    task = django_filters.NumberFilter(field_name='task__id')
    task_name = django_filters.CharFilter(
        field_name='task__name', 
        lookup_expr='icontains'
    )
    algorithm_type = django_filters.ChoiceFilter(
        choices=MatchingSession.AlgorithmType.choices
    )
    status = django_filters.ChoiceFilter(
        choices=MatchingSession.Status.choices
    )
    threshold_min = django_filters.NumberFilter(
        field_name='threshold', 
        lookup_expr='gte'
    )
    threshold_max = django_filters.NumberFilter(
        field_name='threshold', 
        lookup_expr='lte'
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='lte'
    )
    updated_after = django_filters.DateTimeFilter(
        field_name='updated_at', 
        lookup_expr='gte'
    )
    updated_before = django_filters.DateTimeFilter(
        field_name='updated_at', 
        lookup_expr='lte'
    )
    has_detections = django_filters.BooleanFilter(
        method='filter_has_detections',
        help_text="Filter sessions that have/don't have detection results"
    )
    
    class Meta:
        model = MatchingSession
        fields = [
            'roi_template', 'roi_template_name', 'task', 'task_name',
            'algorithm_type', 'status', 'threshold_min', 'threshold_max',
            'created_after', 'created_before', 'updated_after', 'updated_before',
            'has_detections'
        ]

    def filter_has_detections(self, queryset, name, value):
        """Filter sessions based on whether they have detection results."""
        if value:
            return queryset.filter(detection_results__isnull=False).distinct()
        else:
            return queryset.filter(detection_results__isnull=True).distinct()


class DetectionResultFilter(FilterSet):
    """Filter set for Detection Result model."""
    
    matching_session = django_filters.NumberFilter(field_name='matching_session__id')
    roi_template = django_filters.NumberFilter(
        field_name='matching_session__roi_template__id'
    )
    roi_template_name = django_filters.CharFilter(
        field_name='matching_session__roi_template__name', 
        lookup_expr='icontains'
    )
    task = django_filters.NumberFilter(field_name='matching_session__task__id')
    task_name = django_filters.CharFilter(
        field_name='matching_session__task__name', 
        lookup_expr='icontains'
    )
    frame_number = django_filters.NumberFilter()
    frame_number_min = django_filters.NumberFilter(
        field_name='frame_number', 
        lookup_expr='gte'
    )
    frame_number_max = django_filters.NumberFilter(
        field_name='frame_number', 
        lookup_expr='lte'
    )
    confidence_min = django_filters.NumberFilter(
        field_name='confidence_score', 
        lookup_expr='gte',
        help_text="Minimum confidence score"
    )
    confidence_max = django_filters.NumberFilter(
        field_name='confidence_score', 
        lookup_expr='lte',
        help_text="Maximum confidence score"
    )
    is_confirmed = django_filters.BooleanFilter()
    algorithm_type = django_filters.ChoiceFilter(
        field_name='matching_session__algorithm_type',
        choices=MatchingSession.AlgorithmType.choices
    )
    session_status = django_filters.ChoiceFilter(
        field_name='matching_session__status',
        choices=MatchingSession.Status.choices,
        help_text="Filter by matching session status"
    )
    created_after = django_filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='gte'
    )
    created_before = django_filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='lte'
    )
    
    # Coordinate-based filters
    bbox_x_min = django_filters.NumberFilter(
        method='filter_bbox_x_min',
        help_text="Filter detections with bounding box x >= value"
    )
    bbox_x_max = django_filters.NumberFilter(
        method='filter_bbox_x_max',
        help_text="Filter detections with bounding box x <= value"
    )
    bbox_y_min = django_filters.NumberFilter(
        method='filter_bbox_y_min',
        help_text="Filter detections with bounding box y >= value"
    )
    bbox_y_max = django_filters.NumberFilter(
        method='filter_bbox_y_max',
        help_text="Filter detections with bounding box y <= value"
    )
    bbox_width_min = django_filters.NumberFilter(
        method='filter_bbox_width_min',
        help_text="Filter detections with bounding box width >= value"
    )
    bbox_width_max = django_filters.NumberFilter(
        method='filter_bbox_width_max',
        help_text="Filter detections with bounding box width <= value"
    )
    bbox_height_min = django_filters.NumberFilter(
        method='filter_bbox_height_min',
        help_text="Filter detections with bounding box height >= value"
    )
    bbox_height_max = django_filters.NumberFilter(
        method='filter_bbox_height_max',
        help_text="Filter detections with bounding box height <= value"
    )
    
    class Meta:
        model = DetectionResult
        fields = [
            'matching_session', 'roi_template', 'roi_template_name', 'task', 'task_name',
            'frame_number', 'frame_number_min', 'frame_number_max',
            'confidence_min', 'confidence_max', 'is_confirmed',
            'algorithm_type', 'session_status', 'created_after', 'created_before',
            'bbox_x_min', 'bbox_x_max', 'bbox_y_min', 'bbox_y_max',
            'bbox_width_min', 'bbox_width_max', 'bbox_height_min', 'bbox_height_max'
        ]

    def filter_bbox_x_min(self, queryset, name, value):
        """Filter detections with bounding box x coordinate >= value."""
        return queryset.extra(
            where=["(coordinates->>'x')::float >= %s"],
            params=[value]
        )

    def filter_bbox_x_max(self, queryset, name, value):
        """Filter detections with bounding box x coordinate <= value."""
        return queryset.extra(
            where=["(coordinates->>'x')::float <= %s"],
            params=[value]
        )

    def filter_bbox_y_min(self, queryset, name, value):
        """Filter detections with bounding box y coordinate >= value."""
        return queryset.extra(
            where=["(coordinates->>'y')::float >= %s"],
            params=[value]
        )

    def filter_bbox_y_max(self, queryset, name, value):
        """Filter detections with bounding box y coordinate <= value."""
        return queryset.extra(
            where=["(coordinates->>'y')::float <= %s"],
            params=[value]
        )

    def filter_bbox_width_min(self, queryset, name, value):
        """Filter detections with bounding box width >= value."""
        return queryset.extra(
            where=["(coordinates->>'width')::float >= %s"],
            params=[value]
        )

    def filter_bbox_width_max(self, queryset, name, value):
        """Filter detections with bounding box width <= value."""
        return queryset.extra(
            where=["(coordinates->>'width')::float <= %s"],
            params=[value]
        )

    def filter_bbox_height_min(self, queryset, name, value):
        """Filter detections with bounding box height >= value."""
        return queryset.extra(
            where=["(coordinates->>'height')::float >= %s"],
            params=[value]
        )

    def filter_bbox_height_max(self, queryset, name, value):
        """Filter detections with bounding box height <= value."""
        return queryset.extra(
            where=["(coordinates->>'height')::float <= %s"],
            params=[value]
        )


class AdvancedDetectionResultFilter(DetectionResultFilter):
    """Advanced filter set with additional spatial and temporal filtering options."""
    
    # Spatial region filtering
    intersects_region = django_filters.CharFilter(
        method='filter_intersects_region',
        help_text="Filter detections that intersect with region (format: 'x,y,width,height')"
    )
    contains_point = django_filters.CharFilter(
        method='filter_contains_point',
        help_text="Filter detections that contain point (format: 'x,y')"
    )
    
    # Temporal filtering
    frame_range = django_filters.CharFilter(
        method='filter_frame_range',
        help_text="Filter detections within frame range (format: 'start,end')"
    )
    
    # Confidence-based clustering
    confidence_tier = django_filters.ChoiceFilter(
        method='filter_confidence_tier',
        choices=[
            ('high', 'High (>= 0.8)'),
            ('medium', 'Medium (0.5 - 0.8)'),
            ('low', 'Low (< 0.5)'),
        ],
        help_text="Filter by confidence tier"
    )

    def filter_intersects_region(self, queryset, name, value):
        """Filter detections that intersect with the specified region."""
        try:
            x, y, width, height = map(float, value.split(','))
        except (ValueError, TypeError):
            return queryset.none()
        
        # Check if detection bounding box intersects with the region
        return queryset.extra(
            where=["""
                NOT (
                    (coordinates->>'x')::float + (coordinates->>'width')::float < %s OR
                    (coordinates->>'x')::float > %s + %s OR
                    (coordinates->>'y')::float + (coordinates->>'height')::float < %s OR
                    (coordinates->>'y')::float > %s + %s
                )
            """],
            params=[x, x, width, y, y, height]
        )

    def filter_contains_point(self, queryset, name, value):
        """Filter detections whose bounding box contains the specified point."""
        try:
            px, py = map(float, value.split(','))
        except (ValueError, TypeError):
            return queryset.none()
        
        return queryset.extra(
            where=["""
                (coordinates->>'x')::float <= %s AND
                (coordinates->>'x')::float + (coordinates->>'width')::float >= %s AND
                (coordinates->>'y')::float <= %s AND
                (coordinates->>'y')::float + (coordinates->>'height')::float >= %s
            """],
            params=[px, px, py, py]
        )

    def filter_frame_range(self, queryset, name, value):
        """Filter detections within the specified frame range."""
        try:
            start, end = map(int, value.split(','))
        except (ValueError, TypeError):
            return queryset.none()
        
        return queryset.filter(frame_number__range=[start, end])

    def filter_confidence_tier(self, queryset, name, value):
        """Filter detections by confidence tier."""
        if value == 'high':
            return queryset.filter(confidence_score__gte=0.8)
        elif value == 'medium':
            return queryset.filter(confidence_score__gte=0.5, confidence_score__lt=0.8)
        elif value == 'low':
            return queryset.filter(confidence_score__lt=0.5)
        else:
            return queryset