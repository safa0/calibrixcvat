// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { 
    Button, 
    Form, 
    Input, 
    InputNumber, 
    List, 
    Modal, 
    Space, 
    Tooltip,
    Spin,
    Typography
} from 'antd';
import { 
    PlusOutlined, 
    EditOutlined, 
    DeleteOutlined, 
    SaveOutlined, 
    CloseOutlined 
} from '@ant-design/icons';

import { ROICreatorProps, ROI } from './types';

const { Title, Text } = Typography;

interface ROIFormData {
    name: string;
    coordinates: {
        x: number;
        y: number;
        width: number;
        height: number;
    };
}

interface DrawingState {
    isDrawing: boolean;
    startX: number;
    startY: number;
    currentX: number;
    currentY: number;
}

const ROICreator: React.FC<ROICreatorProps> = ({
    rois,
    currentFrame,
    onROICreate,
    onROIUpdate,
    onROIDelete,
    onROISelect,
    selectedROI,
    loading,
    canvasRef,
}) => {
    const [form] = Form.useForm<ROIFormData>();
    const [editingROI, setEditingROI] = useState<ROI | null>(null);
    const [deleteModalVisible, setDeleteModalVisible] = useState(false);
    const [roiToDelete, setROIToDelete] = useState<string | null>(null);
    const [drawingState, setDrawingState] = useState<DrawingState>({
        isDrawing: false,
        startX: 0,
        startY: 0,
        currentX: 0,
        currentY: 0,
    });
    
    const canvasContainerRef = useRef<HTMLDivElement>(null);
    const overlayRef = useRef<HTMLDivElement>(null);

    // Form validation rules
    const validationRules = {
        name: [
            { required: true, message: 'Name is required' },
            { min: 1, max: 50, message: 'Name must be between 1 and 50 characters' },
        ],
        x: [
            { required: true, message: 'X coordinate is required' },
            { type: 'number', min: 0, message: 'X coordinate must be positive' },
        ],
        y: [
            { required: true, message: 'Y coordinate is required' },
            { type: 'number', min: 0, message: 'Y coordinate must be positive' },
        ],
        width: [
            { required: true, message: 'Width is required' },
            { type: 'number', min: 1, message: 'Width must be positive' },
        ],
        height: [
            { required: true, message: 'Height is required' },
            { type: 'number', min: 1, message: 'Height must be positive' },
        ],
    };

    // Handle ROI creation
    const handleCreateROI = useCallback(async () => {
        try {
            const values = await form.validateFields();
            
            // Validate ROI bounds and overlaps
            const newROI: Omit<ROI, 'id' | 'created' | 'updated'> = {
                name: values.name,
                coordinates: values.coordinates,
                frame: currentFrame,
                active: true,
            };

            // Check for overlaps
            const hasOverlap = rois.some(roi => {
                return isOverlapping(newROI.coordinates, roi.coordinates);
            });

            if (hasOverlap) {
                form.setFields([{
                    name: 'name',
                    errors: ['ROI overlaps with existing ROI'],
                }]);
                return;
            }

            // Check canvas bounds
            if (canvasRef?.current) {
                const canvas = canvasRef.current;
                const { x, y, width, height } = newROI.coordinates;
                
                if (x + width > canvas.width || y + height > canvas.height) {
                    form.setFields([{
                        name: ['coordinates', 'x'],
                        errors: ['ROI extends beyond canvas bounds'],
                    }]);
                    return;
                }
            }

            onROICreate(newROI);
            form.resetFields();
        } catch (error) {
            // Validation failed
            console.error('ROI creation validation failed:', error);
        }
    }, [form, currentFrame, rois, onROICreate, canvasRef]);

    // Handle ROI editing
    const handleEditROI = useCallback((roi: ROI) => {
        setEditingROI(roi);
        form.setFieldsValue({
            name: roi.name,
            coordinates: roi.coordinates,
        });
    }, [form]);

    const handleSaveEdit = useCallback(async () => {
        if (!editingROI) return;

        try {
            const values = await form.validateFields();
            const updatedROI: ROI = {
                ...editingROI,
                name: values.name,
                coordinates: values.coordinates,
                updated: new Date().toISOString(),
            };

            onROIUpdate(updatedROI);
            setEditingROI(null);
            form.resetFields();
        } catch (error) {
            console.error('ROI edit validation failed:', error);
        }
    }, [editingROI, form, onROIUpdate]);

    const handleCancelEdit = useCallback(() => {
        setEditingROI(null);
        form.resetFields();
    }, [form]);

    // Handle ROI deletion
    const handleDeleteROI = useCallback((roiId: string) => {
        setROIToDelete(roiId);
        setDeleteModalVisible(true);
    }, []);

    const confirmDelete = useCallback(() => {
        if (roiToDelete) {
            onROIDelete(roiToDelete);
        }
        setDeleteModalVisible(false);
        setROIToDelete(null);
    }, [roiToDelete, onROIDelete]);

    // Handle ROI selection
    const handleSelectROI = useCallback((roiId: string) => {
        onROISelect(roiId);
    }, [onROISelect]);

    // Canvas drawing handlers
    const handleMouseDown = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
        if (!canvasContainerRef.current || editingROI) return;

        const rect = canvasContainerRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        setDrawingState({
            isDrawing: true,
            startX: x,
            startY: y,
            currentX: x,
            currentY: y,
        });
    }, [editingROI]);

    const handleMouseMove = useCallback((event: React.MouseEvent<HTMLDivElement>) => {
        if (!drawingState.isDrawing || !canvasContainerRef.current) return;

        const rect = canvasContainerRef.current.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;

        setDrawingState(prev => ({
            ...prev,
            currentX: x,
            currentY: y,
        }));
    }, [drawingState.isDrawing]);

    const handleMouseUp = useCallback(async () => {
        if (!drawingState.isDrawing) return;

        const { startX, startY, currentX, currentY } = drawingState;
        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);

        setDrawingState({
            isDrawing: false,
            startX: 0,
            startY: 0,
            currentX: 0,
            currentY: 0,
        });

        // Only create ROI if it has meaningful size
        if (width > 5 && height > 5) {
            const roiName = `ROI ${rois.length + 1}`;
            const newROI: Omit<ROI, 'id' | 'created' | 'updated'> = {
                name: roiName,
                coordinates: { x, y, width, height },
                frame: currentFrame,
                active: true,
            };

            onROICreate(newROI);
        }
    }, [drawingState, rois.length, currentFrame, onROICreate]);

    // Keyboard event handlers
    useEffect(() => {
        const handleKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') {
                if (drawingState.isDrawing) {
                    setDrawingState({
                        isDrawing: false,
                        startX: 0,
                        startY: 0,
                        currentX: 0,
                        currentY: 0,
                    });
                }
                if (editingROI) {
                    handleCancelEdit();
                }
            } else if (event.key === 'Delete' && selectedROI) {
                handleDeleteROI(selectedROI.id);
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [drawingState.isDrawing, editingROI, selectedROI, handleCancelEdit, handleDeleteROI]);

    // Utility function to check ROI overlap
    const isOverlapping = (rect1: ROI['coordinates'], rect2: ROI['coordinates']): boolean => {
        return !(
            rect1.x + rect1.width <= rect2.x ||
            rect2.x + rect2.width <= rect1.x ||
            rect1.y + rect1.height <= rect2.y ||
            rect2.y + rect2.height <= rect1.y
        );
    };

    // Render drawing rectangle
    const renderDrawingRectangle = () => {
        if (!drawingState.isDrawing) return null;

        const { startX, startY, currentX, currentY } = drawingState;
        const x = Math.min(startX, currentX);
        const y = Math.min(startY, currentY);
        const width = Math.abs(currentX - startX);
        const height = Math.abs(currentY - startY);

        return (
            <div
                className="roi-rectangle drawing"
                style={{
                    left: x,
                    top: y,
                    width,
                    height,
                }}
            />
        );
    };

    if (loading) {
        return (
            <div className="roi-creator" data-testid="roi-creator-loading">
                <Spin size="large" />
            </div>
        );
    }

    return (
        <div 
            className="roi-creator" 
            data-testid="roi-creator"
            data-drawing={drawingState.isDrawing}
            role="region"
            aria-label="ROI Creator"
        >
            {/* Canvas Container */}
            <div 
                ref={canvasContainerRef}
                className="roi-canvas-container"
                data-testid="roi-canvas-container"
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
            >
                <canvas 
                    ref={canvasRef}
                    data-testid="roi-canvas"
                    tabIndex={0}
                    role="img"
                    aria-label="Canvas for ROI creation"
                />
                
                {/* ROI Overlay */}
                <div 
                    ref={overlayRef}
                    className="roi-overlay"
                    data-testid="roi-overlay"
                >
                    {rois.map(roi => (
                        <div
                            key={roi.id}
                            data-testid={`roi-rect-${roi.id}`}
                            className={`roi-rectangle ${roi.active ? 'active' : ''} ${
                                selectedROI?.id === roi.id ? 'selected' : ''
                            }`}
                            style={{
                                left: roi.coordinates.x,
                                top: roi.coordinates.y,
                                width: roi.coordinates.width,
                                height: roi.coordinates.height,
                            }}
                            onClick={() => handleSelectROI(roi.id)}
                        >
                            {selectedROI?.id === roi.id && (
                                <div 
                                    data-testid={`resize-handle-${roi.id}`}
                                    className="resize-handle"
                                />
                            )}
                        </div>
                    ))}
                    {renderDrawingRectangle()}
                </div>
            </div>

            {/* ROI Creation/Edit Form */}
            <div className="roi-form">
                <Title level={4}>
                    {editingROI ? 'Edit ROI' : 'Create New ROI'}
                </Title>
                
                <Form
                    form={form}
                    layout="vertical"
                    initialValues={{
                        coordinates: { x: 0, y: 0, width: 100, height: 100 }
                    }}
                >
                    <Form.Item
                        name="name"
                        label="ROI Name"
                        rules={validationRules.name}
                    >
                        <Input placeholder="Enter ROI name" />
                    </Form.Item>
                    
                    <div className="coordinates-row">
                        <Form.Item
                            name={['coordinates', 'x']}
                            label="X Coordinate"
                            rules={validationRules.x}
                        >
                            <InputNumber min={0} />
                        </Form.Item>
                        
                        <Form.Item
                            name={['coordinates', 'y']}
                            label="Y Coordinate"
                            rules={validationRules.y}
                        >
                            <InputNumber min={0} />
                        </Form.Item>
                    </div>
                    
                    <div className="coordinates-row">
                        <Form.Item
                            name={['coordinates', 'width']}
                            label="Width"
                            rules={validationRules.width}
                        >
                            <InputNumber min={1} />
                        </Form.Item>
                        
                        <Form.Item
                            name={['coordinates', 'height']}
                            label="Height"
                            rules={validationRules.height}
                        >
                            <InputNumber min={1} />
                        </Form.Item>
                    </div>
                </Form>
                
                <div className="roi-controls">
                    {editingROI ? (
                        <Space>
                            <Button 
                                type="primary"
                                icon={<SaveOutlined />}
                                onClick={handleSaveEdit}
                            >
                                Save
                            </Button>
                            <Button 
                                icon={<CloseOutlined />}
                                onClick={handleCancelEdit}
                            >
                                Cancel
                            </Button>
                        </Space>
                    ) : (
                        <Button
                            type="primary"
                            icon={<PlusOutlined />}
                            onClick={handleCreateROI}
                        >
                            Create ROI
                        </Button>
                    )}
                </div>
            </div>

            {/* ROI List */}
            <div className="roi-list-container">
                <Title level={4}>ROI List</Title>
                
                <List
                    className="roi-list"
                    dataSource={rois}
                    locale={{ emptyText: 'No ROIs created yet' }}
                    role="list"
                    aria-label="ROI List"
                    renderItem={(roi) => (
                        <List.Item
                            key={roi.id}
                            data-testid={`roi-item-${roi.id}`}
                            className={`roi-item ${selectedROI?.id === roi.id ? 'selected' : ''}`}
                            onClick={() => handleSelectROI(roi.id)}
                            role="listitem"
                            tabIndex={0}
                            aria-selected={selectedROI?.id === roi.id}
                            aria-label={`${roi.name} ${selectedROI?.id === roi.id ? 'selected' : ''}`}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    handleSelectROI(roi.id);
                                } else if (e.key === 'Delete') {
                                    handleDeleteROI(roi.id);
                                }
                            }}
                        >
                            <div className="roi-info">
                                <div className="roi-name">{roi.name}</div>
                                <div className="roi-coordinates">
                                    {roi.coordinates.x}, {roi.coordinates.y}, {roi.coordinates.width}x{roi.coordinates.height}
                                </div>
                            </div>
                            
                            <div className="roi-actions">
                                <Tooltip title="Edit ROI">
                                    <Button
                                        type="text"
                                        size="small"
                                        icon={<EditOutlined />}
                                        data-testid={`edit-roi-${roi.id}`}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleEditROI(roi);
                                        }}
                                    />
                                </Tooltip>
                                
                                <Tooltip title="Delete ROI">
                                    <Button
                                        type="text"
                                        size="small"
                                        danger
                                        icon={<DeleteOutlined />}
                                        data-testid={`delete-roi-${roi.id}`}
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleDeleteROI(roi.id);
                                        }}
                                    />
                                </Tooltip>
                            </div>
                        </List.Item>
                    )}
                />
            </div>

            {/* Delete Confirmation Modal */}
            <Modal
                title="Confirm Delete"
                open={deleteModalVisible}
                onOk={confirmDelete}
                onCancel={() => setDeleteModalVisible(false)}
                okText="OK"
                cancelText="Cancel"
                role="dialog"
                aria-label="Confirm Delete ROI"
            >
                <Text>Are you sure you want to delete this ROI? This action cannot be undone.</Text>
            </Modal>
        </div>
    );
};

export default React.memo(ROICreator);