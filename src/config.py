import cv2
import os

# MediaPipe Config
MODEL_FILENAME = 'efficientdet_lite0.tflite'
MODEL_URL = f'https://storage.googleapis.com/mediapipe-models/object_detector/efficientdet_lite0/int8/latest/{MODEL_FILENAME}'
MEDIAPIPE_SCORE_THRESHOLD = 0.3
MEDIAPIPE_MAX_RESULTS = 5

# Video Processing Config
MEDIAPIPE_FRAME_CHECK_INTERVAL_SEC = 0.1 # How often to classify frames
MEDIAPIPE_MERGE_THRESHOLD_FACTOR = 2.0 # Multiplier for interval to get merge gap

# Audio Processing Config
AUDIO_TRIM_TOP_DB = 60

# Editing Styles
EDITING_STYLES = ["Fast-paced", "Standard", "Relaxed"]

# Detection Methods 
METHOD_MEDIAPIPE = "MediaPipe (Scenes & People)" # Currently unused, if more models are added in future then this config will be updated

# Tkinter UI
WINDOW_TITLE = "Recap Assistant for DaVinci Resolve"
WINDOW_GEOMETRY = "650x600"
DEFAULT_THEME = "cosmo"
