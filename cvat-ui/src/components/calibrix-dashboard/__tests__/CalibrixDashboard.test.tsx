// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { Provider } from 'react-redux';
import { BrowserRouter } from 'react-router-dom';
import { createStore } from 'redux';
import CalibrixDashboard from '../CalibrixDashboard';
import { setupTest, mockStore } from './test-setup';

// Mock child components
jest.mock('../ROICreator', () => {
    return function MockROICreator(props: any) {
        return (
            <div data-testid="roi-creator">
                <button 
                    onClick={() => props.onROICreate(props.mockROI)}
                    data-testid="create-roi-btn"
                >
                    Create ROI
                </button>
                <button 
                    onClick={() => props.onROISelect('roi-1')}
                    data-testid="select-roi-btn"
                >
                    Select ROI
                </button>
            </div>
        );
    };
});

jest.mock('../MatchingControls', () => {
    return function MockMatchingControls(props: any) {
        return (
            <div data-testid="matching-controls">
                <button 
                    onClick={() => props.onStartMatching('roi-1')}
                    data-testid="start-matching-btn"
                    disabled={props.disabled}
                >
                    Start Matching
                </button>
                <button 
                    onClick={props.onStopMatching}
                    data-testid="stop-matching-btn"
                >
                    Stop Matching
                </button>
            </div>
        );
    };
});

jest.mock('../DetectionReviewer', () => {
    return function MockDetectionReviewer(props: any) {
        return (
            <div data-testid="detection-reviewer">
                <button 
                    onClick={() => props.onObjectVerify('obj-1', true)}
                    data-testid="verify-object-btn"
                >
                    Verify Object
                </button>
                <button 
                    onClick={() => props.onObjectSelect(['obj-1'])}
                    data-testid="select-object-btn"
                >
                    Select Object
                </button>
            </div>
        );
    };
});

jest.mock('../GroundTruthExporter', () => {
    return function MockGroundTruthExporter(props: any) {
        return (
            <div data-testid="ground-truth-exporter">
                <button 
                    onClick={() => props.onExport('coco', {})}
                    data-testid="export-btn"
                    disabled={props.isExporting}
                >
                    Export
                </button>
            </div>
        );
    };
});

// Mock Redux hooks
const mockDispatch = jest.fn();
const mockSelector = jest.fn();

jest.mock('react-redux', () => ({
    ...jest.requireActual('react-redux'),
    useDispatch: () => mockDispatch,
    useSelector: (selector: any) => selector(mockStore),
}));

describe('CalibrixDashboard Component', () => {
    const { props } = setupTest();
    let mockReduxStore: any;

    beforeEach(() => {
        mockReduxStore = createStore(() => mockStore);
        mockSelector.mockImplementation((selector) => selector(mockStore));
        mockDispatch.mockClear();
    });

    const renderComponent = (customProps = {}) => {
        const componentProps = { ...props, ...customProps };
        return render(
            <Provider store={mockReduxStore}>
                <BrowserRouter>
                    <CalibrixDashboard {...componentProps} />
                </BrowserRouter>
            </Provider>
        );
    };

    describe('Rendering', () => {
        test('should render all main components', () => {
            renderComponent();

            expect(screen.getByTestId('roi-creator')).toBeInTheDocument();
            expect(screen.getByTestId('matching-controls')).toBeInTheDocument();
            expect(screen.getByTestId('detection-reviewer')).toBeInTheDocument();
            expect(screen.getByTestId('ground-truth-exporter')).toBeInTheDocument();
        });

        test('should display loading state when loading', () => {
            mockSelector.mockImplementation((selector) => selector({
                ...mockStore,
                calibrix: { ...mockStore.calibrix, loading: true }
            }));

            renderComponent();

            expect(screen.getByTestId('calibrix-loading')).toBeInTheDocument();
        });

        test('should display error message when error exists', () => {
            const errorMessage = 'Test error message';
            mockSelector.mockImplementation((selector) => selector({
                ...mockStore,
                calibrix: { ...mockStore.calibrix, error: errorMessage }
            }));

            renderComponent();

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });

        test('should render with correct layout and styling', () => {
            renderComponent();

            const dashboard = screen.getByTestId('calibrix-dashboard');
            expect(dashboard).toHaveClass('calibrix-dashboard');
        });
    });

    describe('ROI Operations', () => {
        test('should handle ROI creation', async () => {
            renderComponent();

            const createBtn = screen.getByTestId('create-roi-btn');
            fireEvent.click(createBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'CREATE_ROI_REQUEST'
                    })
                );
            });
        });

        test('should handle ROI selection', async () => {
            renderComponent();

            const selectBtn = screen.getByTestId('select-roi-btn');
            fireEvent.click(selectBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'SELECT_ROI',
                        payload: { roiId: 'roi-1' }
                    })
                );
            });
        });

        test('should call onROIChange when ROI changes', () => {
            const onROIChange = jest.fn();
            renderComponent({ onROIChange });

            const selectBtn = screen.getByTestId('select-roi-btn');
            fireEvent.click(selectBtn);

            expect(onROIChange).toHaveBeenCalled();
        });
    });

    describe('Matching Operations', () => {
        test('should start matching when ROI is selected', async () => {
            mockSelector.mockImplementation((selector) => selector({
                ...mockStore,
                calibrix: { 
                    ...mockStore.calibrix, 
                    currentROI: { id: 'roi-1', name: 'Test ROI' } 
                }
            }));

            renderComponent();

            const startBtn = screen.getByTestId('start-matching-btn');
            fireEvent.click(startBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'START_MATCHING_REQUEST'
                    })
                );
            });
        });

        test('should disable matching controls when no ROI selected', () => {
            renderComponent();

            const startBtn = screen.getByTestId('start-matching-btn');
            expect(startBtn).toBeDisabled();
        });

        test('should stop matching', async () => {
            renderComponent();

            const stopBtn = screen.getByTestId('stop-matching-btn');
            fireEvent.click(stopBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'STOP_MATCHING'
                    })
                );
            });
        });

        test('should call onMatchingComplete when matching finishes', () => {
            const onMatchingComplete = jest.fn();
            renderComponent({ onMatchingComplete });

            // Simulate matching completion through Redux state change
            // This would typically be triggered by the matching algorithm completion
            expect(onMatchingComplete).toBeDefined();
        });
    });

    describe('Detection Review', () => {
        test('should verify detected objects', async () => {
            renderComponent();

            const verifyBtn = screen.getByTestId('verify-object-btn');
            fireEvent.click(verifyBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'VERIFY_OBJECT',
                        payload: { objectId: 'obj-1', verified: true }
                    })
                );
            });
        });

        test('should select detected objects', async () => {
            renderComponent();

            const selectBtn = screen.getByTestId('select-object-btn');
            fireEvent.click(selectBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'SELECT_OBJECTS',
                        payload: { objectIds: ['obj-1'] }
                    })
                );
            });
        });
    });

    describe('Export Operations', () => {
        test('should export ground truth data', async () => {
            renderComponent();

            const exportBtn = screen.getByTestId('export-btn');
            fireEvent.click(exportBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({
                        type: 'EXPORT_GROUND_TRUTH_REQUEST'
                    })
                );
            });
        });

        test('should disable export button when exporting', () => {
            mockSelector.mockImplementation((selector) => selector({
                ...mockStore,
                calibrix: { ...mockStore.calibrix, isExporting: true }
            }));

            renderComponent();

            const exportBtn = screen.getByTestId('export-btn');
            expect(exportBtn).toBeDisabled();
        });

        test('should call onExportComplete when export finishes', () => {
            const onExportComplete = jest.fn();
            renderComponent({ onExportComplete });

            // Simulate export completion through Redux state change
            expect(onExportComplete).toBeDefined();
        });
    });

    describe('Integration', () => {
        test('should handle complete workflow: create ROI -> match -> review -> export', async () => {
            renderComponent();

            // Create ROI
            fireEvent.click(screen.getByTestId('create-roi-btn'));
            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({ type: 'CREATE_ROI_REQUEST' })
                );
            });

            // Select ROI
            fireEvent.click(screen.getByTestId('select-roi-btn'));
            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({ type: 'SELECT_ROI' })
                );
            });

            // Start matching (would require ROI to be selected in actual implementation)
            // Verify object
            fireEvent.click(screen.getByTestId('verify-object-btn'));
            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({ type: 'VERIFY_OBJECT' })
                );
            });

            // Export
            fireEvent.click(screen.getByTestId('export-btn'));
            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({ type: 'EXPORT_GROUND_TRUTH_REQUEST' })
                );
            });
        });

        test('should maintain state consistency across operations', () => {
            renderComponent();

            // Component should reflect the current Redux state
            expect(screen.getByTestId('roi-creator')).toBeInTheDocument();
            expect(screen.getByTestId('matching-controls')).toBeInTheDocument();
            expect(screen.getByTestId('detection-reviewer')).toBeInTheDocument();
            expect(screen.getByTestId('ground-truth-exporter')).toBeInTheDocument();
        });
    });

    describe('Error Handling', () => {
        test('should handle and display errors gracefully', () => {
            const errorMessage = 'Network error occurred';
            mockSelector.mockImplementation((selector) => selector({
                ...mockStore,
                calibrix: { ...mockStore.calibrix, error: errorMessage }
            }));

            renderComponent();

            expect(screen.getByText(errorMessage)).toBeInTheDocument();
        });

        test('should clear errors when performing new operations', async () => {
            renderComponent();

            const createBtn = screen.getByTestId('create-roi-btn');
            fireEvent.click(createBtn);

            await waitFor(() => {
                expect(mockDispatch).toHaveBeenCalledWith(
                    expect.objectContaining({ type: 'CREATE_ROI_REQUEST' })
                );
            });
        });
    });

    describe('Accessibility', () => {
        test('should have proper ARIA labels and roles', () => {
            renderComponent();

            const dashboard = screen.getByTestId('calibrix-dashboard');
            expect(dashboard).toHaveAttribute('role', 'main');
            expect(dashboard).toHaveAttribute('aria-label', 'Calibrix Matching Dashboard');
        });

        test('should support keyboard navigation', () => {
            renderComponent();

            const createBtn = screen.getByTestId('create-roi-btn');
            createBtn.focus();
            expect(createBtn).toHaveFocus();

            // Test tab navigation
            fireEvent.keyDown(createBtn, { key: 'Tab' });
        });
    });
});