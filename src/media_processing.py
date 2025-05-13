import librosa
import numpy as np
import cv2
import os
import traceback

# Import utilities and config
from config import (
    MEDIAPIPE_FRAME_CHECK_INTERVAL_SEC, MEDIAPIPE_MERGE_THRESHOLD_FACTOR,
    METHOD_MEDIAPIPE, AUDIO_TRIM_TOP_DB # METHOD_MEDIAPIPE unused for now - check config.py
)
from mediapipe_utils import classify_frame_mediapipe, load_object_detector

def get_bpm_and_offset(audio_path):
    """
    Estimates BPM, detects audio start offset, and gets total duration using librosa.

    Returns:
        tuple: (estimated_tempo, beat_duration, start_offset_sec, total_audio_duration_sec)
               or raises Exception on failure.
    """
    print(f"Analyzing audio: {os.path.basename(audio_path)}")
    tempo = None
    start_offset_sec = 0.0
    beat_duration_sec = None
    total_audio_duration_sec = None
    y = None
    sr = None

    try:
        print("  Loading audio...")
        y, sr = librosa.load(audio_path, sr=None)
        # Get total duration immediately after loading
        total_audio_duration_sec = librosa.get_duration(y=y, sr=sr)
        print(f"  Total Audio Duration: {total_audio_duration_sec:.3f} sec")

        print("  Trimming silence...")
        y_trimmed, index = librosa.effects.trim(y, top_db=AUDIO_TRIM_TOP_DB)
        if index.size > 0 and index[0] > 0:
            start_offset_sec = librosa.samples_to_time(index[0], sr=sr)
        print(f"  Audio Start Offset: {start_offset_sec:.3f} sec")

        print("  Analyzing rhythm...")
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)

        print("  Tracking beats...")
        # Use the original 'y' for beat tracking as trimming might affect stability
        estimated_tempo_val, beats = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env)

        if estimated_tempo_val is not None:
            if isinstance(estimated_tempo_val, (np.ndarray, list)) and len(estimated_tempo_val) > 0:
                tempo = float(estimated_tempo_val[0])
            elif isinstance(estimated_tempo_val, (int, float)):
                tempo = float(estimated_tempo_val)

            if tempo is not None:
                print(f"  Tempo from beat_track: {tempo:.2f}")

        # Fallback 1: Median interval if beat_track fails but gives beats
        if tempo is None and beats is not None and len(beats) > 1:
            print("  Using beat interval fallback...")
            beat_times = librosa.frames_to_time(beats, sr=sr)
            intervals = np.diff(beat_times)
            if len(intervals) > 0:
                median_interval = np.median(intervals)
                if median_interval > 0:
                    calculated_tempo = 60.0 / median_interval
                    # Check if tempo is within a reasonable range
                    if 30 < calculated_tempo < 300:
                        tempo = calculated_tempo
                        print(f"  Tempo from median interval: {tempo:.2f}")

        # Fallback 2: librosa.feature.rhythm.tempo
        if tempo is None:
            print("  Using feature.rhythm.tempo fallback...")
            # Consider using y_trimmed here if initial silence is very long? Test needed.
            tempo_estimates = librosa.feature.rhythm.tempo(y=y, sr=sr, onset_envelope=onset_env)
            if tempo_estimates is not None and len(tempo_estimates) > 0:
                tempo = float(tempo_estimates[0])
                print(f"  Tempo from feature.rhythm.tempo: {tempo:.2f}")

        # Final check and calculation
        if tempo is not None and np.isfinite(tempo) and tempo > 0 and total_audio_duration_sec is not None:
            raw_tempo = tempo
            estimated_tempo_rounded = round(raw_tempo) # For info only
            beat_duration_sec = 60.0 / raw_tempo
            print(f"  Final Est. BPM: {raw_tempo:.2f} (Rounded: {estimated_tempo_rounded})")
            print(f"  Beat Duration: {beat_duration_sec:.4f} sec")
            return raw_tempo, beat_duration_sec, start_offset_sec, total_audio_duration_sec
        else:
            err_msg = "Could not estimate a valid BPM."
            if total_audio_duration_sec is None:
                err_msg = "Could not determine audio duration."
            raise ValueError(err_msg)

    except Exception as e:
        print(f"ERROR during audio analysis: {e}")
        # Re-raise exception for the main thread to handle UI feedback
        raise Exception(f"Audio analysis failed for {os.path.basename(audio_path)}: {e}")

def _detect_scenes_mediapipe(video_path, detector):
    """Internal helper: Detects scene segments using MediaPipe. Returns [(start, end, label, fname), ...]."""
    base_name = os.path.basename(video_path)
    if detector is None:
        # Safety check
        raise ValueError("MediaPipe detector is not loaded.")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError(f"Could not open video: {base_name}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        cap.release()
        raise ValueError(f"Invalid FPS ({fps}) for video: {base_name}")

    # Determine how often to check frames and the time threshold for merging segments
    frame_interval_frames = max(1, int(fps * MEDIAPIPE_FRAME_CHECK_INTERVAL_SEC))
    merge_threshold_seconds = MEDIAPIPE_FRAME_CHECK_INTERVAL_SEC * MEDIAPIPE_MERGE_THRESHOLD_FACTOR

    raw_moments = []
    current_segment_start_time = 0.0
    current_segment_label = None
    last_processed_timestamp_sec = 0.0
    frame_count = 0

    try:
        ret, first_frame = cap.read()
        if not ret:
            raise IOError(f"Cannot read first frame of video: {base_name}")

        # Classify the first frame to initialize the state
        initial_label = classify_frame_mediapipe(first_frame, detector)
        current_segment_label = initial_label
        frame_count = 1

        # Process video frame by frame (or at intervals)
        while True:
            ret, frame = cap.read()
            if not ret:
                break # End of video

            current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
            # Ensure timestamp progresses even if MSEC doesn't update reliably
            current_timestamp_sec = max(last_processed_timestamp_sec + (1.0 / fps if fps > 0 else 0.01), current_msec / 1000.0)

            # Check frame at the specified interval
            if frame_count % frame_interval_frames == 0:
                label = classify_frame_mediapipe(frame, detector)

                # Check if the label has changed
                if label != current_segment_label:
                    segment_end_time = current_timestamp_sec
                    # Record the previous segment if it was NOT 'Other'
                    if current_segment_label != 'Other' and current_segment_label is not None:
                        if segment_end_time > current_segment_start_time:
                            raw_moments.append((current_segment_start_time, segment_end_time, current_segment_label, base_name))
                    # Start a new segment
                    current_segment_start_time = segment_end_time
                    current_segment_label = label

            last_processed_timestamp_sec = current_timestamp_sec
            frame_count += 1

        # Record the very last segment if it wasn't 'Other'
        final_timestamp = last_processed_timestamp_sec
        if current_segment_label != 'Other' and current_segment_label is not None:
            if final_timestamp > current_segment_start_time:
                raw_moments.append((current_segment_start_time, final_timestamp, current_segment_label, base_name))

    finally:
        # Ensure video capture is released
        cap.release()

    if not raw_moments:
        return [] # Return empty list if no relevant segments found

    # Merge adjacent segments of the same type if the gap between them is small
    raw_moments.sort(key=lambda x: x[0]) # Sort by start time first
    merged_segments = []
    if raw_moments:
        current_segment = list(raw_moments[0]) # Use a mutable list for the current segment being built
        for i in range(1, len(raw_moments)):
            next_start, next_end, next_label, _ = raw_moments[i]
            last_start, last_end, last_label, _ = current_segment
            gap = next_start - last_end # Time difference between segments

            # Check if labels match and the gap is within the merging threshold
            if next_label == last_label and gap >= 0 and gap <= merge_threshold_seconds:
                # Merge: Extend the end time of the current segment to cover the next one
                current_segment[1] = max(last_end, next_end)
            else:
                # Don't merge: Finalize the current segment and add it to the list
                merged_segments.append(tuple(current_segment))
                # Start a new current segment from the next raw moment
                current_segment = list(raw_moments[i])

        # Append the last processed segment after the loop finishes
        merged_segments.append(tuple(current_segment))

    return merged_segments


# General Video Moment Detection Function
def detect_video_moments(video_path, beat_duration_sec):
    """
    Detects moments using MediaPipe, merges them, and filters based on MINIMUM DURATION OF 2 BEATS.

    Args:
        video_path (str): Path to the video file.
        beat_duration_sec (float): The duration of a single beat in seconds.

    Returns:
        tuple: (list_of_people_moments, list_of_other_scene_moments)
               Format: [(start, end, label, fname)]
        Raises Exception on critical errors.
    """
    people_moments = []
    other_scene_moments = []
    base_name = os.path.basename(video_path)
    # Calculate minimum required duration (2 beats)
    min_required_duration_sec = beat_duration_sec * 2.0 if beat_duration_sec and beat_duration_sec > 0 else 0

    print(f"Processing video '{base_name}' using MediaPipe (Filtering for duration >= {min_required_duration_sec:.3f}s)")

    if min_required_duration_sec <= 0:
           print("  Warning: Invalid beat duration or <= 0, cannot apply 2-beat minimum filter.")
           min_required_duration_sec = 0 # Effectively disable filter

    # Load MediaPipe detector instance
    detector = load_object_detector()
    if detector is None:
           raise RuntimeError("MediaPipe Object Detector could not be loaded.")

    try:
        # Get candidate moments
        candidate_moments = _detect_scenes_mediapipe(video_path, detector)

        # Filter candidates by minimum duration and separate into People vs Other - maybe in future let user choose which they want ...
        filtered_people_count = 0
        filtered_other_count = 0
        discarded_count = 0
        for start, end, label, fname in candidate_moments:
            duration = end - start
            # Apply the minimum duration filter
            if duration >= min_required_duration_sec:
                if label == "People Scene":
                    # Standardize label to "People"
                    people_moments.append((start, end, "People", fname))
                    filtered_people_count += 1
                else:
                    # Keep other specific labels (e.g., 'Vehicle', 'Animal')
                    other_scene_moments.append((start, end, label, fname))
                    filtered_other_count += 1
            else:
                # Clip is shorter than the minimum required duration
                discarded_count += 1

        print(f"  Found & Kept: {filtered_people_count} People, {filtered_other_count} Other moments (after >= {min_required_duration_sec:.3f}s filter). Discarded {discarded_count} short segments.")

    except Exception as e:
        print(f"ERROR processing video {base_name}: {e}")
        raise

    return people_moments, other_scene_moments
