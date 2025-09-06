# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from django.contrib import admin
from .models import ROITemplate, MatchingSession, DetectionResult


@admin.register(ROITemplate)
class ROITemplateAdmin(admin.ModelAdmin):
    """Admin interface for ROI Template model."""
    
    list_display = ('name', 'task', 'created_by', 'created_at')
    list_filter = ('created_at', 'task__name', 'created_by')
    search_fields = ('name', 'task__name', 'created_by__username')
    readonly_fields = ('created_at',)
    raw_id_fields = ('task', 'created_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'task', 'created_by')
        }),
        ('ROI Data', {
            'fields': ('coordinates', 'feature_descriptor')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        """Make created_by readonly when editing existing objects."""
        readonly_fields = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly_fields.append('created_by')
        return readonly_fields


@admin.register(MatchingSession)
class MatchingSessionAdmin(admin.ModelAdmin):
    """Admin interface for Matching Session model."""
    
    list_display = ('id', 'roi_template', 'task', 'algorithm_type', 'status', 'threshold', 'created_at')
    list_filter = ('status', 'algorithm_type', 'created_at', 'task__name')
    search_fields = ('roi_template__name', 'task__name')
    readonly_fields = ('created_at', 'updated_at')
    raw_id_fields = ('roi_template', 'task')
    
    fieldsets = (
        ('Session Information', {
            'fields': ('roi_template', 'task', 'status')
        }),
        ('Algorithm Settings', {
            'fields': ('algorithm_type', 'threshold')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_pending', 'mark_as_completed', 'mark_as_failed']
    
    def mark_as_pending(self, request, queryset):
        """Mark selected sessions as pending."""
        updated = queryset.update(status=MatchingSession.Status.PENDING)
        self.message_user(request, f'{updated} sessions marked as pending.')
    mark_as_pending.short_description = "Mark selected sessions as pending"
    
    def mark_as_completed(self, request, queryset):
        """Mark selected sessions as completed."""
        updated = queryset.update(status=MatchingSession.Status.COMPLETED)
        self.message_user(request, f'{updated} sessions marked as completed.')
    mark_as_completed.short_description = "Mark selected sessions as completed"
    
    def mark_as_failed(self, request, queryset):
        """Mark selected sessions as failed."""
        updated = queryset.update(status=MatchingSession.Status.FAILED)
        self.message_user(request, f'{updated} sessions marked as failed.')
    mark_as_failed.short_description = "Mark selected sessions as failed"


@admin.register(DetectionResult)
class DetectionResultAdmin(admin.ModelAdmin):
    """Admin interface for Detection Result model."""
    
    list_display = ('id', 'matching_session', 'frame_number', 'confidence_score', 'is_confirmed', 'created_at')
    list_filter = ('is_confirmed', 'created_at', 'matching_session__status', 'matching_session__algorithm_type')
    search_fields = ('matching_session__roi_template__name', 'matching_session__task__name')
    readonly_fields = ('created_at',)
    raw_id_fields = ('matching_session',)
    
    fieldsets = (
        ('Detection Information', {
            'fields': ('matching_session', 'frame_number', 'is_confirmed')
        }),
        ('Detection Data', {
            'fields': ('coordinates', 'confidence_score')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['confirm_detections', 'unconfirm_detections']
    
    def confirm_detections(self, request, queryset):
        """Confirm selected detection results."""
        updated = queryset.update(is_confirmed=True)
        self.message_user(request, f'{updated} detections confirmed.')
    confirm_detections.short_description = "Confirm selected detections"
    
    def unconfirm_detections(self, request, queryset):
        """Unconfirm selected detection results."""
        updated = queryset.update(is_confirmed=False)
        self.message_user(request, f'{updated} detections unconfirmed.')
    unconfirm_detections.short_description = "Unconfirm selected detections"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        queryset = super().get_queryset(request)
        return queryset.select_related('matching_session', 'matching_session__roi_template', 'matching_session__task')