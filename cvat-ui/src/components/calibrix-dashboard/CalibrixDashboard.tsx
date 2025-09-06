// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import './styles.scss';
import React, { useEffect, useCallback, useMemo } from 'react';
import { useDispatch, useSelector, shallowEqual } from 'react-redux';
import { Row, Col, Alert, Spin } from 'antd';
import { useParams } from 'react-router';

import { CombinedState } from 'reducers';
import { calibrixActions } from 'actions/calibrix-actions';
import {
    CalibrixDashboardProps,
    ROI,
    MatchingResult,
    GroundTruthData,
    ExportOptions,
    MatchingAlgorithmParams,
} from './types';

import ROICreator from './ROICreator';
import MatchingControls from './MatchingControls';
import DetectionReviewer from './DetectionReviewer';
import GroundTruthExporter from './GroundTruthExporter';

const CalibrixDashboard: React.FC<CalibrixDashboardProps> = ({
    taskId,
    currentFrame,
    onROIChange,
    onMatchingComplete,
    onExportComplete,
}) => {
    const dispatch = useDispatch();
    const urlParams = useParams<{ id: string }>();
    const actualTaskId = taskId || parseInt(urlParams.id, 10);

    const {
        rois,
        matchingResults,
        currentROI,
        matchingParams,
        isMatching,
        isExporting,
        selectedObjects,
        detectionFilters,
        error,
        loading,
    } = useSelector((state: CombinedState) => ({
        rois: state.calibrix.rois,
        matchingResults: state.calibrix.matchingResults,
        currentROI: state.calibrix.currentROI,
        matchingParams: state.calibrix.matchingParams,
        isMatching: state.calibrix.isMatching,
        isExporting: state.calibrix.isExporting,
        selectedObjects: state.calibrix.selectedObjects,
        detectionFilters: state.calibrix.detectionFilters,
        error: state.calibrix.error,
        loading: state.calibrix.loading,
    }), shallowEqual);

    // Load ROIs when component mounts or task changes
    useEffect(() => {
        if (actualTaskId) {
            dispatch(calibrixActions.loadROIsRequest(actualTaskId));
        }
    }, [dispatch, actualTaskId]);

    // Clear error when performing new operations
    useEffect(() => {
        if (error) {
            const timer = setTimeout(() => {
                dispatch(calibrixActions.clearCalibrixError());
            }, 5000);
            return () => clearTimeout(timer);
        }
        return undefined;
    }, [error, dispatch]);

    // Handle ROI operations
    const handleROICreate = useCallback((roi: Omit<ROI, 'id' | 'created' | 'updated'>) => {
        dispatch(calibrixActions.createROIRequest(roi, actualTaskId));
    }, [dispatch, actualTaskId]);

    const handleROIUpdate = useCallback((roi: ROI) => {
        dispatch(calibrixActions.updateROIRequest(roi, actualTaskId));
    }, [dispatch, actualTaskId]);

    const handleROIDelete = useCallback((roiId: string) => {
        dispatch(calibrixActions.deleteROIRequest(roiId, actualTaskId));
    }, [dispatch, actualTaskId]);

    const handleROISelect = useCallback((roiId: string) => {
        dispatch(calibrixActions.selectROI(roiId));
        const selectedROI = rois.find(roi => roi.id === roiId);
        if (selectedROI && onROIChange) {
            onROIChange(selectedROI);
        }
    }, [dispatch, rois, onROIChange]);

    // Handle matching operations
    const handleMatchingParamsChange = useCallback((params: MatchingAlgorithmParams) => {
        dispatch(calibrixActions.updateMatchingParams(params));
    }, [dispatch]);

    const handleStartMatching = useCallback((roiId: string) => {
        dispatch(calibrixActions.startMatchingRequest(roiId, matchingParams, actualTaskId));
    }, [dispatch, matchingParams, actualTaskId]);

    const handleStopMatching = useCallback(() => {
        dispatch(calibrixActions.stopMatching());
    }, [dispatch]);

    // Handle detection review operations
    const handleObjectVerify = useCallback((objectId: string, verified: boolean) => {
        dispatch(calibrixActions.verifyObject(objectId, verified));
    }, [dispatch]);

    const handleObjectReject = useCallback((objectId: string, rejected: boolean) => {
        dispatch(calibrixActions.rejectObject(objectId, rejected));
    }, [dispatch]);

    const handleObjectNote = useCallback((objectId: string, note: string) => {
        dispatch(calibrixActions.addObjectNote(objectId, note));
    }, [dispatch]);

    const handleObjectSelect = useCallback((objectIds: string[]) => {
        dispatch(calibrixActions.selectObjects(objectIds));
    }, [dispatch]);

    const handleDetectionFiltersChange = useCallback((filters: typeof detectionFilters) => {
        dispatch(calibrixActions.updateDetectionFilters(filters));
    }, [dispatch]);

    // Handle export operations
    const handleExport = useCallback((
        format: GroundTruthData['exportFormat'], 
        options: ExportOptions
    ) => {
        const roiIds = currentROI ? [currentROI.id] : rois.map(roi => roi.id);
        dispatch(calibrixActions.exportGroundTruthRequest(roiIds, format, options, actualTaskId));
    }, [dispatch, currentROI, rois, actualTaskId]);

    // Get detected objects for current ROI or all ROIs
    const detectedObjects = useMemo(() => {
        const results = currentROI 
            ? matchingResults.filter(result => result.roiId === currentROI.id)
            : matchingResults;
        
        return results.reduce((objects, result) => {
            return objects.concat(result.detectedObjects);
        }, [] as typeof matchingResults[0]['detectedObjects']);
    }, [matchingResults, currentROI]);

    // Prepare ground truth data for export
    const groundTruthData = useMemo(() => {
        return rois.map(roi => {
            const roiResults = matchingResults.filter(result => result.roiId === roi.id);
            const roiObjects = roiResults.reduce((objects, result) => {
                return objects.concat(result.detectedObjects);
            }, [] as typeof matchingResults[0]['detectedObjects']);

            return {
                roiId: roi.id,
                objects: roiObjects.map(obj => ({
                    id: obj.id,
                    label: obj.label,
                    boundingBox: obj.boundingBox,
                    verified: obj.verified,
                    attributes: {},
                })),
                exportFormat: 'coco' as const,
                metadata: {
                    taskId: actualTaskId,
                    frameCount: 1,
                    created: new Date().toISOString(),
                    creator: 'calibrix-dashboard',
                },
            };
        });
    }, [rois, matchingResults, actualTaskId]);

    // Trigger callbacks when operations complete
    useEffect(() => {
        if (matchingResults.length > 0 && onMatchingComplete) {
            onMatchingComplete(matchingResults);
        }
    }, [matchingResults, onMatchingComplete]);

    useEffect(() => {
        if (groundTruthData.length > 0 && onExportComplete && !isExporting) {
            // This would be triggered after successful export
            onExportComplete(groundTruthData[0]);
        }
    }, [groundTruthData, onExportComplete, isExporting]);

    if (loading) {
        return (
            <div className="calibrix-dashboard" data-testid="calibrix-loading">
                <Spin size="large" className="calibrix-spinner" />
            </div>
        );
    }

    return (
        <div 
            className="calibrix-dashboard" 
            data-testid="calibrix-dashboard"
            role="main"
            aria-label="Calibrix Matching Dashboard"
        >
            {error && (
                <Alert
                    message="Error"
                    description={error}
                    type="error"
                    showIcon
                    closable
                    onClose={() => dispatch(calibrixActions.clearCalibrixError())}
                    className="calibrix-error-alert"
                />
            )}

            <Row gutter={[16, 16]} className="calibrix-dashboard-content">
                <Col span={24} lg={12} className="calibrix-left-panel">
                    <div className="calibrix-section">
                        <h2 className="calibrix-section-title">ROI Management</h2>
                        <ROICreator
                            rois={rois}
                            currentFrame={currentFrame}
                            onROICreate={handleROICreate}
                            onROIUpdate={handleROIUpdate}
                            onROIDelete={handleROIDelete}
                            onROISelect={handleROISelect}
                            selectedROI={currentROI}
                            loading={loading}
                        />
                    </div>

                    <div className="calibrix-section">
                        <h2 className="calibrix-section-title">Matching Controls</h2>
                        <MatchingControls
                            params={matchingParams}
                            isMatching={isMatching}
                            onParamsChange={handleMatchingParamsChange}
                            onStartMatching={handleStartMatching}
                            onStopMatching={handleStopMatching}
                            selectedROI={currentROI}
                            disabled={!currentROI}
                        />
                    </div>
                </Col>

                <Col span={24} lg={12} className="calibrix-right-panel">
                    <div className="calibrix-section">
                        <h2 className="calibrix-section-title">Detection Review</h2>
                        <DetectionReviewer
                            detectedObjects={detectedObjects}
                            selectedObjects={selectedObjects}
                            onObjectSelect={handleObjectSelect}
                            onObjectVerify={handleObjectVerify}
                            onObjectReject={handleObjectReject}
                            onObjectNote={handleObjectNote}
                            filters={detectionFilters}
                            onFiltersChange={handleDetectionFiltersChange}
                            loading={loading}
                        />
                    </div>

                    <div className="calibrix-section">
                        <h2 className="calibrix-section-title">Ground Truth Export</h2>
                        <GroundTruthExporter
                            groundTruthData={groundTruthData}
                            selectedObjects={selectedObjects}
                            isExporting={isExporting}
                            onExport={handleExport}
                            taskId={actualTaskId}
                        />
                    </div>
                </Col>
            </Row>
        </div>
    );
};

export default React.memo(CalibrixDashboard);