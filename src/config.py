import os

# Database and file paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "cards.db")
INVENTORY_PATH = os.path.join(BASE_DIR, "inventario.json")

# Card aspect ratio & size
CARD_ASPECT_RATIO_MIN = 0.68
CARD_ASPECT_RATIO_MAX = 0.75
CARD_TARGET_WIDTH = 744
CARD_TARGET_HEIGHT = 1039

# Crop percentages for regions of interest (ROI)
# Title Box (usually in the top 11-12%)
TITLE_CROP_HEIGHT_PCT = 0.12

# Art Box (typically spans between 12% and 55% vertically, and has side margins)
ART_CROP_Y_START_PCT = 0.12
ART_CROP_Y_END_PCT = 0.55
ART_CROP_X_START_PCT = 0.08
ART_CROP_X_END_PCT = 0.92

# OCR Settings
OCR_WHITELIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',- "
OCR_CONFIG = f"--psm 7 --oem 1 -c tessedit_char_whitelist=\"{OCR_WHITELIST}\""

# Tolerances and matching thresholds
FUZZY_MIN_RATIO = 80.0  # RapidFuzz similarity threshold
HAMMING_MAX_DISTANCE = 12 # Maximum Hamming distance allowed for a valid dHash match

# Camera configurations
CAMERA_INDEX = 0
CAMERA_WIDTH = 1920
CAMERA_HEIGHT = 1080
CAMERA_EXPOSURE = -5  # Manual exposure settings (hardware dependent)
