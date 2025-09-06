# Calibrix Dashboard Components

This directory contains the React/TypeScript components for the Calibrix matching dashboard feature.

## Overview

The Calibrix dashboard provides a comprehensive interface for:
- Creating and managing Regions of Interest (ROIs)
- Configuring and running object matching algorithms
- Reviewing and validating detected objects
- Exporting ground truth data in various formats

## Components

### CalibrixDashboard
Main container component that orchestrates the entire dashboard experience.

**Props:**
- `taskId`: Current CVAT task ID
- `currentFrame`: Current frame number
- `onROIChange`: Callback for ROI selection changes
- `onMatchingComplete`: Callback for matching completion
- `onExportComplete`: Callback for export completion

**Features:**
- Redux state management integration
- Error handling and loading states
- Responsive layout with Ant Design components

### ROICreator
Component for creating, editing, and managing ROIs on the canvas.

**Features:**
- Interactive canvas drawing for ROI creation
- Form-based ROI creation with validation
- ROI list management with edit/delete operations
- Drag and drop for ROI positioning and resizing
- Keyboard navigation support

**Props:**
- `rois`: Array of existing ROIs
- `selectedROI`: Currently selected ROI
- `onROICreate/Update/Delete/Select`: CRUD operation callbacks

### MatchingControls
Algorithm configuration and execution controls.

**Features:**
- Algorithm selection (SIFT, ORB, SURF, AKAZE)
- Parameter tuning with sliders and inputs
- Real-time matching progress tracking
- Start/stop matching operations

**Props:**
- `params`: Current algorithm parameters
- `isMatching`: Matching state
- `selectedROI`: Currently selected ROI
- `onParamsChange`: Parameter change callback
- `onStartMatching/StopMatching`: Control callbacks

### DetectionReviewer
Component for reviewing and validating detected objects.

**Features:**
- Object list with confidence scores
- Verify/reject object operations
- Bulk selection and operations
- Filtering by confidence, status, labels
- Notes and comments for objects

**Props:**
- `detectedObjects`: Array of detected objects
- `selectedObjects`: Currently selected object IDs
- `filters`: Current filtering options
- Various callback functions for object operations

### GroundTruthExporter
Export functionality for ground truth data.

**Features:**
- Multiple export formats (COCO, YOLO, Pascal VOC, CVAT)
- Export options configuration
- Progress tracking
- Batch export operations

**Props:**
- `groundTruthData`: Data to export
- `selectedObjects`: Objects to include in export
- `isExporting`: Export state
- `onExport`: Export callback

## State Management

The dashboard uses Redux for state management with the following structure:

```typescript
interface CalibrixState {
    rois: ROI[];
    matchingResults: MatchingResult[];
    currentROI: ROI | null;
    matchingParams: MatchingAlgorithmParams;
    isMatching: boolean;
    isExporting: boolean;
    selectedObjects: string[];
    detectionFilters: FilterOptions;
    error: string | null;
    loading: boolean;
}
```

### Actions
- ROI operations: create, update, delete, select
- Matching operations: start, stop, update parameters
- Detection review: verify, reject, select objects
- Export operations: initiate export, handle progress

## Routing

The dashboard is accessible via the route:
```
/tasks/{id}/calibrix
```

Where `{id}` is the CVAT task ID.

## Testing

### Test Coverage
- Unit tests for all components using Jest and React Testing Library
- Integration tests for component workflows
- Redux state management tests
- Mock implementations for external dependencies

### Test Files
- `__tests__/CalibrixDashboard.test.tsx`: Main dashboard component tests
- `__tests__/ROICreator.test.tsx`: ROI creation and management tests
- `__tests__/test-setup.ts`: Common test utilities and mocks

### Running Tests
```bash
# Run all Calibrix tests
npm test -- --testPathPattern=calibrix-dashboard

# Run specific component tests
npm test -- CalibrixDashboard.test.tsx
```

## Styling

The dashboard uses SCSS with Ant Design components for consistent styling.

### CSS Classes
- `.calibrix-dashboard`: Main container
- `.calibrix-section`: Section containers
- `.roi-creator`: ROI creation interface
- `.matching-controls`: Algorithm controls
- `.detection-reviewer`: Object review interface
- `.ground-truth-exporter`: Export interface

### Responsive Design
The dashboard is fully responsive with breakpoints for:
- Desktop (>= 1200px)
- Tablet (768px - 1199px)
- Mobile (< 768px)

### Dark Theme Support
Full dark theme compatibility with CVAT's theming system.

## TypeScript Interfaces

All components use strict TypeScript with comprehensive interfaces:
- `CalibrixState`: Redux state shape
- `ROI`: Region of Interest data structure
- `MatchingResult`: Algorithm output structure
- `DetectedObject`: Individual detection data
- Component prop interfaces for all components

## Integration with CVAT

The dashboard integrates seamlessly with CVAT:
- Uses existing authentication and routing
- Follows CVAT's component patterns and styling
- Integrates with task and project models
- Uses CVAT's notification system
- Supports internationalization

## Performance Optimizations

- React.memo for component memoization
- useMemo and useCallback for expensive operations
- Lazy loading of matching algorithms
- Virtualized lists for large datasets
- Debounced user inputs

## Accessibility

Full accessibility support including:
- ARIA labels and roles
- Keyboard navigation
- Screen reader compatibility
- Focus management
- High contrast support

## API Integration

The dashboard expects these API endpoints:
- `GET /api/tasks/{id}/calibrix/rois`: Fetch ROIs
- `POST /api/tasks/{id}/calibrix/rois`: Create ROI
- `PUT /api/tasks/{id}/calibrix/rois/{id}`: Update ROI
- `DELETE /api/tasks/{id}/calibrix/rois/{id}`: Delete ROI
- `POST /api/tasks/{id}/calibrix/match`: Start matching
- `GET /api/tasks/{id}/calibrix/results`: Get results
- `POST /api/tasks/{id}/calibrix/export`: Export data

## Future Enhancements

Potential improvements and extensions:
- Real-time matching progress via WebSocket
- Advanced filtering and search capabilities
- Batch operations for ROIs and objects
- Custom algorithm plugin system
- Machine learning model integration
- Collaborative annotation features
- Performance analytics and reporting