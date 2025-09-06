# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

from django.urls import path, include
from rest_framework import routers

from . import views

# Create API router for Calibrix matching endpoints
router = routers.DefaultRouter(trailing_slash=False)

# Register ViewSets with the router
router.register(r'roi-templates', views.ROITemplateViewSet)
router.register(r'matching-sessions', views.MatchingSessionViewSet)
router.register(r'detections', views.DetectionResultViewSet)
router.register(r'ground-truth', views.GroundTruthViewSet, basename='ground-truth')

# URL patterns for the Calibrix matching app
urlpatterns = [
    # API endpoints (versioned)
    path('calibrix/', include(router.urls)),
    
    # Additional custom endpoints that don't fit the ViewSet pattern
    # These could be added later if needed for specific functionality
]

# Export the router for potential use in main URL configuration
calibrix_router = router