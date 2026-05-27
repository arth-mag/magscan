import cv2
import pytesseract
import logging
from rapidfuzz import process, fuzz
from .config import OCR_CONFIG, FUZZY_MIN_RATIO
from src.config import OCR_CONFIG, FUZZY_MIN_RATIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class TextExtractor:
    def __init__(self, unique_names=None):
        """
        Initializes the text extractor with an optional list of unique card names 
        for immediate fuzzy matching.
        """
        self.unique_names = unique_names if unique_names is not None else []

    def set_unique_names(self, names):
        self.unique_names = names

    def extract_title(self, title_crop):
        """
        Preprocesses the cropped title region and extracts text via Tesseract.
        """
        try:
            # 1. Grayscale
            gray = cv2.cvtColor(title_crop, cv2.COLOR_BGR2GRAY)
            
            # 2. Upscale (3x) to increase character stroke thickness for OCR accuracy
            upscaled = cv2.resize(gray, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
            
            # 3. Apply light Gaussian Blur to smooth out print halftone dots
            blurred = cv2.GaussianBlur(upscaled, (3, 3), 0)
            
            # 4. Binarization (Otsu thresholding)
            _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Run pytesseract OCR using restrictive config flags
            raw_text = pytesseract.image_to_string(thresh, config=OCR_CONFIG)
            
            # Clean raw output: strip whitespace and newlines
            clean_text = raw_text.strip().replace("\n", "")
            return clean_text
            
        except Exception as e:
            logging.error(f"OCR Extraction failed: {e}")
            return ""

    def fuzzy_match(self, query):
        """
        Compares raw text string from OCR against all unique database names
        using Levenshtein similarity metric (RapidFuzz).
        """
        if not query or not self.unique_names:
            return None, 0.0

        # RapidFuzz match against unique names
        match_result = process.extractOne(
            query, 
            self.unique_names, 
            scorer=fuzz.WRatio
        )
        
        if match_result:
            matched_name, score, _ = match_result
            if score >= FUZZY_MIN_RATIO:
                return matched_name, score
            else:
                logging.info(f"Fuzzy Match low score: '{query}' -> '{matched_name}' ({score}%)")
                return matched_name, score
                
        return None, 0.0
