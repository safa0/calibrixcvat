# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

This project uses both Python (Django backend) and Node.js (frontend) with Yarn as the package manager.

### Frontend Development

```bash
# Build all frontend packages
yarn build:cvat-ui
yarn build:cvat-canvas
yarn build:cvat-canvas3d
yarn build:cvat-core
yarn build:cvat-data

# Start development server for UI
yarn start:cvat-ui

# Linting
yarn precommit:cvat-ui         # UI linting and fixes
yarn precommit:cvat-core       # Core linting and fixes
yarn precommit:cvat-canvas     # Canvas linting and fixes
yarn precommit:cvat-canvas3d   # Canvas3D linting and fixes
yarn precommit:cvat-data       # Data linting and fixes
yarn precommit:cvat-tests      # Test linting and fixes

# Type checking (for specific packages)
cd cvat-ui && yarn type-check
cd cvat-core && yarn type-check
```

### Backend Development

```bash
# Django management
python manage.py <command>

# Style checking (configured in pyproject.toml)
# Uses Black (line-length 100) and isort
```

### Docker Development

```bash
# Start full development environment
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Database access (when running)
# PostgreSQL available at localhost:5432
```

### Testing

```bash
# Frontend tests
cd tests && yarn test  # Cypress tests

# Python tests
cd tests/python && python -m pytest
```

## Architecture Overview

CVAT is a Computer Vision Annotation Tool with a multi-tiered architecture:

### Core Components

1. **cvat/** - Django backend server
   - **apps/** - Django applications:
     - `engine/` - Core annotation engine, models, views, serializers
     - `dataset_manager/` - Dataset import/export functionality
     - `organizations/` - Multi-tenant organization support
     - `iam/` - Identity and Access Management
     - `quality_control/` - Annotation quality assurance
     - `events/` - Event logging and analytics
     - `webhooks/` - Webhook integrations
     - `lambda_manager/` - Serverless function management
   - **settings/** - Django configuration (base.py contains main settings)

2. **cvat-ui/** - React/TypeScript frontend
   - Single-page application built with React 18, Ant Design UI
   - Uses Redux for state management
   - TypeScript for type safety

3. **cvat-core/** - TypeScript core library
   - Client-side API interface for CVAT backend
   - Shared between UI and external integrations
   - Handles authentication, API calls, data models

4. **cvat-canvas/** & **cvat-canvas3d/** - Annotation canvases
   - 2D and 3D annotation rendering engines
   - Built with Fabric.js for 2D canvas operations
   - WebGL-based 3D point cloud annotation

5. **cvat-data/** - Data handling utilities
   - Dataset format parsers and converters
   - Annotation format support (YOLO, COCO, Pascal VOC, etc.)

6. **serverless/** - Auto-annotation functions
   - ML model integrations (PyTorch, OpenVINO, ONNX, TensorFlow)
   - Serverless functions for automatic labeling
   - GPU and CPU deployment options

### Key Technologies

- **Backend**: Django, PostgreSQL, Redis, RQ (job queue)
- **Frontend**: React 18, TypeScript, Ant Design, Redux, Webpack
- **Canvas**: Fabric.js, WebGL, ONNX Runtime
- **Deployment**: Docker, Kubernetes (Helm charts available)
- **Testing**: Cypress (E2E), pytest (Python)

### Workspaces Structure

This is a Yarn workspace monorepo with the following packages:
- `cvat-data` - Data utilities
- `cvat-core` - Core API client
- `cvat-canvas` - 2D annotation canvas
- `cvat-canvas3d` - 3D annotation canvas  
- `cvat-ui` - Main React application

### Development Workflow

1. Backend development uses Django with debug support (CVAT_DEBUG_ENABLED)
2. Frontend development uses Webpack dev server with hot reload
3. Pre-commit hooks run ESLint and type checking automatically
4. Code style enforced via Black (Python) and ESLint (TypeScript)
5. Docker Compose provides full development environment

### Important Files

- `docker-compose.yml` - Production Docker setup
- `docker-compose.dev.yml` - Development overrides
- `pyproject.toml` - Python code style configuration (Black, isort)
- `.eslintrc.cjs` - JavaScript/TypeScript linting rules
- `manage.py` - Django management script
- `backend_entrypoint.sh` - Docker backend initialization