// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import { ObjectState } from 'cvat-core-wrapper';

export interface ROI {
    id: string;
    name: string;
    coordinates: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
    frame: number;
    active: boolean;
    created: string;
    updated: string;
}

export interface MatchingAlgorithmParams {
    algorithm: 'sift' | 'orb' | 'surf' | 'akaze';
    threshold: number;
    maxFeatures: number;
    confidenceThreshold: number;
    ransacThreshold: number;
    ratioThreshold: number;
}

export interface MatchingResult {
    id: string;
    roiId: string;
    detectedObjects: DetectedObject[];
    matchingScore: number;
    confidence: number;
    timestamp: string;
    algorithmUsed: string;
    parameters: MatchingAlgorithmParams;
}

export interface DetectedObject {
    id: string;
    boundingBox: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
    confidence: number;
    label: string;
    features: FeaturePoint[];
    verified: boolean;
    rejected: boolean;
    notes?: string;
}

export interface FeaturePoint {
    x: number;
    y: number;
    descriptor: number[];
    keypoint: {
        angle: number;
        size: number;
        response: number;
    };
}

export interface GroundTruthData {
    roiId: string;
    objects: GroundTruthObject[];
    exportFormat: 'coco' | 'yolo' | 'voc' | 'cvat';
    metadata: {
        taskId: number;
        frameCount: number;
        created: string;
        creator: string;
    };
}

export interface GroundTruthObject {
    id: string;
    label: string;
    boundingBox: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
    verified: boolean;
    attributes: Record<string, string | number | boolean>;
}

export interface CalibrixState {
    rois: ROI[];
    matchingResults: MatchingResult[];
    currentROI: ROI | null;
    matchingParams: MatchingAlgorithmParams;
    isMatching: boolean;
    isExporting: boolean;
    selectedObjects: string[];
    detectionFilters: {
        minConfidence: number;
        showVerified: boolean;
        showRejected: boolean;
        labelFilter: string[];
    };
    error: string | null;
    loading: boolean;
}

export interface CalibrixDashboardProps {
    taskId: number;
    currentFrame: number;
    onROIChange: (roi: ROI) => void;
    onMatchingComplete: (results: MatchingResult[]) => void;
    onExportComplete: (data: GroundTruthData) => void;
}

export interface ROICreatorProps {
    rois: ROI[];
    currentFrame: number;
    onROICreate: (roi: Omit<ROI, 'id' | 'created' | 'updated'>) => void;
    onROIUpdate: (roi: ROI) => void;
    onROIDelete: (roiId: string) => void;
    onROISelect: (roiId: string) => void;
    selectedROI: ROI | null;
    loading: boolean;
    canvasRef?: React.RefObject<HTMLCanvasElement>;
}

export interface MatchingControlsProps {
    params: MatchingAlgorithmParams;
    isMatching: boolean;
    onParamsChange: (params: MatchingAlgorithmParams) => void;
    onStartMatching: (roiId: string) => void;
    onStopMatching: () => void;
    selectedROI: ROI | null;
    disabled: boolean;
}

export interface DetectionReviewerProps {
    detectedObjects: DetectedObject[];
    selectedObjects: string[];
    onObjectSelect: (objectIds: string[]) => void;
    onObjectVerify: (objectId: string, verified: boolean) => void;
    onObjectReject: (objectId: string, rejected: boolean) => void;
    onObjectNote: (objectId: string, note: string) => void;
    filters: CalibrixState['detectionFilters'];
    onFiltersChange: (filters: CalibrixState['detectionFilters']) => void;
    loading: boolean;
}

export interface GroundTruthExporterProps {
    groundTruthData: GroundTruthData[];
    selectedObjects: string[];
    isExporting: boolean;
    onExport: (format: GroundTruthData['exportFormat'], options: ExportOptions) => void;
    taskId: number;
}

export interface ExportOptions {
    includeImages: boolean;
    includeAnnotations: boolean;
    includeMetadata: boolean;
    minConfidence: number;
    verifiedOnly: boolean;
    customAttributes: string[];
}

export interface CalibrixError {
    type: 'roi_creation' | 'matching' | 'export' | 'validation';
    message: string;
    details?: any;
    timestamp: string;
}

export interface MatchingProgress {
    current: number;
    total: number;
    status: 'initializing' | 'extracting_features' | 'matching' | 'filtering' | 'complete' | 'error';
    message: string;
}