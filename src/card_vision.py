import cv2
import numpy as np
import logging
from src.config import (
    CARD_ASPECT_RATIO_MIN,
    CARD_ASPECT_RATIO_MAX,
    CARD_TARGET_WIDTH,
    CARD_TARGET_HEIGHT,
    TITLE_CROP_HEIGHT_PCT,
    ART_CROP_X_START_PCT,
    ART_CROP_X_END_PCT,
    ART_CROP_Y_START_PCT,
    ART_CROP_Y_END_PCT,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class CardVisionProcessor:
    def __init__(self):
        pass

    def find_card_contour(self, frame, processing_width=600):
        """
        Locates the largest 4-corner contour matching the aspect ratio of an MTG card.
        Uses a downscaled copy of the frame for performance, returning coordinates scaled back
        to the original frame's coordinates.
        """
        orig_h, orig_w = frame.shape[:2]
        scale = orig_w / processing_width
        processing_height = int(orig_h / scale)
        
        # 1. Downscale frame
        small_frame = cv2.resize(frame, (processing_width, processing_height))
        
        # 2. Preprocess to isolate borders
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        
        # Bilateral filter preserves edges while smoothing out textures
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        
        # Canny edge detection
        edged = cv2.Canny(blurred, 30, 150)
        
        # Morphological dilation to close gaps in contours
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edged, kernel, iterations=1)
        
        # 3. Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Sort by area descending
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            # Ignore very small contours
            if area < (processing_width * processing_height * 0.05):
                continue
                
            # Approximate the contour with a polygon
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
            
            # We are looking for a quadrilateral (4 points)
            if len(approx) == 4:
                # Check aspect ratio
                pts = approx.reshape(4, 2)
                
                # Sort points: top-left, top-right, bottom-right, bottom-left
                rect = self._order_points(pts)
                (tl, tr, br, bl) = rect
                
                # Compute widths and heights to find aspect ratio
                widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
                widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
                maxWidth = max(int(widthA), int(widthB))
                
                heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
                heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
                maxHeight = max(int(heightA), int(heightB))
                
                if maxHeight == 0:
                    continue
                    
                ratio = maxWidth / float(maxHeight)
                
                # Validate card ratio limits
                if CARD_ASPECT_RATIO_MIN <= ratio <= CARD_ASPECT_RATIO_MAX:
                    # Scale points back to original image size
                    scaled_rect = rect * scale
                    return scaled_rect
                    
        return None

    def warp_card(self, frame, pts):
        """
        Stretches and flattens the detected card vertices into a standardized 744x1039 matrix.
        """
        (tl, tr, br, bl) = pts
        
        # Define destination points in high resolution
        dst = np.array([
            [0, 0],
            [CARD_TARGET_WIDTH - 1, 0],
            [CARD_TARGET_WIDTH - 1, CARD_TARGET_HEIGHT - 1],
            [0, CARD_TARGET_HEIGHT - 1]
        ], dtype="float32")
        
        # Compute perspective transform matrix and warp image
        M = cv2.getPerspectiveTransform(pts.astype("float32"), dst)
        warped = cv2.warpPerspective(frame, M, (CARD_TARGET_WIDTH, CARD_TARGET_HEIGHT))
        return warped

    def crop_title_box(self, warped_card):
        """
        Crops the top ~12% portion containing the card title box.
        """
        crop_h = int(CARD_TARGET_HEIGHT * TITLE_CROP_HEIGHT_PCT)
        title_box = warped_card[0:crop_h, 0:CARD_TARGET_WIDTH]
        return title_box

    def crop_art_box(self, warped_card):
        """
        Crops the card artwork box based on standard layout coordinates.
        """
        y_start = int(CARD_TARGET_HEIGHT * ART_CROP_Y_START_PCT)
        y_end = int(CARD_TARGET_HEIGHT * ART_CROP_Y_END_PCT)
        x_start = int(CARD_TARGET_WIDTH * ART_CROP_X_START_PCT)
        x_end = int(CARD_TARGET_WIDTH * ART_CROP_X_END_PCT)
        
        art_box = warped_card[y_start:y_end, x_start:x_end]
        return art_box

    def _order_points(self, pts):
        """
        Helper method to sort four coordinates in the order:
        top-left, top-right, bottom-right, bottom-left.
        """
        rect = np.zeros((4, 2), dtype="float32")
        
        # Top-left has the minimum sum, bottom-right has maximum sum
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        # Top-right has minimum difference, bottom-left has maximum difference
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        return rect
