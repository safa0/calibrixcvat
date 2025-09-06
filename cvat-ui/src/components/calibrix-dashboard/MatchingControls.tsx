// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import React from 'react';
import { Button, Form, Select, Slider, Space, Typography } from 'antd';
import { PlayCircleOutlined, StopOutlined } from '@ant-design/icons';
import { MatchingControlsProps } from './types';

const { Title } = Typography;
const { Option } = Select;

const MatchingControls: React.FC<MatchingControlsProps> = ({
    params,
    isMatching,
    onParamsChange,
    onStartMatching,
    onStopMatching,
    selectedROI,
    disabled,
}) => {
    const handleParamChange = (field: string, value: any) => {
        onParamsChange({
            ...params,
            [field]: value,
        });
    };

    return (
        <div className="matching-controls" data-testid="matching-controls">
            <Form layout="vertical">
                <Form.Item label="Algorithm">
                    <Select
                        value={params.algorithm}
                        onChange={(value) => handleParamChange('algorithm', value)}
                        disabled={isMatching}
                    >
                        <Option value="sift">SIFT</Option>
                        <Option value="orb">ORB</Option>
                        <Option value="surf">SURF</Option>
                        <Option value="akaze">AKAZE</Option>
                    </Select>
                </Form.Item>

                <Form.Item label="Threshold">
                    <Slider
                        min={0.1}
                        max={1.0}
                        step={0.1}
                        value={params.threshold}
                        onChange={(value) => handleParamChange('threshold', value)}
                        disabled={isMatching}
                    />
                </Form.Item>

                <Form.Item label="Max Features">
                    <Slider
                        min={1000}
                        max={10000}
                        step={500}
                        value={params.maxFeatures}
                        onChange={(value) => handleParamChange('maxFeatures', value)}
                        disabled={isMatching}
                    />
                </Form.Item>
            </Form>

            <div className="matching-actions">
                <Space>
                    <Button
                        type="primary"
                        icon={<PlayCircleOutlined />}
                        onClick={() => selectedROI && onStartMatching(selectedROI.id)}
                        disabled={disabled || isMatching}
                        data-testid="start-matching-btn"
                    >
                        Start Matching
                    </Button>
                    <Button
                        icon={<StopOutlined />}
                        onClick={onStopMatching}
                        disabled={!isMatching}
                        data-testid="stop-matching-btn"
                    >
                        Stop Matching
                    </Button>
                </Space>
            </div>
        </div>
    );
};

export default React.memo(MatchingControls);