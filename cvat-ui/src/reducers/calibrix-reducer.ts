// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import { CalibrixActions, CalibrixActionTypes } from '../actions/calibrix-actions';
import { CalibrixState, MatchingAlgorithmParams } from '../components/calibrix-dashboard/types';

const defaultMatchingParams: MatchingAlgorithmParams = {
    algorithm: 'sift',
    threshold: 0.8,
    maxFeatures: 5000,
    confidenceThreshold: 0.7,
    ransacThreshold: 3.0,
    ratioThreshold: 0.75,
};

const defaultState: CalibrixState = {
    rois: [],
    matchingResults: [],
    currentROI: null,
    matchingParams: defaultMatchingParams,
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
};

export default function calibrixReducer(
    state: CalibrixState = defaultState,
    action: CalibrixActions,
): CalibrixState {
    switch (action.type) {
        // ROI Actions
        case CalibrixActionTypes.CREATE_ROI_REQUEST:
        case CalibrixActionTypes.UPDATE_ROI_REQUEST:
        case CalibrixActionTypes.DELETE_ROI_REQUEST:
        case CalibrixActionTypes.LOAD_ROIS_REQUEST:
            return {
                ...state,
                loading: true,
                error: null,
            };
        
        case CalibrixActionTypes.CREATE_ROI_SUCCESS:
            return {
                ...state,
                rois: [...state.rois, action.payload.roi],
                loading: false,
                error: null,
            };
        
        case CalibrixActionTypes.UPDATE_ROI_SUCCESS:
            return {
                ...state,
                rois: state.rois.map(roi => 
                    roi.id === action.payload.roi.id ? action.payload.roi : roi
                ),
                currentROI: state.currentROI?.id === action.payload.roi.id 
                    ? action.payload.roi 
                    : state.currentROI,
                loading: false,
                error: null,
            };
        
        case CalibrixActionTypes.DELETE_ROI_SUCCESS:
            return {
                ...state,
                rois: state.rois.filter(roi => roi.id !== action.payload.roiId),
                currentROI: state.currentROI?.id === action.payload.roiId 
                    ? null 
                    : state.currentROI,
                matchingResults: state.matchingResults.filter(
                    result => result.roiId !== action.payload.roiId
                ),
                loading: false,
                error: null,
            };
        
        case CalibrixActionTypes.LOAD_ROIS_SUCCESS:
            return {
                ...state,
                rois: action.payload.rois,
                loading: false,
                error: null,
            };
        
        case CalibrixActionTypes.CREATE_ROI_FAILED:
        case CalibrixActionTypes.UPDATE_ROI_FAILED:
        case CalibrixActionTypes.DELETE_ROI_FAILED:
        case CalibrixActionTypes.LOAD_ROIS_FAILED:
            return {
                ...state,
                loading: false,
                error: action.payload.error.message,
            };
        
        case CalibrixActionTypes.SELECT_ROI:
            return {
                ...state,
                currentROI: action.payload.roiId 
                    ? state.rois.find(roi => roi.id === action.payload.roiId) || null
                    : null,
            };
        
        // Matching Actions
        case CalibrixActionTypes.START_MATCHING_REQUEST:
            return {
                ...state,
                isMatching: true,
                error: null,
            };
        
        case CalibrixActionTypes.START_MATCHING_SUCCESS:
            return {
                ...state,
                isMatching: true,
                error: null,
            };
        
        case CalibrixActionTypes.START_MATCHING_FAILED:
            return {
                ...state,
                isMatching: false,
                error: action.payload.error.message,
            };
        
        case CalibrixActionTypes.STOP_MATCHING:
            return {
                ...state,
                isMatching: false,
            };
        
        case CalibrixActionTypes.MATCHING_COMPLETE:
            return {
                ...state,
                matchingResults: [...state.matchingResults, ...action.payload.results],
                isMatching: false,
                error: null,
            };
        
        case CalibrixActionTypes.UPDATE_MATCHING_PARAMS:
            return {
                ...state,
                matchingParams: action.payload.params,
            };
        
        // Detection Review Actions
        case CalibrixActionTypes.VERIFY_OBJECT:
            return {
                ...state,
                matchingResults: state.matchingResults.map(result => ({
                    ...result,
                    detectedObjects: result.detectedObjects.map(obj =>
                        obj.id === action.payload.objectId
                            ? { ...obj, verified: action.payload.verified, rejected: false }
                            : obj
                    ),
                })),
            };
        
        case CalibrixActionTypes.REJECT_OBJECT:
            return {
                ...state,
                matchingResults: state.matchingResults.map(result => ({
                    ...result,
                    detectedObjects: result.detectedObjects.map(obj =>
                        obj.id === action.payload.objectId
                            ? { ...obj, rejected: action.payload.rejected, verified: false }
                            : obj
                    ),
                })),
            };
        
        case CalibrixActionTypes.ADD_OBJECT_NOTE:
            return {
                ...state,
                matchingResults: state.matchingResults.map(result => ({
                    ...result,
                    detectedObjects: result.detectedObjects.map(obj =>
                        obj.id === action.payload.objectId
                            ? { ...obj, notes: action.payload.note }
                            : obj
                    ),
                })),
            };
        
        case CalibrixActionTypes.SELECT_OBJECTS:
            return {
                ...state,
                selectedObjects: action.payload.objectIds,
            };
        
        case CalibrixActionTypes.UPDATE_DETECTION_FILTERS:
            return {
                ...state,
                detectionFilters: action.payload.filters,
            };
        
        // Export Actions
        case CalibrixActionTypes.EXPORT_GROUND_TRUTH_REQUEST:
            return {
                ...state,
                isExporting: true,
                error: null,
            };
        
        case CalibrixActionTypes.EXPORT_GROUND_TRUTH_SUCCESS:
            return {
                ...state,
                isExporting: false,
                error: null,
            };
        
        case CalibrixActionTypes.EXPORT_GROUND_TRUTH_FAILED:
            return {
                ...state,
                isExporting: false,
                error: action.payload.error.message,
            };
        
        // Error Handling
        case CalibrixActionTypes.SET_CALIBRIX_ERROR:
            return {
                ...state,
                error: action.payload.error.message,
            };
        
        case CalibrixActionTypes.CLEAR_CALIBRIX_ERROR:
            return {
                ...state,
                error: null,
            };
        
        // Reset State
        case CalibrixActionTypes.RESET_CALIBRIX_STATE:
            return defaultState;
        
        default:
            return state;
    }
}