# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any, Optional, Union, cast

from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.request import Request
from rest_framework.viewsets import ViewSet

from cvat.apps.iam.permissions import (
    OpenPolicyAgentPermission,
    StrEnum,
    build_iam_context,
    get_iam_context,
    get_membership,
)
from cvat.apps.engine.models import Task
from cvat.apps.organizations.models import Organization

from .models import ROITemplate, MatchingSession, DetectionResult


def _get_key(d: dict[str, Any], key_path: Union[str, list[str]]) -> Optional[Any]:
    """
    Like dict.get(), but supports nested fields. If the field is missing, returns None.
    """
    if isinstance(key_path, str):
        key_path = [key_path]
    else:
        assert key_path

    for key_part in key_path:
        d = d.get(key_part)
        if d is None:
            return d

    return d


class CalibrixPermission(OpenPolicyAgentPermission):
    """Base permission class for Calibrix matching resources."""
    
    class Scopes(StrEnum):
        LIST = 'list'
        CREATE = 'create'
        VIEW = 'view'
        UPDATE = 'update'
        DELETE = 'delete'

    @staticmethod
    def create_scope_list(request: Request, view: ViewSet, obj: Any) -> list[str]:
        """Create list of permission scopes to check."""
        scopes = []
        
        if view.action in ['list', 'search']:
            scopes.append(CalibrixPermission.Scopes.LIST)
        elif view.action in ['create']:
            scopes.append(CalibrixPermission.Scopes.CREATE)
        elif view.action in ['retrieve']:
            scopes.append(CalibrixPermission.Scopes.VIEW)
        elif view.action in ['update', 'partial_update']:
            scopes.append(CalibrixPermission.Scopes.UPDATE)
        elif view.action in ['destroy']:
            scopes.append(CalibrixPermission.Scopes.DELETE)
        
        return scopes

    @classmethod
    def create_base_context(
        cls, request: Request, view: ViewSet, obj: Any, organization: Optional[Organization] = None
    ) -> dict:
        """Create base context for permission evaluation."""
        if organization is None and hasattr(view, 'get_organization'):
            organization = view.get_organization()

        data = {
            'user_id': request.user.id,
            'groups': list(request.user.groups.values_list('name', flat=True)),
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        }

        if organization is not None:
            membership = get_membership(request.user, organization)
            data.update({
                'organization': {
                    'id': organization.id,
                    'owner': {'id': organization.owner_id},
                    'is_member': membership is not None,
                    'role': membership.role if membership else None,
                },
            })

        return data


class ROITemplatePermission(CalibrixPermission):
    """Permission class for ROI Template resources."""
    
    class Scopes(StrEnum):
        LIST = 'list'
        CREATE = 'create'
        VIEW = 'view'
        UPDATE = 'update'
        DELETE = 'delete'

    @classmethod
    def create_scope_list(cls, request: Request, view: ViewSet, obj: Any) -> list[str]:
        """Create list of permission scopes to check for ROI templates."""
        scopes = []
        
        if view.action in ['list']:
            scopes.append(cls.Scopes.LIST)
        elif view.action in ['create']:
            scopes.append(cls.Scopes.CREATE)
        elif view.action in ['retrieve']:
            scopes.append(cls.Scopes.VIEW)
        elif view.action in ['update', 'partial_update']:
            scopes.append(cls.Scopes.UPDATE)
        elif view.action in ['destroy']:
            scopes.append(cls.Scopes.DELETE)
        
        return scopes

    @classmethod
    def create_context(cls, request: Request, view: ViewSet, obj: Any) -> dict:
        """Create context for ROI template permission evaluation."""
        # Get task and organization information
        task = None
        organization = None
        
        if isinstance(obj, ROITemplate):
            task = obj.task
            organization = task.project.organization if task.project else None
        elif isinstance(obj, Task):
            task = obj
            organization = task.project.organization if task.project else None
        elif hasattr(view, 'get_task'):
            task = view.get_task()
            organization = task.project.organization if task and task.project else None

        context = cls.create_base_context(request, view, obj, organization)
        
        if task:
            context.update({
                'task': {
                    'id': task.id,
                    'owner': {'id': task.owner_id},
                    'assignee': {'id': task.assignee_id} if task.assignee_id else None,
                    'project': {
                        'id': task.project.id,
                        'owner': {'id': task.project.owner_id},
                    } if task.project else None,
                }
            })

        if isinstance(obj, ROITemplate):
            context.update({
                'roi_template': {
                    'id': obj.id,
                    'owner': {'id': obj.created_by_id} if obj.created_by_id else None,
                    'task': context.get('task'),
                }
            })

        return context


class MatchingSessionPermission(CalibrixPermission):
    """Permission class for Matching Session resources."""
    
    class Scopes(StrEnum):
        LIST = 'list'
        CREATE = 'create'
        VIEW = 'view'
        UPDATE = 'update'
        DELETE = 'delete'
        START = 'start'
        CANCEL = 'cancel'

    @classmethod
    def create_scope_list(cls, request: Request, view: ViewSet, obj: Any) -> list[str]:
        """Create list of permission scopes to check for matching sessions."""
        scopes = []
        
        if view.action in ['list']:
            scopes.append(cls.Scopes.LIST)
        elif view.action in ['create']:
            scopes.append(cls.Scopes.CREATE)
        elif view.action in ['retrieve']:
            scopes.append(cls.Scopes.VIEW)
        elif view.action in ['update', 'partial_update']:
            scopes.append(cls.Scopes.UPDATE)
        elif view.action in ['destroy']:
            scopes.append(cls.Scopes.DELETE)
        elif view.action in ['start']:
            scopes.append(cls.Scopes.START)
        elif view.action in ['cancel']:
            scopes.append(cls.Scopes.CANCEL)
        
        return scopes

    @classmethod
    def create_context(cls, request: Request, view: ViewSet, obj: Any) -> dict:
        """Create context for matching session permission evaluation."""
        # Get task and organization information
        task = None
        organization = None
        roi_template = None
        
        if isinstance(obj, MatchingSession):
            task = obj.task
            roi_template = obj.roi_template
            organization = task.project.organization if task.project else None
        elif isinstance(obj, Task):
            task = obj
            organization = task.project.organization if task.project else None
        elif hasattr(view, 'get_task'):
            task = view.get_task()
            organization = task.project.organization if task and task.project else None

        context = cls.create_base_context(request, view, obj, organization)
        
        if task:
            context.update({
                'task': {
                    'id': task.id,
                    'owner': {'id': task.owner_id},
                    'assignee': {'id': task.assignee_id} if task.assignee_id else None,
                    'project': {
                        'id': task.project.id,
                        'owner': {'id': task.project.owner_id},
                    } if task.project else None,
                }
            })

        if roi_template:
            context.update({
                'roi_template': {
                    'id': roi_template.id,
                    'owner': {'id': roi_template.created_by_id} if roi_template.created_by_id else None,
                }
            })

        if isinstance(obj, MatchingSession):
            context.update({
                'matching_session': {
                    'id': obj.id,
                    'status': obj.status,
                    'task': context.get('task'),
                    'roi_template': context.get('roi_template'),
                }
            })

        return context


class DetectionResultPermission(CalibrixPermission):
    """Permission class for Detection Result resources."""
    
    class Scopes(StrEnum):
        LIST = 'list'
        VIEW = 'view'
        UPDATE = 'update'
        DELETE = 'delete'
        CONFIRM = 'confirm'
        BULK_CONFIRM = 'bulk_confirm'

    @classmethod
    def create_scope_list(cls, request: Request, view: ViewSet, obj: Any) -> list[str]:
        """Create list of permission scopes to check for detection results."""
        scopes = []
        
        if view.action in ['list']:
            scopes.append(cls.Scopes.LIST)
        elif view.action in ['retrieve']:
            scopes.append(cls.Scopes.VIEW)
        elif view.action in ['update', 'partial_update']:
            scopes.append(cls.Scopes.UPDATE)
        elif view.action in ['destroy']:
            scopes.append(cls.Scopes.DELETE)
        elif view.action in ['confirm']:
            scopes.append(cls.Scopes.CONFIRM)
        elif view.action in ['bulk_confirm']:
            scopes.append(cls.Scopes.BULK_CONFIRM)
        
        return scopes

    @classmethod
    def create_context(cls, request: Request, view: ViewSet, obj: Any) -> dict:
        """Create context for detection result permission evaluation."""
        # Get task and organization information
        task = None
        organization = None
        matching_session = None
        roi_template = None
        
        if isinstance(obj, DetectionResult):
            matching_session = obj.matching_session
            task = matching_session.task
            roi_template = matching_session.roi_template
            organization = task.project.organization if task.project else None
        elif isinstance(obj, MatchingSession):
            matching_session = obj
            task = obj.task
            roi_template = obj.roi_template
            organization = task.project.organization if task.project else None
        elif isinstance(obj, Task):
            task = obj
            organization = task.project.organization if task.project else None
        elif hasattr(view, 'get_task'):
            task = view.get_task()
            organization = task.project.organization if task and task.project else None

        context = cls.create_base_context(request, view, obj, organization)
        
        if task:
            context.update({
                'task': {
                    'id': task.id,
                    'owner': {'id': task.owner_id},
                    'assignee': {'id': task.assignee_id} if task.assignee_id else None,
                    'project': {
                        'id': task.project.id,
                        'owner': {'id': task.project.owner_id},
                    } if task.project else None,
                }
            })

        if roi_template:
            context.update({
                'roi_template': {
                    'id': roi_template.id,
                    'owner': {'id': roi_template.created_by_id} if roi_template.created_by_id else None,
                }
            })

        if matching_session:
            context.update({
                'matching_session': {
                    'id': matching_session.id,
                    'status': matching_session.status,
                    'task': context.get('task'),
                    'roi_template': context.get('roi_template'),
                }
            })

        if isinstance(obj, DetectionResult):
            context.update({
                'detection_result': {
                    'id': obj.id,
                    'is_confirmed': obj.is_confirmed,
                    'matching_session': context.get('matching_session'),
                }
            })

        return context


class GroundTruthPermission(CalibrixPermission):
    """Permission class for Ground Truth export resources."""
    
    class Scopes(StrEnum):
        EXPORT = 'export'
        VIEW_STATUS = 'view:status'

    @classmethod
    def create_scope_list(cls, request: Request, view: ViewSet, obj: Any) -> list[str]:
        """Create list of permission scopes to check for ground truth operations."""
        scopes = []
        
        if view.action in ['export']:
            scopes.append(cls.Scopes.EXPORT)
        elif view.action in ['status']:
            scopes.append(cls.Scopes.VIEW_STATUS)
        
        return scopes

    @classmethod
    def create_context(cls, request: Request, view: ViewSet, obj: Any) -> dict:
        """Create context for ground truth permission evaluation."""
        # Get task and organization information
        task = None
        organization = None
        
        if isinstance(obj, Task):
            task = obj
            organization = task.project.organization if task.project else None
        elif hasattr(view, 'get_task'):
            task = view.get_task()
            organization = task.project.organization if task and task.project else None

        context = cls.create_base_context(request, view, obj, organization)
        
        if task:
            context.update({
                'task': {
                    'id': task.id,
                    'owner': {'id': task.owner_id},
                    'assignee': {'id': task.assignee_id} if task.assignee_id else None,
                    'project': {
                        'id': task.project.id,
                        'owner': {'id': task.project.owner_id},
                    } if task.project else None,
                }
            })

        return context


# Helper permission mixins

class TaskAccessMixin:
    """Mixin to check task access permissions."""
    
    def check_task_access(self, request, task_id: int) -> Task:
        """
        Check if user has access to the specified task.
        Raises PermissionDenied if access is not allowed.
        Returns the task if access is granted.
        """
        try:
            task = Task.objects.get(id=task_id)
        except Task.DoesNotExist:
            raise ValidationError(f"Task with ID {task_id} does not exist")
        
        # Check basic task access permissions using CVAT's permission system
        if not request.user.is_superuser:
            # Check if user is task owner or assignee
            if task.owner_id != request.user.id and task.assignee_id != request.user.id:
                # Check if user has project-level access
                if task.project:
                    if task.project.owner_id != request.user.id:
                        # Check organization membership if applicable
                        if task.project.organization:
                            membership = get_membership(request.user, task.project.organization)
                            if not membership:
                                raise PermissionDenied("You do not have access to this task")
                        else:
                            raise PermissionDenied("You do not have access to this task")
                else:
                    raise PermissionDenied("You do not have access to this task")
        
        return task


class ROITemplateAccessMixin:
    """Mixin to check ROI template access permissions."""
    
    def check_roi_template_access(self, request, roi_template_id: int) -> ROITemplate:
        """
        Check if user has access to the specified ROI template.
        Raises PermissionDenied if access is not allowed.
        Returns the ROI template if access is granted.
        """
        try:
            roi_template = ROITemplate.objects.select_related('task', 'task__project').get(id=roi_template_id)
        except ROITemplate.DoesNotExist:
            raise ValidationError(f"ROI template with ID {roi_template_id} does not exist")
        
        # Check task access first
        task_access_mixin = TaskAccessMixin()
        task_access_mixin.check_task_access(request, roi_template.task_id)
        
        return roi_template