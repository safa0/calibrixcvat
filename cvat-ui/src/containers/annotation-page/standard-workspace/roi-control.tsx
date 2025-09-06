// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useEffect, useState, useCallback } from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { message } from 'antd';

import { CombinedState } from 'reducers/interfaces';
import ROIControlComponent from 'components/annotation-page/standard-workspace/controls-side-bar/roi-control';
import { Canvas } from 'cvat-canvas-wrapper';

// ROI types (would normally come from a shared types file)
interface ROITemplate {
    id: string;
    name: string;
    type: string;
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

interface ROIState {
    templates: ROITemplate[];
    matchingResults: ROIMatchingResult[];
    isInitialized: boolean;
}

function ROIControlContainer(): JSX.Element {
    const dispatch = useDispatch();
    
    // Get canvas instance from Redux store
    const canvasInstance = useSelector((state: CombinedState) => state.annotation.canvas.instance);
    const jobInstance = useSelector((state: CombinedState) => state.annotation.job.instance);
    const frameNumber = useSelector((state: CombinedState) => state.annotation.player.frame.number);
    
    // Local ROI state (could be moved to Redux in a full implementation)
    const [roiState, setROIState] = useState<ROIState>({
        templates: [],
        matchingResults: [],
        isInitialized: false,
    });

    // Initialize ROI functionality
    useEffect(() => {
        if (canvasInstance && !roiState.isInitialized) {
            // Initialize with any existing ROI data
            initializeROIData();
            setROIState(prev => ({ ...prev, isInitialized: true }));
        }
    }, [canvasInstance, roiState.isInitialized]);

    // Load ROI data for current frame
    useEffect(() => {
        if (canvasInstance && frameNumber !== undefined) {
            loadROIDataForFrame(frameNumber);
        }
    }, [canvasInstance, frameNumber]);

    const initializeROIData = useCallback(async () => {
        try {
            // In a full implementation, this would load ROI templates from the server
            // For now, we'll use a mock implementation
            const mockTemplates: ROITemplate[] = [
                {
                    id: 'template-1',
                    name: 'Sample Rectangle',
                    type: 'roi_rectangle',
                    points: [100, 100, 200, 200],
                    color: '#ff0000',
                    confidence: 0.9,
                },
                {
                    id: 'template-2', 
                    name: 'Sample Circle',
                    type: 'roi_circle',
                    points: [150, 150, 50], // cx, cy, radius
                    color: '#00ff00',
                    confidence: 0.85,
                },
            ];

            setROIState(prev => ({
                ...prev,
                templates: mockTemplates,
                matchingResults: [],
            }));
        } catch (error) {
            console.error('Failed to initialize ROI data:', error);
            message.error('Failed to initialize ROI functionality');
        }
    }, []);

    const loadROIDataForFrame = useCallback(async (frame: number) => {
        try {
            // In a full implementation, this would load frame-specific ROI data
            // For now, we'll simulate loading matching results
            const mockMatchingResults: ROIMatchingResult[] = [
                {
                    templateId: 'template-1',
                    matchPoints: [150, 150, 250, 250],
                    confidence: 0.92,
                    boundingBox: [150, 150, 250, 250],
                    featureMatches: [
                        {
                            templatePoint: [125, 125],
                            imagePoint: [175, 175],
                            confidence: 0.95,
                        },
                    ],
                },
            ];

            setROIState(prev => ({
                ...prev,
                matchingResults: frame % 3 === 0 ? mockMatchingResults : [], // Show results on every 3rd frame
            }));
        } catch (error) {
            console.error('Failed to load ROI data for frame:', error);
        }
    }, []);

    const handleROICreated = useCallback(async (roi: ROITemplate) => {
        try {
            // Generate a unique ID if not provided
            const newROI = {
                ...roi,
                id: roi.id || `roi_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
                name: roi.name || `ROI ${roiState.templates.length + 1}`,
            };

            // In a full implementation, this would save to the server
            setROIState(prev => ({
                ...prev,
                templates: [...prev.templates, newROI],
            }));

            message.success(`ROI template "${newROI.name}" created successfully`);
        } catch (error) {
            console.error('Failed to create ROI:', error);
            message.error('Failed to create ROI template');
        }
    }, [roiState.templates.length]);

    const handleROIUpdated = useCallback(async (roi: ROITemplate) => {
        try {
            setROIState(prev => ({
                ...prev,
                templates: prev.templates.map(template => 
                    template.id === roi.id ? { ...template, ...roi } : template
                ),
            }));

            message.success(`ROI template "${roi.name}" updated successfully`);
        } catch (error) {
            console.error('Failed to update ROI:', error);
            message.error('Failed to update ROI template');
        }
    }, []);

    const handleROIDeleted = useCallback(async (roiId: string) => {
        try {
            const template = roiState.templates.find(t => t.id === roiId);
            
            setROIState(prev => ({
                ...prev,
                templates: prev.templates.filter(template => template.id !== roiId),
                matchingResults: prev.matchingResults.filter(result => result.templateId !== roiId),
            }));

            message.success(`ROI template "${template?.name || roiId}" deleted successfully`);
        } catch (error) {
            console.error('Failed to delete ROI:', error);
            message.error('Failed to delete ROI template');
        }
    }, [roiState.templates]);

    const handleROIMatching = useCallback(async (templateId: string) => {
        try {
            const template = roiState.templates.find(t => t.id === templateId);
            if (!template) {
                throw new Error('Template not found');
            }

            message.info(`Starting template matching for "${template.name}"...`);

            // In a full implementation, this would call the matching service
            // For now, we'll simulate the matching process
            setTimeout(() => {
                const mockResult: ROIMatchingResult = {
                    templateId,
                    matchPoints: [
                        template.points[0] + 50,
                        template.points[1] + 50,
                        template.points[2] + 50,
                        template.points[3] + 50,
                    ],
                    confidence: 0.8 + Math.random() * 0.2,
                    boundingBox: [
                        template.points[0] + 50,
                        template.points[1] + 50,
                        template.points[2] + 50,
                        template.points[3] + 50,
                    ],
                };

                setROIState(prev => ({
                    ...prev,
                    matchingResults: [
                        ...prev.matchingResults.filter(r => r.templateId !== templateId),
                        mockResult,
                    ],
                }));

                message.success(`Template matching completed for "${template.name}"`);
            }, 2000);
        } catch (error) {
            console.error('Failed to perform template matching:', error);
            message.error('Failed to perform template matching');
        }
    }, [roiState.templates]);

    const handleImportTemplates = useCallback(async (files: File[]) => {
        try {
            for (const file of files) {
                const content = await file.text();
                let templates: ROITemplate[];

                if (file.name.endsWith('.json')) {
                    templates = JSON.parse(content);
                } else {
                    // Handle other formats (XML, YAML) in a full implementation
                    throw new Error(`Unsupported file format: ${file.name}`);
                }

                // Validate and import templates
                const validTemplates = templates.filter(template => 
                    template.id && template.name && template.type && template.points
                );

                setROIState(prev => ({
                    ...prev,
                    templates: [
                        ...prev.templates,
                        ...validTemplates.map(template => ({
                            ...template,
                            id: `imported_${template.id}_${Date.now()}`, // Ensure unique IDs
                        }))
                    ],
                }));

                message.success(`Imported ${validTemplates.length} templates from ${file.name}`);
            }
        } catch (error) {
            console.error('Failed to import templates:', error);
            message.error('Failed to import ROI templates');
        }
    }, []);

    const handleExportTemplates = useCallback(async (templateIds: string[]) => {
        try {
            const templatesToExport = roiState.templates.filter(template => 
                templateIds.includes(template.id)
            );

            const exportData = {
                version: '1.0',
                exported_at: new Date().toISOString(),
                templates: templatesToExport,
            };

            const dataStr = JSON.stringify(exportData, null, 2);
            const dataBlob = new Blob([dataStr], { type: 'application/json' });
            
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = `roi_templates_${Date.now()}.json`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            URL.revokeObjectURL(url);

            message.success(`Exported ${templatesToExport.length} ROI templates`);
        } catch (error) {
            console.error('Failed to export templates:', error);
            message.error('Failed to export ROI templates');
        }
    }, [roiState.templates]);

    // Don't render if canvas is not available
    if (!canvasInstance) {
        return <div>Loading ROI controls...</div>;
    }

    return (
        <ROIControlComponent
            canvasInstance={canvasInstance}
            jobInstance={jobInstance}
            disabled={false}
            roiTemplates={roiState.templates}
            matchingResults={roiState.matchingResults}
            onROICreated={handleROICreated}
            onROIUpdated={handleROIUpdated}
            onROIDeleted={handleROIDeleted}
            onROIMatching={handleROIMatching}
            onImportTemplates={handleImportTemplates}
            onExportTemplates={handleExportTemplates}
        />
    );
}

export default React.memo(ROIControlContainer);