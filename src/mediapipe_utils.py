import os
import requests
import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision
from tkinter import messagebox

from config import (
    MODEL_FILENAME, MODEL_URL, MEDIAPIPE_SCORE_THRESHOLD, MEDIAPIPE_MAX_RESULTS
)

OBJECT_DETECTOR = None

def download_model(url=MODEL_URL, filename=MODEL_FILENAME):
    """Downloads the MediaPipe model if it doesn't exist. Returns True on success/exists, False on failure."""
    if not os.path.exists(filename):
        print(f"Downloading MediaPipe Object Detection model from {url}...")
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status() # Raise HTTPError for bad responses
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Model downloaded successfully as {filename}")
            return True
        except requests.exceptions.RequestException as e:
            messagebox.showerror("Download Error", f"Failed to download model '{filename}':\n{e}")
            return False
        except IOError as e:
            messagebox.showerror("File Error", f"Failed write model file '{filename}':\n{e}")
            return False
    else:
        print(f"Model '{filename}' already exists.")
        return True

def load_object_detector(force_reload=False):
    """Loads or returns the cached MediaPipe Object Detector. Returns detector instance or None."""
    global OBJECT_DETECTOR
    if OBJECT_DETECTOR is not None and not force_reload:
        return OBJECT_DETECTOR

    if not download_model():
        OBJECT_DETECTOR = None
        return None

    try:
        print("Initializing MediaPipe Object Detector...")
        base_options = mp_python.BaseOptions(model_asset_path=MODEL_FILENAME)
        options = mp_vision.ObjectDetectorOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.IMAGE,
            score_threshold=MEDIAPIPE_SCORE_THRESHOLD,
            max_results=MEDIAPIPE_MAX_RESULTS
        )
        OBJECT_DETECTOR = mp_vision.ObjectDetector.create_from_options(options)
        print("MediaPipe Object Detector loaded successfully.")
        return OBJECT_DETECTOR
    except Exception as e:
        print(f"ERROR: Failed to initialize MediaPipe Object Detector: {e}")
        # Show error but allow app to continue - maybe another model choosable in future version
        messagebox.showerror(
            "Detector Load Error",
            f"Failed to load MediaPipe Object Detector:\n{e}"
        )
        OBJECT_DETECTOR = None
        return None

def classify_frame_mediapipe(image_cv2, detector):
    """
    Classifies a single frame using the provided MediaPipe Object Detector.
    Returns a scene category string ("People Scene", "Vehicle Scene", etc., or "Other").
    """
    if detector is None:
        print("Warning: classify_frame_mediapipe called with no detector.")
        return "Other" # Or raise an error?

    try:
        image_rgb = cv2.cvtColor(image_cv2, cv2.COLOR_BGR2RGB)
        # Use SRGB as format - colors fine
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = detector.detect(mp_image)

        if not detection_result or not detection_result.detections:
            return "Other"

        best_category = "Other"
        highest_score = 0.0

        for detection in detection_result.detections:
            if not detection.categories: continue # Skip if no categories found

            category = detection.categories[0]
            score = category.score
            label = category.category_name.lower() if category.category_name else ""

            if score >= MEDIAPIPE_SCORE_THRESHOLD and score > highest_score:
                mapped_category = "Other" # Default
                #Categories for Mediapipe - add more later, and into config.py?
                if label == 'person':
                    mapped_category = "People Scene"
                elif label in ['car','truck','bus','motorcycle','bicycle','airplane','boat','train']:
                    mapped_category = "Vehicle Scene"
                elif label in ['cat','dog','bird','horse','sheep','cow','bear','zebra','giraffe','elephant']:
                    mapped_category = "Animal Scene"
                elif label in ['chair','couch','potted plant','bed','dining table','toilet','tv','laptop',
                               'mouse','remote','keyboard','cell phone','microwave','oven','toaster','sink',
                               'refrigerator','book','clock','vase','scissors','teddy bear','hair drier',
                               'toothbrush','cup','fork','knife','spoon','bowl']:
                     mapped_category = "Indoor Scene"
                elif label in ['bench','traffic light','fire hydrant','stop sign','parking meter','tree',
                               'backpack','umbrella','handbag','tie','suitcase','frisbee','skis','snowboard',
                               'sports ball','kite','baseball bat','baseball glove','skateboard','surfboard',
                               'tennis racket','bottle','wine glass']:
                     mapped_category = "Outdoor/Object Scene"
                elif label in ['banana','apple','sandwich','orange','broccoli','carrot','hot dog','pizza','donut','cake']:
                     mapped_category = "Food Scene"
                # Else: remains "Other"

                # If successfully mapped to a category and it's the best score so far
                if mapped_category != "Other":
                    highest_score = score
                    best_category = mapped_category

        return best_category

    except Exception as e:
        print(f"Error during MediaPipe frame classification: {e}")
        return "Other" # Return default on error

def release_detector():
    """Releases the MediaPipe detector resources if loaded."""
    global OBJECT_DETECTOR
    if OBJECT_DETECTOR is not None:
        try:
            print("Releasing MediaPipe detector reference.")
            OBJECT_DETECTOR = None
        except Exception as e:
            print(f"Error potentially releasing MediaPipe detector: {e}")
