# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

import uuid
import logging
import json
from typing import Any, Optional
from django.db.models import Q, Count, Prefetch
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import status, viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
import django_rq
from rq.job import Job as RQJob

from cvat.apps.engine.filters import FilteredOrderingFilter
from cvat.apps.engine.mixins import PartialUpdateModelMixin, UploadMixin
from cvat.apps.engine.pagination import StandardPagination
from cvat.apps.engine.models import Task
from cvat.apps.engine.rq import RequestId

from .models import ROITemplate, MatchingSession, DetectionResult
from .serializers import (
    ROITemplateSerializer,
    DetailedROITemplateSerializer,
    MatchingSessionSerializer,
    DetailedMatchingSessionSerializer,
    MatchingSessionStartSerializer,
    MatchingSessionCancelSerializer,
    DetectionResultSerializer,
    DetailedDetectionResultSerializer,
    DetectionConfirmSerializer,
    BulkDetectionConfirmSerializer,
    GroundTruthExportSerializer,
)
from .permissions import (
    ROITemplatePermission,
    MatchingSessionPermission,
    DetectionResultPermission,
    GroundTruthPermission,
    TaskAccessMixin,
    ROITemplateAccessMixin,
)
from .filters import (
    ROITemplateFilter,
    MatchingSessionFilter,
    DetectionResultFilter,
)


logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(
        summary="List ROI templates",
        description="Returns a paginated list of ROI templates that the user has access to.",
        parameters=[
            OpenApiParameter('task', OpenApiTypes.INT, description='Filter by task ID'),
            OpenApiParameter('search', OpenApiTypes.STR, description='Search in template names'),
            OpenApiParameter('ordering', OpenApiTypes.STR, 
                           description='Order results by field (prefix with - for descending)'),
        ]
    ),
    create=extend_schema(
        summary="Create ROI template",
        description="Create a new ROI template for feature extraction and matching."
    ),
    retrieve=extend_schema(
        summary="Get ROI template details",
        description="Retrieve detailed information about a specific ROI template."
    ),
    update=extend_schema(
        summary="Update ROI template",
        description="Update all fields of an existing ROI template."
    ),
    partial_update=extend_schema(
        summary="Partially update ROI template",
        description="Update specific fields of an existing ROI template."
    ),
    destroy=extend_schema(
        summary="Delete ROI template",
        description="Delete an ROI template and all its associated matching sessions."
    ),
)
class ROITemplateViewSet(
    PartialUpdateModelMixin,
    viewsets.ModelViewSet,
    TaskAccessMixin,
):
    """
    ViewSet for managing ROI templates.
    
    ROI templates define regions of interest with feature descriptors
    that can be used for matching against video frames.
    """
    
    queryset = ROITemplate.objects.select_related('task', 'created_by').prefetch_related(
        'matching_sessions'
    )
    serializer_class = ROITemplateSerializer
    permission_classes = [ROITemplatePermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, FilteredOrderingFilter]
    filterset_class = ROITemplateFilter
    search_fields = ['name', 'task__name']
    ordering_fields = ['id', 'name', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return DetailedROITemplateSerializer
        return ROITemplateSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = self.queryset
        
        if not self.request.user.is_superuser:
            # Filter to only show ROI templates the user has access to
            accessible_tasks = Task.objects.filter(
                Q(owner=self.request.user) |
                Q(assignee=self.request.user) |
                Q(project__owner=self.request.user)
            )
            queryset = queryset.filter(task__in=accessible_tasks)
        
        return queryset

    def perform_create(self, serializer):
        """Set the current user as the creator of the ROI template."""
        # Check task access
        task_id = serializer.validated_data['task'].id
        self.check_task_access(self.request, task_id)
        
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Check task access before updating."""
        task_id = serializer.validated_data['task'].id
        self.check_task_access(self.request, task_id)
        
        serializer.save()

    @extend_schema(
        summary="Export ROI template",
        description="Export ROI template data in various formats.",
        parameters=[
            OpenApiParameter('format', OpenApiTypes.STR, 
                           description='Export format (json, xml)', enum=['json', 'xml'])
        ],
        responses={
            200: OpenApiResponse(description="Export file"),
            400: OpenApiResponse(description="Invalid parameters"),
        }
    )
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export ROI template data."""
        roi_template = self.get_object()
        export_format = request.query_params.get('format', 'json')
        
        if export_format not in ['json', 'xml']:
            raise ValidationError("Format must be 'json' or 'xml'")
        
        # Prepare export data
        export_data = {
            'roi_template': DetailedROITemplateSerializer(roi_template).data,
            'export_timestamp': timezone.now().isoformat(),
            'export_format': export_format
        }
        
        if export_format == 'json':
            response = HttpResponse(
                json.dumps(export_data, indent=2),
                content_type='application/json'
            )
            response['Content-Disposition'] = f'attachment; filename="roi_template_{pk}.json"'
        else:  # xml
            # Convert to XML format (simplified implementation)
            from dicttoxml import dicttoxml
            xml_data = dicttoxml(export_data, root='roi_template_export')
            response = HttpResponse(xml_data, content_type='application/xml')
            response['Content-Disposition'] = f'attachment; filename="roi_template_{pk}.xml"'
        
        return response


@extend_schema_view(
    list=extend_schema(
        summary="List matching sessions",
        description="Returns a paginated list of matching sessions that the user has access to.",
        parameters=[
            OpenApiParameter('task', OpenApiTypes.INT, description='Filter by task ID'),
            OpenApiParameter('roi_template', OpenApiTypes.INT, description='Filter by ROI template ID'),
            OpenApiParameter('status', OpenApiTypes.STR, 
                           description='Filter by status', enum=['PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED']),
            OpenApiParameter('algorithm_type', OpenApiTypes.STR, 
                           description='Filter by algorithm', enum=['SIFT', 'SURF', 'ORB', 'AKAZE']),
        ]
    ),
    create=extend_schema(
        summary="Create matching session",
        description="Create a new matching session to find ROI template matches in video frames."
    ),
    retrieve=extend_schema(
        summary="Get matching session details",
        description="Retrieve detailed information about a specific matching session."
    ),
    update=extend_schema(
        summary="Update matching session",
        description="Update all fields of an existing matching session."
    ),
    partial_update=extend_schema(
        summary="Partially update matching session",
        description="Update specific fields of an existing matching session."
    ),
    destroy=extend_schema(
        summary="Delete matching session",
        description="Delete a matching session and all its detection results."
    ),
)
class MatchingSessionViewSet(
    PartialUpdateModelMixin,
    viewsets.ModelViewSet,
    TaskAccessMixin,
    ROITemplateAccessMixin,
):
    """
    ViewSet for managing matching sessions.
    
    Matching sessions use ROI templates to find matches in video frames
    using computer vision algorithms.
    """
    
    queryset = MatchingSession.objects.select_related(
        'roi_template', 'task', 'roi_template__created_by'
    ).prefetch_related(
        Prefetch('detection_results', DetectionResult.objects.order_by('-confidence_score'))
    )
    serializer_class = MatchingSessionSerializer
    permission_classes = [MatchingSessionPermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, FilteredOrderingFilter]
    filterset_class = MatchingSessionFilter
    search_fields = ['roi_template__name', 'task__name']
    ordering_fields = ['id', 'created_at', 'updated_at', 'threshold']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return DetailedMatchingSessionSerializer
        elif self.action == 'start':
            return MatchingSessionStartSerializer
        elif self.action == 'cancel':
            return MatchingSessionCancelSerializer
        return MatchingSessionSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = self.queryset
        
        if not self.request.user.is_superuser:
            # Filter to only show matching sessions the user has access to
            accessible_tasks = Task.objects.filter(
                Q(owner=self.request.user) |
                Q(assignee=self.request.user) |
                Q(project__owner=self.request.user)
            )
            queryset = queryset.filter(task__in=accessible_tasks)
        
        return queryset

    def perform_create(self, serializer):
        """Check access before creating matching session."""
        # Check task access
        task_id = serializer.validated_data['task'].id
        self.check_task_access(self.request, task_id)
        
        # Check ROI template access
        roi_template_id = serializer.validated_data['roi_template'].id
        self.check_roi_template_access(self.request, roi_template_id)
        
        serializer.save()

    @extend_schema(
        summary="Start matching session",
        description="Start the matching process for this session. Returns a job ID to track progress.",
        request=MatchingSessionStartSerializer,
        responses={
            200: inline_serializer(
                'MatchingSessionStartResponse',
                fields={
                    'rq_id': drf_serializers.CharField(),
                    'status': drf_serializers.CharField(),
                    'message': drf_serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description="Invalid session state or parameters"),
        }
    )
    @action(detail=True, methods=['post'])
    def start(self, request, pk=None):
        """Start the matching session processing."""
        matching_session = self.get_object()
        
        # Check if session is in a valid state to start
        if matching_session.status not in [MatchingSession.Status.PENDING, MatchingSession.Status.FAILED]:
            raise ValidationError("Matching session can only be started from PENDING or FAILED status")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get frame range if specified
        frame_range = serializer.validated_data.get('frame_range')
        
        # Update session status
        matching_session.status = MatchingSession.Status.IN_PROGRESS
        matching_session.save()
        
        # Start background job
        try:
            from .services.matching_service import run_matching_task
            
            queue = django_rq.get_queue('default')
            rq_job = queue.enqueue(
                run_matching_task,
                matching_session_id=matching_session.id,
                frame_range=frame_range,
                job_timeout='30m',  # 30 minute timeout
            )
            
            rq_id = RequestId.from_rq_job(rq_job)
            
            logger.info(f"Started matching session {matching_session.id} with job {rq_id}")
            
            return Response({
                'rq_id': str(rq_id),
                'status': 'started',
                'message': f'Matching session {matching_session.id} started successfully'
            })
            
        except Exception as e:
            # Revert status change if job creation failed
            matching_session.status = MatchingSession.Status.FAILED
            matching_session.save()
            
            logger.error(f"Failed to start matching session {matching_session.id}: {e}")
            raise ValidationError(f"Failed to start matching session: {str(e)}")

    @extend_schema(
        summary="Cancel matching session",
        description="Cancel a running matching session.",
        request=MatchingSessionCancelSerializer,
        responses={
            200: inline_serializer(
                'MatchingSessionCancelResponse',
                fields={
                    'status': drf_serializers.CharField(),
                    'message': drf_serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description="Session not in cancellable state"),
        }
    )
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel the matching session processing."""
        matching_session = self.get_object()
        
        # Check if session is in a cancellable state
        if matching_session.status != MatchingSession.Status.IN_PROGRESS:
            raise ValidationError("Can only cancel sessions that are in progress")
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Update session status
        matching_session.status = MatchingSession.Status.FAILED
        matching_session.save()
        
        # TODO: Cancel RQ job if job ID is stored
        # This would require storing the job ID in the matching session model
        
        reason = serializer.validated_data.get('reason', 'Cancelled by user')
        logger.info(f"Cancelled matching session {matching_session.id}: {reason}")
        
        return Response({
            'status': 'cancelled',
            'message': f'Matching session {matching_session.id} cancelled successfully'
        })

    @extend_schema(
        summary="Get matching session progress",
        description="Get the current progress and status of the matching session.",
        responses={
            200: inline_serializer(
                'MatchingSessionProgressResponse',
                fields={
                    'status': drf_serializers.CharField(),
                    'progress': drf_serializers.FloatField(),
                    'total_frames': drf_serializers.IntegerField(),
                    'processed_frames': drf_serializers.IntegerField(),
                    'detections_found': drf_serializers.IntegerField(),
                    'message': drf_serializers.CharField(),
                }
            )
        }
    )
    @action(detail=True, methods=['get'])
    def progress(self, request, pk=None):
        """Get matching session progress."""
        matching_session = self.get_object()
        
        # Get detection count
        detection_count = matching_session.detection_results.count()
        
        # Calculate progress based on status
        progress = 0.0
        if matching_session.status == MatchingSession.Status.COMPLETED:
            progress = 100.0
        elif matching_session.status == MatchingSession.Status.IN_PROGRESS:
            # This is a simplified progress calculation
            # In a real implementation, you'd track actual frame processing progress
            progress = min(50.0, detection_count * 2.0)  # Arbitrary progress calculation
        
        return Response({
            'status': matching_session.status,
            'progress': progress,
            'total_frames': matching_session.task.data.size if matching_session.task.data else 0,
            'processed_frames': detection_count,
            'detections_found': detection_count,
            'message': f'Matching session is {matching_session.status.lower()}'
        })


@extend_schema_view(
    list=extend_schema(
        summary="List detection results",
        description="Returns a paginated list of detection results that the user has access to.",
        parameters=[
            OpenApiParameter('matching_session', OpenApiTypes.INT, description='Filter by matching session ID'),
            OpenApiParameter('task', OpenApiTypes.INT, description='Filter by task ID'),
            OpenApiParameter('min_confidence', OpenApiTypes.NUMBER, description='Minimum confidence score'),
            OpenApiParameter('max_confidence', OpenApiTypes.NUMBER, description='Maximum confidence score'),
            OpenApiParameter('is_confirmed', OpenApiTypes.BOOL, description='Filter by confirmation status'),
            OpenApiParameter('frame_number', OpenApiTypes.INT, description='Filter by frame number'),
        ]
    ),
    retrieve=extend_schema(
        summary="Get detection result details",
        description="Retrieve detailed information about a specific detection result."
    ),
    update=extend_schema(
        summary="Update detection result",
        description="Update all fields of an existing detection result."
    ),
    partial_update=extend_schema(
        summary="Partially update detection result",
        description="Update specific fields of an existing detection result."
    ),
    destroy=extend_schema(
        summary="Delete detection result",
        description="Delete a detection result."
    ),
)
class DetectionResultViewSet(
    PartialUpdateModelMixin,
    viewsets.ModelViewSet,
    TaskAccessMixin,
):
    """
    ViewSet for managing detection results.
    
    Detection results are the output of matching sessions, representing
    potential matches found in video frames.
    """
    
    queryset = DetectionResult.objects.select_related(
        'matching_session', 'matching_session__roi_template', 'matching_session__task'
    )
    serializer_class = DetectionResultSerializer
    permission_classes = [DetectionResultPermission]
    pagination_class = StandardPagination
    filter_backends = [DjangoFilterBackend, FilteredOrderingFilter]
    filterset_class = DetectionResultFilter
    ordering_fields = ['id', 'frame_number', 'confidence_score', 'created_at']
    ordering = ['frame_number', '-confidence_score']

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return DetailedDetectionResultSerializer
        elif self.action == 'confirm':
            return DetectionConfirmSerializer
        elif self.action == 'bulk_confirm':
            return BulkDetectionConfirmSerializer
        return DetectionResultSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = self.queryset
        
        if not self.request.user.is_superuser:
            # Filter to only show detection results the user has access to
            accessible_tasks = Task.objects.filter(
                Q(owner=self.request.user) |
                Q(assignee=self.request.user) |
                Q(project__owner=self.request.user)
            )
            queryset = queryset.filter(matching_session__task__in=accessible_tasks)
        
        return queryset

    @extend_schema(
        summary="Confirm detection result",
        description="Confirm or unconfirm a detection result.",
        request=DetectionConfirmSerializer,
        responses={
            200: inline_serializer(
                'DetectionConfirmResponse',
                fields={
                    'id': drf_serializers.IntegerField(),
                    'is_confirmed': drf_serializers.BooleanField(),
                    'message': drf_serializers.CharField(),
                }
            )
        }
    )
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm or unconfirm a detection result."""
        detection = self.get_object()
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        confirmed = serializer.validated_data['confirmed']
        detection.is_confirmed = confirmed
        detection.save()
        
        action_text = 'confirmed' if confirmed else 'unconfirmed'
        
        return Response({
            'id': detection.id,
            'is_confirmed': detection.is_confirmed,
            'message': f'Detection result {action_text} successfully'
        })

    @extend_schema(
        summary="Bulk confirm detection results",
        description="Confirm or unconfirm multiple detection results at once.",
        request=BulkDetectionConfirmSerializer,
        responses={
            200: inline_serializer(
                'BulkDetectionConfirmResponse',
                fields={
                    'updated_count': drf_serializers.IntegerField(),
                    'detection_ids': drf_serializers.ListField(child=drf_serializers.IntegerField()),
                    'message': drf_serializers.CharField(),
                }
            )
        }
    )
    @action(detail=False, methods=['post'])
    def bulk_confirm(self, request):
        """Bulk confirm or unconfirm multiple detection results."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        detection_ids = serializer.validated_data['detection_ids']
        confirmed = serializer.validated_data['confirmed']
        
        # Filter to only detections the user has access to
        accessible_detections = self.get_queryset().filter(id__in=detection_ids)
        
        with transaction.atomic():
            updated_count = accessible_detections.update(is_confirmed=confirmed)
        
        action_text = 'confirmed' if confirmed else 'unconfirmed'
        
        return Response({
            'updated_count': updated_count,
            'detection_ids': list(accessible_detections.values_list('id', flat=True)),
            'message': f'{updated_count} detection results {action_text} successfully'
        })


@extend_schema_view(
    export=extend_schema(
        summary="Export ground truth data",
        description="Export confirmed detection results as ground truth data in various formats.",
        request=GroundTruthExportSerializer,
        responses={
            200: inline_serializer(
                'GroundTruthExportResponse',
                fields={
                    'rq_id': drf_serializers.CharField(),
                    'status': drf_serializers.CharField(),
                    'message': drf_serializers.CharField(),
                }
            ),
            400: OpenApiResponse(description="Invalid parameters"),
        }
    ),
    status=extend_schema(
        summary="Get export job status",
        description="Get the status of a ground truth export job.",
        parameters=[
            OpenApiParameter('rq_id', OpenApiTypes.STR, description='Job ID from export request'),
        ],
        responses={
            200: inline_serializer(
                'GroundTruthStatusResponse',
                fields={
                    'status': drf_serializers.CharField(),
                    'progress': drf_serializers.FloatField(),
                    'result_url': drf_serializers.URLField(allow_null=True),
                    'error': drf_serializers.CharField(allow_null=True),
                }
            )
        }
    )
)
class GroundTruthViewSet(
    viewsets.GenericViewSet,
    TaskAccessMixin,
):
    """
    ViewSet for ground truth data export operations.
    
    Provides functionality to export confirmed detection results
    as ground truth data in various formats.
    """
    
    permission_classes = [GroundTruthPermission]
    serializer_class = GroundTruthExportSerializer

    @action(detail=False, methods=['post'])
    def export(self, request):
        """Export ground truth data."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        task = serializer.validated_data['task']
        export_format = serializer.validated_data['format']
        confirmed_only = serializer.validated_data['confirmed_only']
        min_confidence = serializer.validated_data.get('min_confidence')
        roi_template = serializer.validated_data.get('roi_template')
        
        # Check task access
        self.check_task_access(request, task.id)
        
        # Start background export job
        try:
            from .services.export_service import export_ground_truth_task
            
            queue = django_rq.get_queue('default')
            rq_job = queue.enqueue(
                export_ground_truth_task,
                task_id=task.id,
                export_format=export_format,
                confirmed_only=confirmed_only,
                min_confidence=min_confidence,
                roi_template_id=roi_template.id if roi_template else None,
                user_id=request.user.id,
                job_timeout='15m',  # 15 minute timeout
            )
            
            rq_id = RequestId.from_rq_job(rq_job)
            
            logger.info(f"Started ground truth export for task {task.id} with job {rq_id}")
            
            return Response({
                'rq_id': str(rq_id),
                'status': 'started',
                'message': f'Ground truth export for task {task.id} started successfully'
            })
            
        except Exception as e:
            logger.error(f"Failed to start ground truth export for task {task.id}: {e}")
            raise ValidationError(f"Failed to start export: {str(e)}")

    @action(detail=False, methods=['get'])
    def status(self, request):
        """Get export job status."""
        rq_id = request.query_params.get('rq_id')
        if not rq_id:
            raise ValidationError("rq_id parameter is required")
        
        try:
            request_id = RequestId.parse(rq_id)
            queue = django_rq.get_queue('default')
            rq_job = queue.job_class.fetch(str(request_id.job_id), connection=queue.connection)
            
            if rq_job is None:
                raise ValidationError("Job not found")
            
            # Calculate progress (simplified)
            progress = 0.0
            if rq_job.is_finished:
                progress = 100.0
            elif rq_job.is_started:
                progress = 50.0  # Simplified progress
            
            response_data = {
                'status': rq_job.get_status(),
                'progress': progress,
                'result_url': None,
                'error': None,
            }
            
            if rq_job.is_finished and rq_job.result:
                # Assume result contains download URL
                if isinstance(rq_job.result, dict) and 'download_url' in rq_job.result:
                    response_data['result_url'] = rq_job.result['download_url']
            
            if rq_job.is_failed:
                response_data['error'] = str(rq_job.exc_info) if rq_job.exc_info else 'Unknown error'
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error checking export job status {rq_id}: {e}")
            raise ValidationError(f"Error checking job status: {str(e)}")