// Copyright (C) 2025 Calibrix Corporation
// SPDX-License-Identifier: MIT

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ROICreator from '../ROICreator';
import { setupTest, mockROI, mockCanvasRef } from './test-setup';

describe('ROICreator Component', () => {
    const { props } = setupTest();

    const defaultProps = {
        rois: [mockROI],
        currentFrame: 0,
        onROICreate: jest.fn(),
        onROIUpdate: jest.fn(),
        onROIDelete: jest.fn(),
        onROISelect: jest.fn(),
        selectedROI: null,
        loading: false,
        canvasRef: mockCanvasRef,
    };

    beforeEach(() => {
        jest.clearAllMocks();
    });

    const renderComponent = (customProps = {}) => {
        const componentProps = { ...defaultProps, ...customProps };
        return render(<ROICreator {...componentProps} />);
    };

    describe('Rendering', () => {
        test('should render ROI creator interface', () => {
            renderComponent();

            expect(screen.getByText('Create New ROI')).toBeInTheDocument();
            expect(screen.getByText('ROI List')).toBeInTheDocument();
            expect(screen.getByRole('button', { name: /create roi/i })).toBeInTheDocument();
        });

        test('should render existing ROIs in the list', () => {
            renderComponent();

            expect(screen.getByText(mockROI.name)).toBeInTheDocument();
            expect(screen.getByText(/10, 10, 100x100/)).toBeInTheDocument();
        });

        test('should show loading state when loading', () => {
            renderComponent({ loading: true });

            expect(screen.getByTestId('roi-creator-loading')).toBeInTheDocument();
        });

        test('should highlight selected ROI', () => {
            renderComponent({ selectedROI: mockROI });

            const roiItem = screen.getByTestId('roi-item-roi-1');
            expect(roiItem).toHaveClass('selected');
        });

        test('should render canvas container', () => {
            renderComponent();

            expect(screen.getByTestId('roi-canvas-container')).toBeInTheDocument();
        });
    });

    describe('ROI Creation', () => {
        test('should allow creating new ROI with form inputs', async () => {
            const user = userEvent.setup();
            renderComponent();

            // Fill out ROI creation form
            const nameInput = screen.getByLabelText(/roi name/i);
            await user.type(nameInput, 'Test ROI 2');

            const xInput = screen.getByLabelText(/x coordinate/i);
            await user.clear(xInput);
            await user.type(xInput, '50');

            const yInput = screen.getByLabelText(/y coordinate/i);
            await user.clear(yInput);
            await user.type(yInput, '60');

            const widthInput = screen.getByLabelText(/width/i);
            await user.clear(widthInput);
            await user.type(widthInput, '150');

            const heightInput = screen.getByLabelText(/height/i);
            await user.clear(heightInput);
            await user.type(heightInput, '120');

            // Submit form
            const createBtn = screen.getByRole('button', { name: /create roi/i });
            await user.click(createBtn);

            expect(defaultProps.onROICreate).toHaveBeenCalledWith({
                name: 'Test ROI 2',
                coordinates: { x: 50, y: 60, width: 150, height: 120 },
                frame: 0,
                active: true,
            });
        });

        test('should validate ROI creation form', async () => {
            const user = userEvent.setup();
            renderComponent();

            // Try to create ROI without required fields
            const createBtn = screen.getByRole('button', { name: /create roi/i });
            await user.click(createBtn);

            expect(screen.getByText(/name is required/i)).toBeInTheDocument();
            expect(defaultProps.onROICreate).not.toHaveBeenCalled();
        });

        test('should reset form after successful creation', async () => {
            const user = userEvent.setup();
            renderComponent();

            const nameInput = screen.getByLabelText(/roi name/i);
            await user.type(nameInput, 'Test ROI');

            const createBtn = screen.getByRole('button', { name: /create roi/i });
            await user.click(createBtn);

            // Form should be reset
            expect(nameInput).toHaveValue('');
        });

        test('should create ROI from canvas drawing', async () => {
            renderComponent();

            const canvas = screen.getByTestId('roi-canvas');
            
            // Simulate canvas drawing
            fireEvent.mouseDown(canvas, { clientX: 10, clientY: 10 });
            fireEvent.mouseMove(canvas, { clientX: 110, clientY: 110 });
            fireEvent.mouseUp(canvas, { clientX: 110, clientY: 110 });

            await waitFor(() => {
                expect(defaultProps.onROICreate).toHaveBeenCalledWith(
                    expect.objectContaining({
                        coordinates: expect.objectContaining({
                            x: expect.any(Number),
                            y: expect.any(Number),
                            width: expect.any(Number),
                            height: expect.any(Number),
                        }),
                    })
                );
            });
        });
    });

    describe('ROI Management', () => {
        test('should select ROI when clicked', async () => {
            const user = userEvent.setup();
            renderComponent();

            const roiItem = screen.getByTestId('roi-item-roi-1');
            await user.click(roiItem);

            expect(defaultProps.onROISelect).toHaveBeenCalledWith('roi-1');
        });

        test('should edit ROI when edit button clicked', async () => {
            const user = userEvent.setup();
            renderComponent();

            const editBtn = screen.getByTestId('edit-roi-roi-1');
            await user.click(editBtn);

            expect(screen.getByText('Edit ROI')).toBeInTheDocument();
            expect(screen.getByDisplayValue(mockROI.name)).toBeInTheDocument();
        });

        test('should update ROI with new values', async () => {
            const user = userEvent.setup();
            renderComponent();

            // Start editing
            const editBtn = screen.getByTestId('edit-roi-roi-1');
            await user.click(editBtn);

            // Modify values
            const nameInput = screen.getByDisplayValue(mockROI.name);
            await user.clear(nameInput);
            await user.type(nameInput, 'Updated ROI Name');

            // Save changes
            const saveBtn = screen.getByRole('button', { name: /save/i });
            await user.click(saveBtn);

            expect(defaultProps.onROIUpdate).toHaveBeenCalledWith(
                expect.objectContaining({
                    id: 'roi-1',
                    name: 'Updated ROI Name',
                })
            );
        });

        test('should delete ROI when delete button clicked', async () => {
            const user = userEvent.setup();
            renderComponent();

            const deleteBtn = screen.getByTestId('delete-roi-roi-1');
            await user.click(deleteBtn);

            // Confirm deletion in modal
            const confirmBtn = screen.getByRole('button', { name: /ok/i });
            await user.click(confirmBtn);

            expect(defaultProps.onROIDelete).toHaveBeenCalledWith('roi-1');
        });

        test('should cancel ROI deletion', async () => {
            const user = userEvent.setup();
            renderComponent();

            const deleteBtn = screen.getByTestId('delete-roi-roi-1');
            await user.click(deleteBtn);

            // Cancel deletion in modal
            const cancelBtn = screen.getByRole('button', { name: /cancel/i });
            await user.click(cancelBtn);

            expect(defaultProps.onROIDelete).not.toHaveBeenCalled();
        });
    });

    describe('Canvas Interaction', () => {
        test('should display ROIs on canvas', () => {
            renderComponent();

            const roiOverlay = screen.getByTestId('roi-overlay');
            expect(roiOverlay).toBeInTheDocument();
            
            const roiRect = screen.getByTestId('roi-rect-roi-1');
            expect(roiRect).toBeInTheDocument();
        });

        test('should highlight selected ROI on canvas', () => {
            renderComponent({ selectedROI: mockROI });

            const roiRect = screen.getByTestId('roi-rect-roi-1');
            expect(roiRect).toHaveClass('selected');
        });

        test('should handle canvas mouse events for ROI creation', () => {
            renderComponent();

            const canvas = screen.getByTestId('roi-canvas');
            
            // Start drawing
            fireEvent.mouseDown(canvas, { clientX: 20, clientY: 30 });
            
            // The drawing state should be active
            expect(screen.getByTestId('roi-creator')).toHaveAttribute('data-drawing', 'true');
            
            // Move mouse to create rectangle
            fireEvent.mouseMove(canvas, { clientX: 120, clientY: 130 });
            
            // End drawing
            fireEvent.mouseUp(canvas, { clientX: 120, clientY: 130 });
        });

        test('should resize ROI when dragging handles', () => {
            renderComponent({ selectedROI: mockROI });

            const resizeHandle = screen.getByTestId('resize-handle-roi-1');
            
            fireEvent.mouseDown(resizeHandle, { clientX: 110, clientY: 110 });
            fireEvent.mouseMove(resizeHandle, { clientX: 150, clientY: 150 });
            fireEvent.mouseUp(resizeHandle, { clientX: 150, clientY: 150 });

            expect(defaultProps.onROIUpdate).toHaveBeenCalledWith(
                expect.objectContaining({
                    id: 'roi-1',
                    coordinates: expect.objectContaining({
                        width: expect.any(Number),
                        height: expect.any(Number),
                    }),
                })
            );
        });

        test('should move ROI when dragging', () => {
            renderComponent({ selectedROI: mockROI });

            const roiRect = screen.getByTestId('roi-rect-roi-1');
            
            fireEvent.mouseDown(roiRect, { clientX: 60, clientY: 60 });
            fireEvent.mouseMove(roiRect, { clientX: 80, clientY: 90 });
            fireEvent.mouseUp(roiRect, { clientX: 80, clientY: 90 });

            expect(defaultProps.onROIUpdate).toHaveBeenCalledWith(
                expect.objectContaining({
                    id: 'roi-1',
                    coordinates: expect.objectContaining({
                        x: expect.any(Number),
                        y: expect.any(Number),
                    }),
                })
            );
        });
    });

    describe('Keyboard Interaction', () => {
        test('should support keyboard navigation in ROI list', async () => {
            const user = userEvent.setup();
            renderComponent();

            const roiItem = screen.getByTestId('roi-item-roi-1');
            roiItem.focus();

            await user.keyboard('{Enter}');
            expect(defaultProps.onROISelect).toHaveBeenCalledWith('roi-1');

            await user.keyboard('{Delete}');
            // Should trigger delete confirmation
            expect(screen.getByText(/delete roi/i)).toBeInTheDocument();
        });

        test('should handle keyboard shortcuts in canvas', async () => {
            const user = userEvent.setup();
            renderComponent();

            const canvas = screen.getByTestId('roi-canvas');
            canvas.focus();

            // Escape should cancel current drawing
            await user.keyboard('{Escape}');
            
            // Delete key should delete selected ROI
            await user.keyboard('{Delete}');
        });
    });

    describe('ROI Validation', () => {
        test('should validate ROI coordinates', async () => {
            const user = userEvent.setup();
            renderComponent();

            const nameInput = screen.getByLabelText(/roi name/i);
            await user.type(nameInput, 'Invalid ROI');

            // Set invalid coordinates (negative width)
            const widthInput = screen.getByLabelText(/width/i);
            await user.clear(widthInput);
            await user.type(widthInput, '-50');

            const createBtn = screen.getByRole('button', { name: /create roi/i });
            await user.click(createBtn);

            expect(screen.getByText(/width must be positive/i)).toBeInTheDocument();
            expect(defaultProps.onROICreate).not.toHaveBeenCalled();
        });

        test('should validate ROI bounds within canvas', async () => {
            const user = userEvent.setup();
            renderComponent();

            const nameInput = screen.getByLabelText(/roi name/i);
            await user.type(nameInput, 'Out of bounds ROI');

            // Set coordinates outside canvas bounds
            const xInput = screen.getByLabelText(/x coordinate/i);
            await user.clear(xInput);
            await user.type(xInput, '1000');

            const createBtn = screen.getByRole('button', { name: /create roi/i });
            await user.click(createBtn);

            expect(screen.getByText(/roi extends beyond canvas/i)).toBeInTheDocument();
            expect(defaultProps.onROICreate).not.toHaveBeenCalled();
        });

        test('should prevent overlapping ROIs', async () => {
            const user = userEvent.setup();
            const overlappingROI = {
                ...mockROI,
                id: 'roi-2',
                name: 'Overlapping ROI',
                coordinates: { x: 15, y: 15, width: 50, height: 50 }, // Overlaps with mockROI
            };
            
            renderComponent({ rois: [mockROI, overlappingROI] });

            const nameInput = screen.getByLabelText(/roi name/i);
            await user.type(nameInput, 'Another overlapping ROI');

            // Set coordinates that would overlap
            const xInput = screen.getByLabelText(/x coordinate/i);
            await user.clear(xInput);
            await user.type(xInput, '20');

            const createBtn = screen.getByRole('button', { name: /create roi/i });
            await user.click(createBtn);

            expect(screen.getByText(/roi overlaps with existing roi/i)).toBeInTheDocument();
            expect(defaultProps.onROICreate).not.toHaveBeenCalled();
        });
    });

    describe('Accessibility', () => {
        test('should have proper ARIA labels', () => {
            renderComponent();

            expect(screen.getByRole('region', { name: /roi creator/i })).toBeInTheDocument();
            expect(screen.getByRole('list', { name: /roi list/i })).toBeInTheDocument();
        });

        test('should support screen reader navigation', () => {
            renderComponent({ selectedROI: mockROI });

            const selectedROI = screen.getByTestId('roi-item-roi-1');
            expect(selectedROI).toHaveAttribute('aria-selected', 'true');
            expect(selectedROI).toHaveAttribute('aria-label', 
                expect.stringContaining('Test ROI selected')
            );
        });

        test('should announce ROI operations', async () => {
            const user = userEvent.setup();
            renderComponent();

            const deleteBtn = screen.getByTestId('delete-roi-roi-1');
            await user.click(deleteBtn);

            expect(screen.getByRole('dialog', { name: /confirm delete/i }))
                .toBeInTheDocument();
        });
    });
});