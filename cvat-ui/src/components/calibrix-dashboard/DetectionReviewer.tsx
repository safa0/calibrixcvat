// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import React from 'react';
import { List, Button, Checkbox, Input, Space, Typography, Tag } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { DetectionReviewerProps } from './types';

const { Title } = Typography;

const DetectionReviewer: React.FC<DetectionReviewerProps> = ({
    detectedObjects,
    selectedObjects,
    onObjectSelect,
    onObjectVerify,
    onObjectReject,
    onObjectNote,
    filters,
    onFiltersChange,
    loading,
}) => {
    return (
        <div className="detection-reviewer" data-testid="detection-reviewer">
            <div className="detections-list">
                <List
                    dataSource={detectedObjects}
                    locale={{ emptyText: 'No objects detected yet' }}
                    renderItem={(obj) => (
                        <List.Item
                            key={obj.id}
                            className={`detection-item ${obj.verified ? 'verified' : ''} ${obj.rejected ? 'rejected' : ''}`}
                        >
                            <div className="detection-header">
                                <div className="detection-info">
                                    <div className="detection-label">{obj.label}</div>
                                    <div className="detection-confidence">
                                        Confidence: {(obj.confidence * 100).toFixed(1)}%
                                    </div>
                                </div>
                                <div className="detection-actions">
                                    <Space>
                                        <Button
                                            type={obj.verified ? 'primary' : 'default'}
                                            size="small"
                                            icon={<CheckOutlined />}
                                            onClick={() => onObjectVerify(obj.id, !obj.verified)}
                                            data-testid="verify-object-btn"
                                        >
                                            Verify
                                        </Button>
                                        <Button
                                            danger={obj.rejected}
                                            size="small"
                                            icon={<CloseOutlined />}
                                            onClick={() => onObjectReject(obj.id, !obj.rejected)}
                                        >
                                            Reject
                                        </Button>
                                        <Checkbox
                                            checked={selectedObjects.includes(obj.id)}
                                            onChange={(e) => {
                                                const newSelection = e.target.checked
                                                    ? [...selectedObjects, obj.id]
                                                    : selectedObjects.filter(id => id !== obj.id);
                                                onObjectSelect(newSelection);
                                            }}
                                            data-testid="select-object-btn"
                                        />
                                    </Space>
                                </div>
                            </div>
                        </List.Item>
                    )}
                />
            </div>
        </div>
    );
};

export default React.memo(DetectionReviewer);