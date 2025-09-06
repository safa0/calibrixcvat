# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

"""
Minimal Django settings for testing calibrix_matching models independently.
"""

import os
import tempfile

# Build paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'test-secret-key-only-for-testing'

# Test database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Installed apps - minimal for testing
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'cvat.apps.engine',
    'cvat.apps.calibrix_matching',
]

# Other required settings
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Minimal media settings for testing
MEDIA_ROOT = tempfile.mkdtemp()
STATIC_ROOT = tempfile.mkdtemp()