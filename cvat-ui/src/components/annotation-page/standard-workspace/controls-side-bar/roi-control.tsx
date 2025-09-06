// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useCallback, useEffect, useState } from 'react';
import { Row, Col, Divider, Button, Select, Switch, Tooltip, Upload, Modal, Card, Tag, Slider, InputNumber } from 'antd';
import {
    PlayCircleOutlined,
    EditOutlined,
    EyeOutlined,
    DeleteOutlined,
    UploadOutlined,
    DownloadOutlined,
    SettingOutlined,
    PlusOutlined,
    MinusOutlined,
    AimOutlined,
} from '@ant-design/icons';

import { CVATTooltip } from 'components/common/cvat-tooltip';
import { ROIDrawingMode, ROIVisualizationMode } from 'cvat-canvas/src/typescript/canvasModel';

const { Option } = Select;

interface ROITemplate {
    id: string;
    name: string;
    type: ROIDrawingMode;
    points: number[];
    featurePoints?: number[];
    confidence?: number;
    color?: string;
    metadata?: Record<string, any>;
}

interface ROIMatchingResult {
    templateId: string;
    matchPoints: number[];
    confidence: number;
    boundingBox: number[];
    featureMatches?: Array<{
        templatePoint: number[];
        imagePoint: number[];
        confidence: number;
    }>;
}

export interface Props {
    canvasInstance: any;
    jobInstance?: any;
    disabled?: boolean;
    roiTemplates: ROITemplate[];
    matchingResults: ROIMatchingResult[];
    onROICreated: (roi: ROITemplate) => void;
    onROIUpdated: (roi: ROITemplate) => void;
    onROIDeleted: (roiId: string) => void;
    onROIMatching: (templateId: string) => void;
    onImportTemplates: (files: File[]) => void;
    onExportTemplates: (templateIds: string[]) => void;
}

interface ROIControlState {
    isDrawing: boolean;
    isEditing: boolean;
    isVisualizationEnabled: boolean;
    currentDrawingMode: ROIDrawingMode;
    currentVisualizationMode: ROIVisualizationMode;
    selectedTemplate: string | null;
    showFeaturePoints: boolean;
    showMatchingResults: boolean;
    confidenceThreshold: number;
    templatesVisible: boolean;
    matchingInProgress: boolean;
}

function ROIControl(props: Props): JSX.Element {
    const {
        canvasInstance,
        jobInstance,
        disabled = false,
        roiTemplates = [],
        matchingResults = [],
        onROICreated,
        onROIUpdated,
        onROIDeleted,
        onROIMatching,
        onImportTemplates,
        onExportTemplates,
    } = props;

    const [state, setState] = useState<ROIControlState>({
        isDrawing: false,
        isEditing: false,
        isVisualizationEnabled: false,
        currentDrawingMode: ROIDrawingMode.RECTANGLE,
        currentVisualizationMode: ROIVisualizationMode.TEMPLATE_PREVIEW,
        selectedTemplate: null,
        showFeaturePoints: true,
        showMatchingResults: true,
        confidenceThreshold: 0.7,
        templatesVisible: true,
        matchingInProgress: false,
    });

    const {
        isDrawing,
        isEditing,
        isVisualizationEnabled,
        currentDrawingMode,
        currentVisualizationMode,
        selectedTemplate,
        showFeaturePoints,
        showMatchingResults,
        confidenceThreshold,
        templatesVisible,
        matchingInProgress,
    } = state;

    // Handle canvas ROI events
    useEffect(() => {
        if (!canvasInstance) return;

        const handleROICreated = (event: CustomEvent) => {
            const { roi } = event.detail;
            onROICreated(roi);
            setState(prevState => ({ ...prevState, isDrawing: false }));
        };

        const handleROIUpdated = (event: CustomEvent) => {
            const { roi } = event.detail;
            onROIUpdated(roi);
        };

        const handleROIDeleted = (event: CustomEvent) => {
            const { roiId } = event.detail;
            onROIDeleted(roiId);
        };

        const canvas = canvasInstance.html();
        canvas.addEventListener('canvas.roi.created', handleROICreated);
        canvas.addEventListener('canvas.roi.updated', handleROIUpdated);
        canvas.addEventListener('canvas.roi.deleted', handleROIDeleted);

        return () => {
            canvas.removeEventListener('canvas.roi.created', handleROICreated);
            canvas.removeEventListener('canvas.roi.updated', handleROIUpdated);
            canvas.removeEventListener('canvas.roi.deleted', handleROIDeleted);
        };
    }, [canvasInstance, onROICreated, onROIUpdated, onROIDeleted]);

    const enableROIDrawing = useCallback(() => {
        if (!canvasInstance) return;

        canvasInstance.drawROI({
            enabled: true,
            mode: currentDrawingMode,
            showFeaturePoints,
            onROICreated: (roi: ROITemplate) => {
                onROICreated(roi);
                setState(prevState => ({ ...prevState, isDrawing: false }));
            },
        });

        setState(prevState => ({ ...prevState, isDrawing: true }));
    }, [canvasInstance, currentDrawingMode, showFeaturePoints, onROICreated]);

    const disableROIDrawing = useCallback(() => {
        if (!canvasInstance) return;

        canvasInstance.drawROI({ enabled: false });
        setState(prevState => ({ ...prevState, isDrawing: false }));
    }, [canvasInstance]);

    const enableROIEditing = useCallback((templateId: string) => {
        if (!canvasInstance) return;

        canvasInstance.editROI({
            enabled: true,
            roiId: templateId,
            allowResize: true,
            allowMove: true,
            allowDelete: true,
        });

        setState(prevState => ({ 
            ...prevState, 
            isEditing: true, 
            selectedTemplate: templateId 
        }));
    }, [canvasInstance]);

    const disableROIEditing = useCallback(() => {
        if (!canvasInstance) return;

        canvasInstance.editROI({ enabled: false });
        setState(prevState => ({ 
            ...prevState, 
            isEditing: false, 
            selectedTemplate: null 
        }));
    }, [canvasInstance]);

    const enableVisualization = useCallback(() => {
        if (!canvasInstance) return;

        const filteredResults = showMatchingResults 
            ? matchingResults.filter(result => result.confidence >= confidenceThreshold)
            : [];

        canvasInstance.visualizeROI({
            enabled: true,
            templates: roiTemplates,
            matchingResults: filteredResults,
            visualizationMode: currentVisualizationMode,
        });

        setState(prevState => ({ ...prevState, isVisualizationEnabled: true }));
    }, [canvasInstance, roiTemplates, matchingResults, currentVisualizationMode, showMatchingResults, confidenceThreshold]);

    const disableVisualization = useCallback(() => {
        if (!canvasInstance) return;

        canvasInstance.visualizeROI({ enabled: false, templates: [] });
        setState(prevState => ({ ...prevState, isVisualizationEnabled: false }));
    }, [canvasInstance]);

    const handleDrawingModeChange = useCallback((mode: ROIDrawingMode) => {
        setState(prevState => ({ ...prevState, currentDrawingMode: mode }));
        
        if (isDrawing && canvasInstance) {
            // Update the current drawing mode
            canvasInstance.drawROI({
                enabled: true,
                mode,
                showFeaturePoints,
            });
        }
    }, [isDrawing, canvasInstance, showFeaturePoints]);

    const handleVisualizationModeChange = useCallback((mode: ROIVisualizationMode) => {
        setState(prevState => ({ ...prevState, currentVisualizationMode: mode }));
        
        if (isVisualizationEnabled) {
            enableVisualization();
        }
    }, [isVisualizationEnabled, enableVisualization]);

    const handleTemplateDelete = useCallback((templateId: string) => {
        Modal.confirm({
            title: 'Delete ROI Template',
            content: 'Are you sure you want to delete this ROI template?',
            onOk: () => {
                onROIDeleted(templateId);
                if (selectedTemplate === templateId) {
                    disableROIEditing();
                }
            },
        });
    }, [onROIDeleted, selectedTemplate, disableROIEditing]);

    const handleTemplateMatching = useCallback((templateId: string) => {
        setState(prevState => ({ ...prevState, matchingInProgress: true }));
        
        onROIMatching(templateId);
        
        // Simulate matching completion (in real implementation, this would be handled by the matching service)
        setTimeout(() => {
            setState(prevState => ({ ...prevState, matchingInProgress: false }));
        }, 3000);
    }, [onROIMatching]);

    const handleImport = useCallback((info: any) => {
        const { fileList } = info;
        const files = fileList.map((file: any) => file.originFileObj).filter(Boolean);
        if (files.length > 0) {
            onImportTemplates(files);
        }
    }, [onImportTemplates]);

    const handleExport = useCallback(() => {
        const selectedIds = roiTemplates.map(template => template.id);
        onExportTemplates(selectedIds);
    }, [roiTemplates, onExportTemplates]);

    const getConfidenceColor = useCallback((confidence: number) => {
        if (confidence >= 0.8) return 'green';
        if (confidence >= 0.6) return 'orange';
        return 'red';
    }, []);

    const drawingModeOptions = [
        { value: ROIDrawingMode.RECTANGLE, label: 'Rectangle', icon: '⬛' },
        { value: ROIDrawingMode.POLYGON, label: 'Polygon', icon: '▰' },
        { value: ROIDrawingMode.CIRCLE, label: 'Circle', icon: '●' },
        { value: ROIDrawingMode.FREEHAND, label: 'Freehand', icon: '✏️' },
    ];

    const visualizationModeOptions = [
        { value: ROIVisualizationMode.TEMPLATE_PREVIEW, label: 'Template Preview' },
        { value: ROIVisualizationMode.FEATURE_POINTS, label: 'Feature Points' },
        { value: ROIVisualizationMode.MATCHING_RESULTS, label: 'Matching Results' },
    ];

    return (
        <div className='cvat-roi-control'>
            <Row justify='start' align='middle'>
                <Col>
                    <CVATTooltip title='Region of Interest (ROI) tools'>
                        <AimOutlined />
                    </CVATTooltip>
                </Col>
            </Row>

            <Divider />

            {/* Drawing Controls */}
            <Row gutter={[8, 8]}>
                <Col span={24}>
                    <Row justify='space-between' align='middle'>
                        <Col>
                            <strong>Drawing Mode</strong>
                        </Col>
                        <Col>
                            <Select
                                value={currentDrawingMode}
                                onChange={handleDrawingModeChange}
                                disabled={disabled || isEditing}
                                size='small'
                                style={{ minWidth: 100 }}
                            >
                                {drawingModeOptions.map(option => (
                                    <Option key={option.value} value={option.value}>
                                        {option.icon} {option.label}
                                    </Option>
                                ))}
                            </Select>
                        </Col>
                    </Row>
                </Col>

                <Col span={24}>
                    <Row gutter={8}>
                        <Col flex='auto'>
                            <Button
                                type={isDrawing ? 'primary' : 'default'}
                                icon={<PlayCircleOutlined />}
                                onClick={isDrawing ? disableROIDrawing : enableROIDrawing}
                                disabled={disabled || isEditing}
                                block
                            >
                                {isDrawing ? 'Stop Drawing' : 'Start Drawing'}
                            </Button>
                        </Col>
                    </Row>
                </Col>
            </Row>

            <Divider />

            {/* Visualization Controls */}
            <Row gutter={[8, 8]}>
                <Col span={24}>
                    <Row justify='space-between' align='middle'>
                        <Col>
                            <strong>Visualization</strong>
                        </Col>
                        <Col>
                            <Switch
                                checked={isVisualizationEnabled}
                                onChange={isVisualizationEnabled ? disableVisualization : enableVisualization}
                                disabled={disabled || isDrawing}
                                size='small'
                            />
                        </Col>
                    </Row>
                </Col>

                <Col span={24}>
                    <Select
                        value={currentVisualizationMode}
                        onChange={handleVisualizationModeChange}
                        disabled={disabled || !isVisualizationEnabled}
                        size='small'
                        style={{ width: '100%' }}
                    >
                        {visualizationModeOptions.map(option => (
                            <Option key={option.value} value={option.value}>
                                {option.label}
                            </Option>
                        ))}
                    </Select>
                </Col>

                <Col span={24}>
                    <Row gutter={8}>
                        <Col span={12}>
                            <CVATTooltip title='Show feature points'>
                                <Switch
                                    checked={showFeaturePoints}
                                    onChange={(checked) => setState(prev => ({ ...prev, showFeaturePoints: checked }))}
                                    disabled={disabled}
                                    size='small'
                                />
                            </CVATTooltip>
                            <span style={{ marginLeft: 8, fontSize: 12 }}>Features</span>
                        </Col>
                        <Col span={12}>
                            <CVATTooltip title='Show matching results'>
                                <Switch
                                    checked={showMatchingResults}
                                    onChange={(checked) => setState(prev => ({ ...prev, showMatchingResults: checked }))}
                                    disabled={disabled}
                                    size='small'
                                />
                            </CVATTooltip>
                            <span style={{ marginLeft: 8, fontSize: 12 }}>Results</span>
                        </Col>
                    </Row>
                </Col>

                <Col span={24}>
                    <Row gutter={8} align='middle'>
                        <Col span={12}>
                            <span style={{ fontSize: 12 }}>Confidence:</span>
                        </Col>
                        <Col span={12}>
                            <InputNumber
                                min={0}
                                max={1}
                                step={0.1}
                                value={confidenceThreshold}
                                onChange={(value) => setState(prev => ({ 
                                    ...prev, 
                                    confidenceThreshold: value || 0.7 
                                }))}
                                disabled={disabled}
                                size='small'
                                style={{ width: '100%' }}
                            />
                        </Col>
                    </Row>
                </Col>
            </Row>

            <Divider />

            {/* Template Management */}
            <Row gutter={[8, 8]}>
                <Col span={24}>
                    <Row justify='space-between' align='middle'>
                        <Col>
                            <strong>Templates ({roiTemplates.length})</strong>
                        </Col>
                        <Col>
                            <Switch
                                checked={templatesVisible}
                                onChange={(checked) => setState(prev => ({ ...prev, templatesVisible: checked }))}
                                size='small'
                            />
                        </Col>
                    </Row>
                </Col>

                <Col span={24}>
                    <Row gutter={8}>
                        <Col span={12}>
                            <Upload
                                accept='.json,.xml,.yaml'
                                multiple
                                showUploadList={false}
                                onChange={handleImport}
                                disabled={disabled}
                            >
                                <Button
                                    icon={<UploadOutlined />}
                                    disabled={disabled}
                                    size='small'
                                    block
                                >
                                    Import
                                </Button>
                            </Upload>
                        </Col>
                        <Col span={12}>
                            <Button
                                icon={<DownloadOutlined />}
                                onClick={handleExport}
                                disabled={disabled || roiTemplates.length === 0}
                                size='small'
                                block
                            >
                                Export
                            </Button>
                        </Col>
                    </Row>
                </Col>
            </Row>

            {templatesVisible && (
                <Row gutter={[8, 8]} style={{ marginTop: 8 }}>
                    <Col span={24}>
                        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
                            {roiTemplates.map((template) => (
                                <Card
                                    key={template.id}
                                    size='small'
                                    style={{ marginBottom: 8 }}
                                    bodyStyle={{ padding: 8 }}
                                >
                                    <Row justify='space-between' align='middle'>
                                        <Col flex='auto'>
                                            <div style={{ fontSize: 12, fontWeight: 'bold' }}>
                                                {template.name}
                                            </div>
                                            <div style={{ fontSize: 10, color: '#666' }}>
                                                {template.type} • {template.points.length} points
                                            </div>
                                            {template.confidence && (
                                                <Tag
                                                    color={getConfidenceColor(template.confidence)}
                                                    size='small'
                                                    style={{ marginTop: 2 }}
                                                >
                                                    {(template.confidence * 100).toFixed(1)}%
                                                </Tag>
                                            )}
                                        </Col>
                                        <Col>
                                            <Row gutter={4}>
                                                <Col>
                                                    <CVATTooltip title='Edit template'>
                                                        <Button
                                                            type='text'
                                                            icon={<EditOutlined />}
                                                            onClick={() => enableROIEditing(template.id)}
                                                            disabled={disabled || isDrawing}
                                                            size='small'
                                                        />
                                                    </CVATTooltip>
                                                </Col>
                                                <Col>
                                                    <CVATTooltip title='Match template'>
                                                        <Button
                                                            type='text'
                                                            icon={<EyeOutlined />}
                                                            onClick={() => handleTemplateMatching(template.id)}
                                                            disabled={disabled || matchingInProgress}
                                                            size='small'
                                                            loading={matchingInProgress}
                                                        />
                                                    </CVATTooltip>
                                                </Col>
                                                <Col>
                                                    <CVATTooltip title='Delete template'>
                                                        <Button
                                                            type='text'
                                                            icon={<DeleteOutlined />}
                                                            onClick={() => handleTemplateDelete(template.id)}
                                                            disabled={disabled}
                                                            size='small'
                                                            danger
                                                        />
                                                    </CVATTooltip>
                                                </Col>
                                            </Row>
                                        </Col>
                                    </Row>
                                </Card>
                            ))}
                            {roiTemplates.length === 0 && (
                                <div style={{ 
                                    textAlign: 'center', 
                                    color: '#999', 
                                    padding: 16,
                                    fontSize: 12
                                }}>
                                    No ROI templates available.<br />
                                    Start drawing to create templates.
                                </div>
                            )}
                        </div>
                    </Col>
                </Row>
            )}

            {/* Matching Results */}
            {matchingResults.length > 0 && (
                <>
                    <Divider />
                    <Row gutter={[8, 8]}>
                        <Col span={24}>
                            <strong>Matching Results ({matchingResults.length})</strong>
                        </Col>
                        <Col span={24}>
                            <div style={{ maxHeight: 150, overflowY: 'auto' }}>
                                {matchingResults.map((result, index) => (
                                    <div key={`${result.templateId}-${index}`} style={{ 
                                        padding: 4, 
                                        border: '1px solid #f0f0f0',
                                        marginBottom: 4,
                                        borderRadius: 4,
                                        fontSize: 11
                                    }}>
                                        <Row justify='space-between' align='middle'>
                                            <Col>
                                                Template: {result.templateId}
                                            </Col>
                                            <Col>
                                                <Tag color={getConfidenceColor(result.confidence)} size='small'>
                                                    {(result.confidence * 100).toFixed(1)}%
                                                </Tag>
                                            </Col>
                                        </Row>
                                    </div>
                                ))}
                            </div>
                        </Col>
                    </Row>
                </>
            )}
        </div>
    );
}

export default React.memo(ROIControl);