// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import React from 'react';
import { Button, Select, Checkbox, Space, Typography, Progress } from 'antd';
import { DownloadOutlined } from '@ant-design/icons';
import { GroundTruthExporterProps } from './types';

const { Title } = Typography;
const { Option } = Select;

const GroundTruthExporter: React.FC<GroundTruthExporterProps> = ({
    groundTruthData,
    selectedObjects,
    isExporting,
    onExport,
    taskId,
}) => {
    const [format, setFormat] = React.useState<'coco' | 'yolo' | 'voc' | 'cvat'>('coco');
    const [options, setOptions] = React.useState({
        includeImages: true,
        includeAnnotations: true,
        includeMetadata: true,
        minConfidence: 0.5,
        verifiedOnly: false,
        customAttributes: [],
    });

    const handleExport = () => {
        onExport(format, options);
    };

    const handleOptionChange = (option: string, value: boolean) => {
        setOptions(prev => ({
            ...prev,
            [option]: value,
        }));
    };

    return (
        <div className="ground-truth-exporter" data-testid="ground-truth-exporter">
            <div className="export-format">
                <Title level={5}>Export Format</Title>
                <Select
                    value={format}
                    onChange={setFormat}
                    disabled={isExporting}
                    style={{ width: '100%' }}
                >
                    <Option value="coco">COCO</Option>
                    <Option value="yolo">YOLO</Option>
                    <Option value="voc">Pascal VOC</Option>
                    <Option value="cvat">CVAT</Option>
                </Select>
            </div>

            <div className="export-options">
                <Title level={5}>Export Options</Title>
                <Space direction="vertical">
                    <Checkbox
                        checked={options.includeImages}
                        onChange={(e) => handleOptionChange('includeImages', e.target.checked)}
                        disabled={isExporting}
                    >
                        Include Images
                    </Checkbox>
                    <Checkbox
                        checked={options.includeAnnotations}
                        onChange={(e) => handleOptionChange('includeAnnotations', e.target.checked)}
                        disabled={isExporting}
                    >
                        Include Annotations
                    </Checkbox>
                    <Checkbox
                        checked={options.verifiedOnly}
                        onChange={(e) => handleOptionChange('verifiedOnly', e.target.checked)}
                        disabled={isExporting}
                    >
                        Verified Objects Only
                    </Checkbox>
                </Space>
            </div>

            <div className="export-actions">
                <div className="export-info">
                    {selectedObjects.length} objects selected
                </div>
                <Button
                    type="primary"
                    icon={<DownloadOutlined />}
                    onClick={handleExport}
                    disabled={isExporting || selectedObjects.length === 0}
                    loading={isExporting}
                    data-testid="export-btn"
                    className="export-button"
                >
                    Export Ground Truth
                </Button>
            </div>

            {isExporting && (
                <div className="export-progress">
                    <Progress percent={50} status="active" />
                    <div className="progress-text">Exporting ground truth data...</div>
                </div>
            )}
        </div>
    );
};

export default React.memo(GroundTruthExporter);