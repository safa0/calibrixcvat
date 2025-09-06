# Copyright (C) 2024 Calibrix Corporation
#
# SPDX-License-Identifier: MIT

import logging
import time
from typing import Optional, List, Tuple, Dict, Any
from django.db import transaction
from django.utils import timezone

from ..models import MatchingSession, DetectionResult
from ..algorithms.pipeline import MatchingPipeline
from cvat.apps.engine.frame_provider import TaskFrameProvider
from cvat.apps.engine.models import Task

logger = logging.getLogger(__name__)


class MatchingSessionProcessor:
    """
    Service class for processing matching sessions using computer vision algorithms.
    """
    
    def __init__(self, matching_session_id: int):
        """Initialize the processor with a matching session."""
        try:
            self.matching_session = MatchingSession.objects.select_related(
                'roi_template', 'task'
            ).get(id=matching_session_id)
        except MatchingSession.DoesNotExist:
            raise ValueError(f"Matching session {matching_session_id} not found")
        
        self.task = self.matching_session.task
        self.roi_template = self.matching_session.roi_template
        self.frame_provider = None
        self.pipeline = None
    
    def setup_frame_provider(self):
        """Setup frame provider for accessing video frames."""
        try:
            self.frame_provider = TaskFrameProvider(
                self.task.data,
                task_id=self.task.id,
            )
            logger.info(f"Frame provider setup complete for task {self.task.id}")
        except Exception as e:
            logger.error(f"Failed to setup frame provider: {e}")
            raise
    
    def setup_matching_pipeline(self):
        """Setup the matching pipeline based on session configuration."""
        try:
            self.pipeline = MatchingPipeline(
                algorithm_type=self.matching_session.algorithm_type,
                threshold=self.matching_session.threshold
            )
            
            # Load ROI template into pipeline
            self.pipeline.load_template(
                coordinates=self.roi_template.coordinates,
                feature_descriptor=self.roi_template.feature_descriptor
            )
            
            logger.info(f"Matching pipeline setup complete for session {self.matching_session.id}")
        except Exception as e:
            logger.error(f"Failed to setup matching pipeline: {e}")
            raise
    
    def process_frame(self, frame_number: int) -> List[Dict[str, Any]]:
        """
        Process a single frame and return detection results.
        
        Args:
            frame_number: Frame number to process
            
        Returns:
            List of detection dictionaries with coordinates and confidence scores
        """
        try:
            # Get frame data
            frame_data = self.frame_provider.get_frame(
                frame_number,
                quality=self.frame_provider.Quality.ORIGINAL
            )
            
            # Run matching algorithm
            detections = self.pipeline.match_frame(frame_data, frame_number)
            
            return detections
            
        except Exception as e:
            logger.error(f"Error processing frame {frame_number}: {e}")
            return []
    
    def save_detection_results(self, detections: List[Dict[str, Any]], frame_number: int):
        """
        Save detection results to the database.
        
        Args:
            detections: List of detection dictionaries
            frame_number: Frame number these detections belong to
        """
        try:
            detection_objects = []
            
            for detection in detections:
                detection_obj = DetectionResult(
                    matching_session=self.matching_session,
                    frame_number=frame_number,
                    coordinates=detection['coordinates'],
                    confidence_score=detection['confidence_score']
                )
                detection_objects.append(detection_obj)
            
            if detection_objects:
                with transaction.atomic():
                    DetectionResult.objects.bulk_create(detection_objects, batch_size=100)
                
                logger.info(f"Saved {len(detection_objects)} detection results for frame {frame_number}")
            
        except Exception as e:
            logger.error(f"Error saving detection results for frame {frame_number}: {e}")
            raise
    
    def update_session_status(self, status: str, error_message: Optional[str] = None):
        """
        Update matching session status.
        
        Args:
            status: New status for the session
            error_message: Optional error message if status is FAILED
        """
        try:
            self.matching_session.status = status
            self.matching_session.updated_at = timezone.now()
            
            # You might want to add an error_message field to the model
            # For now, we'll just log the error
            if error_message:
                logger.error(f"Session {self.matching_session.id} failed: {error_message}")
            
            self.matching_session.save()
            logger.info(f"Updated session {self.matching_session.id} status to {status}")
            
        except Exception as e:
            logger.error(f"Error updating session status: {e}")
            raise
    
    def process_session(self, frame_range: Optional[Tuple[int, int]] = None, 
                       progress_callback: Optional[callable] = None):
        """
        Process the entire matching session.
        
        Args:
            frame_range: Optional tuple of (start_frame, end_frame) to process
            progress_callback: Optional callback function for progress updates
        """
        try:
            # Setup components
            self.setup_frame_provider()
            self.setup_matching_pipeline()
            
            # Determine frame range
            total_frames = self.task.data.size
            start_frame = 0
            end_frame = total_frames - 1
            
            if frame_range:
                start_frame, end_frame = frame_range
                end_frame = min(end_frame, total_frames - 1)
            
            logger.info(f"Processing frames {start_frame} to {end_frame} for session {self.matching_session.id}")
            
            # Process frames
            total_detections = 0
            processed_frames = 0
            
            for frame_number in range(start_frame, end_frame + 1):
                try:
                    # Process frame
                    detections = self.process_frame(frame_number)
                    
                    # Save results
                    if detections:
                        self.save_detection_results(detections, frame_number)
                        total_detections += len(detections)
                    
                    processed_frames += 1
                    
                    # Update progress
                    if progress_callback:
                        progress = (processed_frames / (end_frame - start_frame + 1)) * 100
                        progress_callback(progress, processed_frames, total_detections)
                    
                    # Log progress periodically
                    if processed_frames % 100 == 0:
                        logger.info(f"Processed {processed_frames} frames, found {total_detections} detections")
                    
                except Exception as frame_error:
                    logger.warning(f"Error processing frame {frame_number}: {frame_error}")
                    continue
            
            # Update session as completed
            self.update_session_status(MatchingSession.Status.COMPLETED)
            
            logger.info(f"Completed processing session {self.matching_session.id}: "
                       f"{processed_frames} frames processed, {total_detections} detections found")
            
            return {
                'processed_frames': processed_frames,
                'total_detections': total_detections,
                'status': 'completed'
            }
            
        except Exception as e:
            # Update session as failed
            self.update_session_status(MatchingSession.Status.FAILED, str(e))
            logger.error(f"Failed to process session {self.matching_session.id}: {e}")
            raise


def run_matching_task(matching_session_id: int, frame_range: Optional[List[int]] = None):
    """
    RQ task function for running matching sessions.
    
    Args:
        matching_session_id: ID of the matching session to process
        frame_range: Optional list of [start_frame, end_frame] to process
    
    Returns:
        Dictionary with processing results
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting matching task for session {matching_session_id}")
        
        # Create processor
        processor = MatchingSessionProcessor(matching_session_id)
        
        # Convert frame_range list to tuple if provided
        frame_range_tuple = tuple(frame_range) if frame_range else None
        
        # Define progress callback for RQ job updates
        def progress_callback(progress: float, processed_frames: int, total_detections: int):
            # This could be used to update job progress in Redis
            # For now, just log the progress
            logger.info(f"Session {matching_session_id} progress: {progress:.1f}% "
                       f"({processed_frames} frames, {total_detections} detections)")
        
        # Process the session
        result = processor.process_session(
            frame_range=frame_range_tuple,
            progress_callback=progress_callback
        )
        
        # Add timing information
        duration = time.time() - start_time
        result['duration_seconds'] = duration
        result['session_id'] = matching_session_id
        
        logger.info(f"Completed matching task for session {matching_session_id} in {duration:.1f} seconds")
        
        return result
        
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Matching task failed for session {matching_session_id} after {duration:.1f} seconds: {e}"
        logger.error(error_msg)
        
        # Try to update session status even if processing failed
        try:
            processor = MatchingSessionProcessor(matching_session_id)
            processor.update_session_status(MatchingSession.Status.FAILED, str(e))
        except Exception as status_error:
            logger.error(f"Failed to update session status: {status_error}")
        
        raise Exception(error_msg)


def cancel_matching_task(matching_session_id: int, rq_job_id: Optional[str] = None):
    """
    Cancel a running matching task.
    
    Args:
        matching_session_id: ID of the matching session to cancel
        rq_job_id: Optional RQ job ID to cancel
    
    Returns:
        Boolean indicating if cancellation was successful
    """
    try:
        logger.info(f"Cancelling matching task for session {matching_session_id}")
        
        # Update session status
        processor = MatchingSessionProcessor(matching_session_id)
        processor.update_session_status(MatchingSession.Status.FAILED, "Cancelled by user")
        
        # Cancel RQ job if job ID provided
        if rq_job_id:
            try:
                import django_rq
                from rq.job import Job
                
                queue = django_rq.get_queue('default')
                job = Job.fetch(rq_job_id, connection=queue.connection)
                
                if job and not job.is_finished:
                    job.cancel()
                    logger.info(f"Cancelled RQ job {rq_job_id}")
                
            except Exception as job_error:
                logger.warning(f"Failed to cancel RQ job {rq_job_id}: {job_error}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to cancel matching task for session {matching_session_id}: {e}")
        return False


def get_matching_task_progress(matching_session_id: int) -> Dict[str, Any]:
    """
    Get the current progress of a matching task.
    
    Args:
        matching_session_id: ID of the matching session
        
    Returns:
        Dictionary with progress information
    """
    try:
        matching_session = MatchingSession.objects.get(id=matching_session_id)
        detection_count = matching_session.detection_results.count()
        
        # Calculate basic progress information
        progress_info = {
            'session_id': matching_session_id,
            'status': matching_session.status,
            'total_detections': detection_count,
            'confirmed_detections': matching_session.detection_results.filter(is_confirmed=True).count(),
            'created_at': matching_session.created_at.isoformat(),
            'updated_at': matching_session.updated_at.isoformat(),
        }
        
        # Add task information
        if matching_session.task:
            progress_info['task_id'] = matching_session.task.id
            progress_info['total_frames'] = matching_session.task.data.size if matching_session.task.data else 0
        
        return progress_info
        
    except MatchingSession.DoesNotExist:
        raise ValueError(f"Matching session {matching_session_id} not found")
    except Exception as e:
        logger.error(f"Error getting progress for session {matching_session_id}: {e}")
        raise