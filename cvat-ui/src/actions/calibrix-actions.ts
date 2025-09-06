// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import { ActionUnion, createAction } from './common';
import {
    ROI,
    MatchingResult,
    MatchingAlgorithmParams,
    GroundTruthData,
    DetectedObject,
    CalibrixError,
    MatchingProgress,
    ExportOptions,
} from '../components/calibrix-dashboard/types';

export enum CalibrixActionTypes {
    // ROI Actions
    CREATE_ROI_REQUEST = 'CREATE_ROI_REQUEST',
    CREATE_ROI_SUCCESS = 'CREATE_ROI_SUCCESS',
    CREATE_ROI_FAILED = 'CREATE_ROI_FAILED',
    
    UPDATE_ROI_REQUEST = 'UPDATE_ROI_REQUEST',
    UPDATE_ROI_SUCCESS = 'UPDATE_ROI_SUCCESS',
    UPDATE_ROI_FAILED = 'UPDATE_ROI_FAILED',
    
    DELETE_ROI_REQUEST = 'DELETE_ROI_REQUEST',
    DELETE_ROI_SUCCESS = 'DELETE_ROI_SUCCESS',
    DELETE_ROI_FAILED = 'DELETE_ROI_FAILED',
    
    LOAD_ROIS_REQUEST = 'LOAD_ROIS_REQUEST',
    LOAD_ROIS_SUCCESS = 'LOAD_ROIS_SUCCESS',
    LOAD_ROIS_FAILED = 'LOAD_ROIS_FAILED',
    
    SELECT_ROI = 'SELECT_ROI',
    
    // Matching Actions
    START_MATCHING_REQUEST = 'START_MATCHING_REQUEST',
    START_MATCHING_SUCCESS = 'START_MATCHING_SUCCESS',
    START_MATCHING_FAILED = 'START_MATCHING_FAILED',
    
    STOP_MATCHING = 'STOP_MATCHING',
    
    UPDATE_MATCHING_PROGRESS = 'UPDATE_MATCHING_PROGRESS',
    
    MATCHING_COMPLETE = 'MATCHING_COMPLETE',
    
    UPDATE_MATCHING_PARAMS = 'UPDATE_MATCHING_PARAMS',
    
    // Detection Review Actions
    VERIFY_OBJECT = 'VERIFY_OBJECT',
    REJECT_OBJECT = 'REJECT_OBJECT',
    ADD_OBJECT_NOTE = 'ADD_OBJECT_NOTE',
    SELECT_OBJECTS = 'SELECT_OBJECTS',
    UPDATE_DETECTION_FILTERS = 'UPDATE_DETECTION_FILTERS',
    
    // Export Actions
    EXPORT_GROUND_TRUTH_REQUEST = 'EXPORT_GROUND_TRUTH_REQUEST',
    EXPORT_GROUND_TRUTH_SUCCESS = 'EXPORT_GROUND_TRUTH_SUCCESS',
    EXPORT_GROUND_TRUTH_FAILED = 'EXPORT_GROUND_TRUTH_FAILED',
    
    // Error Handling
    SET_CALIBRIX_ERROR = 'SET_CALIBRIX_ERROR',
    CLEAR_CALIBRIX_ERROR = 'CLEAR_CALIBRIX_ERROR',
    
    // Reset State
    RESET_CALIBRIX_STATE = 'RESET_CALIBRIX_STATE',
}

// ROI Action Creators
export const calibrixActions = {
    // ROI Actions
    createROIRequest: (roi: Omit<ROI, 'id' | 'created' | 'updated'>, taskId: number) => (
        createAction(CalibrixActionTypes.CREATE_ROI_REQUEST, { roi, taskId })
    ),
    createROISuccess: (roi: ROI) => (
        createAction(CalibrixActionTypes.CREATE_ROI_SUCCESS, { roi })
    ),
    createROIFailed: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.CREATE_ROI_FAILED, { error })
    ),
    
    updateROIRequest: (roi: ROI, taskId: number) => (
        createAction(CalibrixActionTypes.UPDATE_ROI_REQUEST, { roi, taskId })
    ),
    updateROISuccess: (roi: ROI) => (
        createAction(CalibrixActionTypes.UPDATE_ROI_SUCCESS, { roi })
    ),
    updateROIFailed: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.UPDATE_ROI_FAILED, { error })
    ),
    
    deleteROIRequest: (roiId: string, taskId: number) => (
        createAction(CalibrixActionTypes.DELETE_ROI_REQUEST, { roiId, taskId })
    ),
    deleteROISuccess: (roiId: string) => (
        createAction(CalibrixActionTypes.DELETE_ROI_SUCCESS, { roiId })
    ),
    deleteROIFailed: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.DELETE_ROI_FAILED, { error })
    ),
    
    loadROIsRequest: (taskId: number) => (
        createAction(CalibrixActionTypes.LOAD_ROIS_REQUEST, { taskId })
    ),
    loadROIsSuccess: (rois: ROI[]) => (
        createAction(CalibrixActionTypes.LOAD_ROIS_SUCCESS, { rois })
    ),
    loadROIsFailed: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.LOAD_ROIS_FAILED, { error })
    ),
    
    selectROI: (roiId: string | null) => (
        createAction(CalibrixActionTypes.SELECT_ROI, { roiId })
    ),
    
    // Matching Actions
    startMatchingRequest: (roiId: string, params: MatchingAlgorithmParams, taskId: number) => (
        createAction(CalibrixActionTypes.START_MATCHING_REQUEST, { roiId, params, taskId })
    ),
    startMatchingSuccess: () => (
        createAction(CalibrixActionTypes.START_MATCHING_SUCCESS, {})
    ),
    startMatchingFailed: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.START_MATCHING_FAILED, { error })
    ),
    
    stopMatching: () => (
        createAction(CalibrixActionTypes.STOP_MATCHING, {})
    ),
    
    updateMatchingProgress: (progress: MatchingProgress) => (
        createAction(CalibrixActionTypes.UPDATE_MATCHING_PROGRESS, { progress })
    ),
    
    matchingComplete: (results: MatchingResult[]) => (
        createAction(CalibrixActionTypes.MATCHING_COMPLETE, { results })
    ),
    
    updateMatchingParams: (params: MatchingAlgorithmParams) => (
        createAction(CalibrixActionTypes.UPDATE_MATCHING_PARAMS, { params })
    ),
    
    // Detection Review Actions
    verifyObject: (objectId: string, verified: boolean) => (
        createAction(CalibrixActionTypes.VERIFY_OBJECT, { objectId, verified })
    ),
    
    rejectObject: (objectId: string, rejected: boolean) => (
        createAction(CalibrixActionTypes.REJECT_OBJECT, { objectId, rejected })
    ),
    
    addObjectNote: (objectId: string, note: string) => (
        createAction(CalibrixActionTypes.ADD_OBJECT_NOTE, { objectId, note })
    ),
    
    selectObjects: (objectIds: string[]) => (
        createAction(CalibrixActionTypes.SELECT_OBJECTS, { objectIds })
    ),
    
    updateDetectionFilters: (filters: any) => (
        createAction(CalibrixActionTypes.UPDATE_DETECTION_FILTERS, { filters })
    ),
    
    // Export Actions
    exportGroundTruthRequest: (
        roiIds: string[], 
        format: GroundTruthData['exportFormat'], 
        options: ExportOptions,
        taskId: number
    ) => (
        createAction(CalibrixActionTypes.EXPORT_GROUND_TRUTH_REQUEST, { roiIds, format, options, taskId })
    ),
    exportGroundTruthSuccess: (data: GroundTruthData) => (
        createAction(CalibrixActionTypes.EXPORT_GROUND_TRUTH_SUCCESS, { data })
    ),
    exportGroundTruthFailed: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.EXPORT_GROUND_TRUTH_FAILED, { error })
    ),
    
    // Error Handling
    setCalibrixError: (error: CalibrixError) => (
        createAction(CalibrixActionTypes.SET_CALIBRIX_ERROR, { error })
    ),
    
    clearCalibrixError: () => (
        createAction(CalibrixActionTypes.CLEAR_CALIBRIX_ERROR, {})
    ),
    
    // Reset State
    resetCalibrixState: () => (
        createAction(CalibrixActionTypes.RESET_CALIBRIX_STATE, {})
    ),
};

export type CalibrixActions = ActionUnion<typeof calibrixActions>;