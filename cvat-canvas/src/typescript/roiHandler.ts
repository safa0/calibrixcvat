// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import * as SVG from 'svg.js';
import 'svg.draw.js';
import 'svg.draggable.js';
import 'svg.resize.js';
import 'svg.select.js';

import {
    translateToSVG,
    translateFromSVG,
    translateToCanvas,
    translateFromCanvas,
    pointsToNumberArray,
    displayShapeSize,
    ShapeSizeElement,
    stringifyPoints,
    BBox,
    Box,
    Point,
    readPointsFromShape,
    clamp,
    computeWrappingBox,
} from './shared';
import Crosshair from './crosshair';
import consts from './consts';
import {
    ROIDrawData,
    ROIEditData,
    ROIVisualizationData,
    ROITemplate,
    ROIDrawingMode,
    ROIVisualizationMode,
    ROIMatchingResult,
    Geometry,
    Configuration,
    UpdateReasons,
} from './canvasModel';

export interface ROIHandler {
    configure(configuration: Configuration): void;
    drawROI(roiDrawData: ROIDrawData, geometry: Geometry): void;
    editROI(roiEditData: ROIEditData, geometry: Geometry): void;
    visualizeROI(roiVisualizationData: ROIVisualizationData, geometry: Geometry): void;
    transform(geometry: Geometry): void;
    cancel(): void;
}

interface ROIDrawingState {
    isDrawing: boolean;
    currentMode: ROIDrawingMode | null;
    currentPoints: number[];
    template: ROITemplate | null;
    drawingShape: SVG.Shape | null;
    previewShape: SVG.Shape | null;
}

export class ROIHandlerImpl implements ROIHandler {
    private onROICreated: (roi: ROITemplate) => void;
    private onROIUpdated: (roi: ROITemplate) => void;
    private onROIDeleted: (roiId: string) => void;
    private canvas: SVG.Container;
    private text: SVG.Container;
    private geometry: Geometry;
    private configuration: Configuration;
    private crosshair: Crosshair | null;
    
    // ROI-specific state
    private roiDrawingState: ROIDrawingState;
    private roiShapes: Record<string, SVG.Shape>;
    private featurePointsGroup: SVG.G | null;
    private matchingResultsGroup: SVG.G | null;
    private templatePreviewGroup: SVG.G | null;
    
    // Drawing handlers for different ROI modes
    private rectangleHandler: ROIRectangleHandler;
    private polygonHandler: ROIPolygonHandler;
    private circleHandler: ROICircleHandler;
    private freehandHandler: ROIFreehandHandler;
    
    // Interaction state
    private isEditingROI: boolean;
    private editingROIId: string | null;
    private editingShape: SVG.Shape | null;
    
    // Performance optimization
    private renderCache: Map<string, { shape: SVG.Shape; timestamp: number }>;
    private debounceTimer: number | null;
    private isTransforming: boolean;

    public constructor(
        onROICreated: (roi: ROITemplate) => void,
        onROIUpdated: (roi: ROITemplate) => void,
        onROIDeleted: (roiId: string) => void,
        canvas: SVG.Container,
        text: SVG.Container,
    ) {
        this.onROICreated = onROICreated;
        this.onROIUpdated = onROIUpdated;
        this.onROIDeleted = onROIDeleted;
        this.canvas = canvas;
        this.text = text;
        this.geometry = null as any;
        this.configuration = {} as Configuration;
        this.crosshair = null;

        // Initialize ROI state
        this.roiDrawingState = {
            isDrawing: false,
            currentMode: null,
            currentPoints: [],
            template: null,
            drawingShape: null,
            previewShape: null,
        };

        this.roiShapes = {};
        this.featurePointsGroup = null;
        this.matchingResultsGroup = null;
        this.templatePreviewGroup = null;

        this.isEditingROI = false;
        this.editingROIId = null;
        this.editingShape = null;

        // Initialize performance optimization properties
        this.renderCache = new Map();
        this.debounceTimer = null;
        this.isTransforming = false;

        // Initialize drawing mode handlers
        this.rectangleHandler = new ROIRectangleHandler(this);
        this.polygonHandler = new ROIPolygonHandler(this);
        this.circleHandler = new ROICircleHandler(this);
        this.freehandHandler = new ROIFreehandHandler(this);
    }

    public configure(configuration: Configuration): void {
        this.configuration = { ...configuration };
    }

    public drawROI(roiDrawData: ROIDrawData, geometry: Geometry): void {
        this.geometry = geometry;

        if (roiDrawData.enabled && !this.roiDrawingState.isDrawing) {
            this.startROIDrawing(roiDrawData);
        } else if (!roiDrawData.enabled && this.roiDrawingState.isDrawing) {
            this.finishROIDrawing();
        }

        // Update drawing mode if changed
        if (roiDrawData.enabled && roiDrawData.mode !== this.roiDrawingState.currentMode) {
            this.changeDrawingMode(roiDrawData.mode!);
        }
    }

    public editROI(roiEditData: ROIEditData, geometry: Geometry): void {
        this.geometry = geometry;

        if (roiEditData.enabled && !this.isEditingROI) {
            this.startROIEditing(roiEditData);
        } else if (!roiEditData.enabled && this.isEditingROI) {
            this.finishROIEditing();
        }
    }

    public visualizeROI(roiVisualizationData: ROIVisualizationData, geometry: Geometry): void {
        this.geometry = geometry;

        this.clearVisualization();

        if (roiVisualizationData.enabled) {
            this.renderROIVisualization(roiVisualizationData);
        }
    }

    public transform(geometry: Geometry): void {
        this.geometry = geometry;

        // Debounce transforms to avoid excessive updates during continuous transformations
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }

        this.isTransforming = true;

        this.debounceTimer = window.setTimeout(() => {
            this.performTransform();
            this.isTransforming = false;
            this.debounceTimer = null;
        }, 16); // ~60fps
    }

    private performTransform(): void {
        // Transform all ROI shapes with batching
        const shapesToTransform = Object.values(this.roiShapes);
        
        // Use requestAnimationFrame for smooth transformations
        if (shapesToTransform.length > 0) {
            requestAnimationFrame(() => {
                shapesToTransform.forEach((shape) => {
                    this.transformROIShape(shape);
                });
            });
        }

        // Transform visualization groups
        const groups = [this.featurePointsGroup, this.matchingResultsGroup, this.templatePreviewGroup]
            .filter(group => group !== null);
        
        if (groups.length > 0) {
            requestAnimationFrame(() => {
                groups.forEach(group => this.transformGroup(group!));
            });
        }

        // Transform drawing state
        if (this.roiDrawingState.drawingShape || this.roiDrawingState.previewShape) {
            requestAnimationFrame(() => {
                if (this.roiDrawingState.drawingShape) {
                    this.transformROIShape(this.roiDrawingState.drawingShape);
                }
                if (this.roiDrawingState.previewShape) {
                    this.transformROIShape(this.roiDrawingState.previewShape);
                }
            });
        }
    }

    public cancel(): void {
        this.finishROIDrawing();
        this.finishROIEditing();
        this.clearVisualization();
        this.cleanup();
    }

    private cleanup(): void {
        // Clear timers
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }

        // Clear render cache
        this.renderCache.clear();
        
        // Reset transformation state
        this.isTransforming = false;
    }

    // Private methods

    private startROIDrawing(roiDrawData: ROIDrawData): void {
        this.roiDrawingState = {
            isDrawing: true,
            currentMode: roiDrawData.mode || ROIDrawingMode.RECTANGLE,
            currentPoints: [],
            template: roiDrawData.template || null,
            drawingShape: null,
            previewShape: null,
        };

        // Enable crosshair if requested
        if (roiDrawData.template && roiDrawData.template.points.length > 0) {
            this.showCrosshair();
        }

        // Start drawing with the appropriate handler
        this.getDrawingHandler().startDrawing();
    }

    private finishROIDrawing(): void {
        if (this.roiDrawingState.isDrawing) {
            this.getDrawingHandler().finishDrawing();
            this.hideCrosshair();
            
            // Clean up drawing state
            if (this.roiDrawingState.drawingShape) {
                this.roiDrawingState.drawingShape.remove();
            }
            if (this.roiDrawingState.previewShape) {
                this.roiDrawingState.previewShape.remove();
            }

            this.roiDrawingState = {
                isDrawing: false,
                currentMode: null,
                currentPoints: [],
                template: null,
                drawingShape: null,
                previewShape: null,
            };
        }
    }

    private changeDrawingMode(newMode: ROIDrawingMode): void {
        if (this.roiDrawingState.isDrawing) {
            this.getDrawingHandler().finishDrawing();
            this.roiDrawingState.currentMode = newMode;
            this.getDrawingHandler().startDrawing();
        }
    }

    private startROIEditing(roiEditData: ROIEditData): void {
        this.isEditingROI = true;
        this.editingROIId = roiEditData.roiId || null;

        if (this.editingROIId && this.roiShapes[this.editingROIId]) {
            this.editingShape = this.roiShapes[this.editingROIId];
            this.makeROIEditable(this.editingShape, roiEditData);
        }
    }

    private finishROIEditing(): void {
        if (this.isEditingROI && this.editingShape) {
            this.makeROIStatic(this.editingShape);
        }

        this.isEditingROI = false;
        this.editingROIId = null;
        this.editingShape = null;
    }

    private renderROIVisualization(data: ROIVisualizationData): void {
        switch (data.visualizationMode) {
            case ROIVisualizationMode.TEMPLATE_PREVIEW:
                this.renderTemplatePreview(data.templates);
                break;
            case ROIVisualizationMode.FEATURE_POINTS:
                this.renderFeaturePoints(data.templates);
                break;
            case ROIVisualizationMode.MATCHING_RESULTS:
                this.renderMatchingResults(data.matchingResults || []);
                break;
        }

        // Highlight specific ROI if requested
        if (data.highlightedROI) {
            this.highlightROI(data.highlightedROI);
        }
    }

    private renderTemplatePreview(templates: ROITemplate[]): void {
        this.templatePreviewGroup = this.canvas.group().addClass('cvat_roi_template_preview_group');

        templates.forEach((template) => {
            const shape = this.createROIShape(template, true);
            if (shape) {
                this.templatePreviewGroup!.add(shape);
                this.roiShapes[template.id] = shape;
            }
        });
    }

    private renderFeaturePoints(templates: ROITemplate[]): void {
        this.featurePointsGroup = this.canvas.group().addClass('cvat_roi_feature_points_group');

        templates.forEach((template) => {
            if (template.featurePoints && template.featurePoints.length >= 2) {
                // Render template shape first
                const templateShape = this.createROIShape(template, false);
                if (templateShape) {
                    this.featurePointsGroup!.add(templateShape);
                }

                // Render feature points
                for (let i = 0; i < template.featurePoints.length; i += 2) {
                    const x = template.featurePoints[i];
                    const y = template.featurePoints[i + 1];
                    
                    const point = this.canvas.circle(consts.ROI_FEATURE_POINT_RADIUS * 2)
                        .cx(x)
                        .cy(y)
                        .fill(consts.ROI_FEATURE_POINT_COLOR)
                        .stroke({ width: 1, color: '#000000' })
                        .addClass('cvat_roi_feature_point');
                    
                    this.featurePointsGroup!.add(point);
                }
            }
        });
    }

    private renderMatchingResults(matchingResults: ROIMatchingResult[]): void {
        this.matchingResultsGroup = this.canvas.group().addClass('cvat_roi_matching_results_group');

        matchingResults.forEach((result) => {
            // Render bounding box
            const [x1, y1, x2, y2] = result.boundingBox;
            const bbox = this.canvas.rect(x2 - x1, y2 - y1)
                .x(x1)
                .y(y1)
                .fill('none')
                .stroke({
                    width: consts.ROI_STROKE_WIDTH,
                    color: this.getConfidenceColor(result.confidence),
                })
                .opacity(consts.ROI_MATCHING_RESULT_OPACITY)
                .addClass('cvat_roi_matching_result');

            this.matchingResultsGroup!.add(bbox);

            // Add confidence text
            const confidenceText = this.text.text(`${(result.confidence * 100).toFixed(1)}%`)
                .x(x1)
                .y(y1 - 5)
                .fill(this.getConfidenceColor(result.confidence))
                .addClass('cvat_roi_confidence_text');

            this.matchingResultsGroup!.add(confidenceText);

            // Render feature matches if available
            if (result.featureMatches) {
                result.featureMatches.forEach((match) => {
                    const line = this.canvas.line(
                        match.templatePoint[0], match.templatePoint[1],
                        match.imagePoint[0], match.imagePoint[1]
                    )
                    .stroke({
                        width: 1,
                        color: this.getConfidenceColor(match.confidence),
                        opacity: 0.6,
                    })
                    .addClass('cvat_roi_feature_match');

                    this.matchingResultsGroup!.add(line);
                });
            }
        });
    }

    private createROIShape(template: ROITemplate, isPreview: boolean): SVG.Shape | null {
        const points = template.points;
        const color = template.color || consts.ROI_DEFAULT_COLOR;
        const opacity = isPreview ? consts.ROI_TEMPLATE_OPACITY : 1.0;

        let shape: SVG.Shape | null = null;

        switch (template.type) {
            case ROIDrawingMode.RECTANGLE:
                if (points.length >= 4) {
                    const [x1, y1, x2, y2] = points;
                    shape = this.canvas.rect(Math.abs(x2 - x1), Math.abs(y2 - y1))
                        .x(Math.min(x1, x2))
                        .y(Math.min(y1, y2));
                }
                break;

            case ROIDrawingMode.CIRCLE:
                if (points.length >= 3) {
                    const [cx, cy, radius] = points;
                    shape = this.canvas.circle(radius * 2)
                        .cx(cx)
                        .cy(cy);
                }
                break;

            case ROIDrawingMode.POLYGON:
            case ROIDrawingMode.FREEHAND:
                if (points.length >= 6) {
                    const pointPairs: number[][] = [];
                    for (let i = 0; i < points.length; i += 2) {
                        pointPairs.push([points[i], points[i + 1]]);
                    }
                    shape = this.canvas.polygon(pointPairs);
                }
                break;
        }

        if (shape) {
            shape
                .fill(isPreview ? 'none' : color)
                .stroke({
                    width: consts.ROI_STROKE_WIDTH,
                    color: color,
                })
                .opacity(opacity)
                .addClass(`cvat_roi_${template.type}`)
                .data('roi-id', template.id);

            // Add event handlers for interaction
            this.addROIEventHandlers(shape, template);
        }

        return shape;
    }

    private addROIEventHandlers(shape: SVG.Shape, template: ROITemplate): void {
        shape
            .on('mouseenter', () => {
                shape.stroke({ width: consts.ROI_SELECTED_STROKE_WIDTH });
            })
            .on('mouseleave', () => {
                shape.stroke({ width: consts.ROI_STROKE_WIDTH });
            })
            .on('click', (event: MouseEvent) => {
                event.stopPropagation();
                this.selectROI(template.id);
            })
            .on('dblclick', (event: MouseEvent) => {
                event.stopPropagation();
                this.editROI({
                    enabled: true,
                    roiId: template.id,
                    allowResize: true,
                    allowMove: true,
                    allowDelete: true,
                }, this.geometry);
            });
    }

    private makeROIEditable(shape: SVG.Shape, editData: ROIEditData): void {
        shape.addClass('cvat_roi_editing');

        if (editData.allowMove) {
            (shape as any).draggable();
        }

        if (editData.allowResize) {
            (shape as any).selectize({
                rotationPoint: false,
                deepSelect: true,
                pointSize: (size: number) => size / this.geometry.scale,
            });
        }

        // Add delete handler if allowed
        if (editData.allowDelete) {
            shape.on('keydown.roi', (event: KeyboardEvent) => {
                if (event.key === 'Delete' || event.key === 'Backspace') {
                    this.deleteROI(editData.roiId!);
                }
            });
        }
    }

    private makeROIStatic(shape: SVG.Shape): void {
        shape.removeClass('cvat_roi_editing');
        
        // Remove draggable
        if ((shape as any).draggable) {
            (shape as any).draggable(false);
        }

        // Remove selectize
        if ((shape as any).selectize) {
            (shape as any).selectize(false);
        }

        // Remove delete handler
        shape.off('keydown.roi');
    }

    private selectROI(roiId: string): void {
        // Remove previous selection
        this.canvas.select('.cvat_roi_selected').removeClass('cvat_roi_selected');

        // Add selection to current ROI
        if (this.roiShapes[roiId]) {
            this.roiShapes[roiId].addClass('cvat_roi_selected');
        }
    }

    private highlightROI(roiId: string): void {
        if (this.roiShapes[roiId]) {
            this.roiShapes[roiId]
                .stroke({ color: consts.ROI_SELECTED_COLOR })
                .addClass('cvat_roi_highlighted');
        }
    }

    private deleteROI(roiId: string): void {
        if (this.roiShapes[roiId]) {
            this.roiShapes[roiId].remove();
            delete this.roiShapes[roiId];
            this.onROIDeleted(roiId);
        }
    }

    private clearVisualization(): void {
        if (this.templatePreviewGroup) {
            this.templatePreviewGroup.remove();
            this.templatePreviewGroup = null;
        }
        if (this.featurePointsGroup) {
            this.featurePointsGroup.remove();
            this.featurePointsGroup = null;
        }
        if (this.matchingResultsGroup) {
            this.matchingResultsGroup.remove();
            this.matchingResultsGroup = null;
        }

        // Clear shapes registry
        this.roiShapes = {};
    }

    private showCrosshair(): void {
        if (!this.crosshair) {
            this.crosshair = new Crosshair();
        }
        this.crosshair.show(this.canvas, this.geometry);
    }

    private hideCrosshair(): void {
        if (this.crosshair) {
            this.crosshair.hide();
        }
    }

    private transformROIShape(shape: SVG.Shape): void {
        // Apply current geometry transformation to the shape
        const { offset, scale, angle } = this.geometry;
        
        shape.transform({
            scale: scale,
            rotation: angle,
            origin: 'center center',
        });
    }

    private transformGroup(group: SVG.G): void {
        const { offset, scale, angle } = this.geometry;
        
        group.transform({
            scale: scale,
            rotation: angle,
            origin: 'center center',
        });
    }

    private getDrawingHandler(): ROIDrawingHandler {
        switch (this.roiDrawingState.currentMode) {
            case ROIDrawingMode.RECTANGLE:
                return this.rectangleHandler;
            case ROIDrawingMode.POLYGON:
                return this.polygonHandler;
            case ROIDrawingMode.CIRCLE:
                return this.circleHandler;
            case ROIDrawingMode.FREEHAND:
                return this.freehandHandler;
            default:
                return this.rectangleHandler;
        }
    }

    private getConfidenceColor(confidence: number): string {
        if (confidence >= consts.ROI_CONFIDENCE_THRESHOLD) {
            return '#00ff00'; // Green for high confidence
        } else if (confidence >= 0.5) {
            return '#ffff00'; // Yellow for medium confidence
        } else {
            return '#ff0000'; // Red for low confidence
        }
    }

    // Public accessors for drawing handlers
    public getCanvas(): SVG.Container {
        return this.canvas;
    }

    public getText(): SVG.Container {
        return this.text;
    }

    public getGeometry(): Geometry {
        return this.geometry;
    }

    public getDrawingState(): ROIDrawingState {
        return this.roiDrawingState;
    }

    public setDrawingState(state: Partial<ROIDrawingState>): void {
        this.roiDrawingState = { ...this.roiDrawingState, ...state };
    }

    public notifyROICreated(roi: ROITemplate): void {
        this.onROICreated(roi);
    }

    public notifyROIUpdated(roi: ROITemplate): void {
        this.onROIUpdated(roi);
    }
}

// Base interface for ROI drawing mode handlers
interface ROIDrawingHandler {
    startDrawing(): void;
    finishDrawing(): void;
    handleMouseDown(event: MouseEvent): void;
    handleMouseMove(event: MouseEvent): void;
    handleMouseUp(event: MouseEvent): void;
}

// Rectangle drawing handler
class ROIRectangleHandler implements ROIDrawingHandler {
    private roiHandler: ROIHandlerImpl;
    private startPoint: Point | null = null;

    constructor(roiHandler: ROIHandlerImpl) {
        this.roiHandler = roiHandler;
    }

    startDrawing(): void {
        this.startPoint = null;
        const canvas = this.roiHandler.getCanvas();
        
        canvas.on('mousedown.roi.rectangle', (event: MouseEvent) => {
            this.handleMouseDown(event);
        });
    }

    finishDrawing(): void {
        const canvas = this.roiHandler.getCanvas();
        canvas.off('mousedown.roi.rectangle');
        canvas.off('mousemove.roi.rectangle');
        canvas.off('mouseup.roi.rectangle');
        this.startPoint = null;
    }

    handleMouseDown(event: MouseEvent): void {
        const canvas = this.roiHandler.getCanvas();
        const geometry = this.roiHandler.getGeometry();
        
        this.startPoint = translateToSVG((canvas.node as any), [event.clientX, event.clientY]);

        // Create preview rectangle
        const rect = canvas.rect(0, 0)
            .x(this.startPoint[0])
            .y(this.startPoint[1])
            .fill('none')
            .stroke({
                width: consts.ROI_STROKE_WIDTH,
                color: consts.ROI_DEFAULT_COLOR,
                dasharray: '5,5',
            })
            .addClass('cvat_roi_rectangle_preview');

        this.roiHandler.setDrawingState({ previewShape: rect });

        canvas.on('mousemove.roi.rectangle', (moveEvent: MouseEvent) => {
            this.handleMouseMove(moveEvent);
        });

        canvas.on('mouseup.roi.rectangle', (upEvent: MouseEvent) => {
            this.handleMouseUp(upEvent);
        });
    }

    handleMouseMove(event: MouseEvent): void {
        if (!this.startPoint) return;

        const canvas = this.roiHandler.getCanvas();
        const drawingState = this.roiHandler.getDrawingState();
        
        if (drawingState.previewShape) {
            const currentPoint = translateToSVG((canvas.node as any), [event.clientX, event.clientY]);
            const width = Math.abs(currentPoint[0] - this.startPoint[0]);
            const height = Math.abs(currentPoint[1] - this.startPoint[1]);
            const x = Math.min(this.startPoint[0], currentPoint[0]);
            const y = Math.min(this.startPoint[1], currentPoint[1]);

            (drawingState.previewShape as any)
                .width(width)
                .height(height)
                .x(x)
                .y(y);
        }
    }

    handleMouseUp(event: MouseEvent): void {
        if (!this.startPoint) return;

        const canvas = this.roiHandler.getCanvas();
        const endPoint = translateToSVG((canvas.node as any), [event.clientX, event.clientY]);
        
        // Create ROI template
        const roi: ROITemplate = {
            id: `roi_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
            name: 'Rectangle ROI',
            type: ROIDrawingMode.RECTANGLE,
            points: [this.startPoint[0], this.startPoint[1], endPoint[0], endPoint[1]],
        };

        this.roiHandler.notifyROICreated(roi);
        this.finishDrawing();
    }
}

// Polygon drawing handler
class ROIPolygonHandler implements ROIDrawingHandler {
    private roiHandler: ROIHandlerImpl;
    private points: number[] = [];

    constructor(roiHandler: ROIHandlerImpl) {
        this.roiHandler = roiHandler;
    }

    startDrawing(): void {
        this.points = [];
        // Implementation for polygon drawing
    }

    finishDrawing(): void {
        this.points = [];
        // Clean up polygon drawing
    }

    handleMouseDown(event: MouseEvent): void {
        // Add point to polygon
    }

    handleMouseMove(event: MouseEvent): void {
        // Update preview line
    }

    handleMouseUp(event: MouseEvent): void {
        // Handle polygon completion
    }
}

// Circle drawing handler
class ROICircleHandler implements ROIDrawingHandler {
    private roiHandler: ROIHandlerImpl;
    private centerPoint: Point | null = null;

    constructor(roiHandler: ROIHandlerImpl) {
        this.roiHandler = roiHandler;
    }

    startDrawing(): void {
        this.centerPoint = null;
        // Implementation for circle drawing
    }

    finishDrawing(): void {
        this.centerPoint = null;
        // Clean up circle drawing
    }

    handleMouseDown(event: MouseEvent): void {
        // Set circle center
    }

    handleMouseMove(event: MouseEvent): void {
        // Update circle radius
    }

    handleMouseUp(event: MouseEvent): void {
        // Finalize circle
    }
}

// Freehand drawing handler
class ROIFreehandHandler implements ROIDrawingHandler {
    private roiHandler: ROIHandlerImpl;
    private points: number[] = [];
    private isDrawing = false;

    constructor(roiHandler: ROIHandlerImpl) {
        this.roiHandler = roiHandler;
    }

    startDrawing(): void {
        this.points = [];
        this.isDrawing = false;
        // Implementation for freehand drawing
    }

    finishDrawing(): void {
        this.points = [];
        this.isDrawing = false;
        // Clean up freehand drawing
    }

    handleMouseDown(event: MouseEvent): void {
        this.isDrawing = true;
        // Start freehand path
    }

    handleMouseMove(event: MouseEvent): void {
        if (this.isDrawing) {
            // Add point to path
        }
    }

    handleMouseUp(event: MouseEvent): void {
        this.isDrawing = false;
        // Finalize freehand path
    }
}