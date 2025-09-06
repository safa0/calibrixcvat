// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

/**
 * Test setup configuration for Calibrix Dashboard components
 * This file provides common mocks and utilities for component testing
 */

// Mock Redux store and actions
export const mockStore = {
    calibrix: {
        rois: [],
        matchingResults: [],
        currentROI: null,
        matchingParams: {
            algorithm: 'sift' as const,
            threshold: 0.8,
            maxFeatures: 5000,
            confidenceThreshold: 0.7,
            ransacThreshold: 3.0,
            ratioThreshold: 0.75,
        },
        isMatching: false,
        isExporting: false,
        selectedObjects: [],
        detectionFilters: {
            minConfidence: 0.5,
            showVerified: true,
            showRejected: false,
            labelFilter: [],
        },
        error: null,
        loading: false,
    },
};

export const mockActions = {
    createROIRequest: jest.fn(),
    updateROIRequest: jest.fn(),
    deleteROIRequest: jest.fn(),
    selectROI: jest.fn(),
    startMatchingRequest: jest.fn(),
    stopMatching: jest.fn(),
    verifyObject: jest.fn(),
    rejectObject: jest.fn(),
    selectObjects: jest.fn(),
    exportGroundTruthRequest: jest.fn(),
    updateMatchingParams: jest.fn(),
    updateDetectionFilters: jest.fn(),
};

// Mock ROI data
export const mockROI = {
    id: 'roi-1',
    name: 'Test ROI',
    coordinates: { x: 10, y: 10, width: 100, height: 100 },
    frame: 0,
    active: true,
    created: '2025-01-01T00:00:00Z',
    updated: '2025-01-01T00:00:00Z',
};

// Mock detected object data
export const mockDetectedObject = {
    id: 'obj-1',
    boundingBox: { x: 20, y: 20, width: 50, height: 50 },
    confidence: 0.85,
    label: 'person',
    features: [],
    verified: false,
    rejected: false,
    notes: '',
};

// Mock matching result data
export const mockMatchingResult = {
    id: 'result-1',
    roiId: 'roi-1',
    detectedObjects: [mockDetectedObject],
    matchingScore: 0.9,
    confidence: 0.85,
    timestamp: '2025-01-01T00:00:00Z',
    algorithmUsed: 'sift',
    parameters: mockStore.calibrix.matchingParams,
};

// Mock Canvas ref
export const mockCanvasRef = {
    current: document.createElement('canvas'),
};

// Mock common props
export const mockProps = {
    taskId: 1,
    currentFrame: 0,
    onROIChange: jest.fn(),
    onMatchingComplete: jest.fn(),
    onExportComplete: jest.fn(),
};

// Reset all mocks
export const resetMocks = () => {
    Object.values(mockActions).forEach(mock => mock.mockClear());
    Object.values(mockProps).forEach(mock => {
        if (jest.isMockFunction(mock)) {
            mock.mockClear();
        }
    });
};

// Setup for each test
export const setupTest = () => {
    resetMocks();
    return {
        store: mockStore,
        actions: mockActions,
        props: mockProps,
        mockData: {
            roi: mockROI,
            detectedObject: mockDetectedObject,
            matchingResult: mockMatchingResult,
        },
    };
};