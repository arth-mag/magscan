# pyrefly: ignore [missing-import]
import sys
import os
import cv2
import json
import threading
import queue
import logging
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.config import (
    INVENTORY_PATH,
    CAMERA_INDEX,
    CAMERA_WIDTH,
    CAMERA_HEIGHT,
)
from src.database import DatabaseManager
from src.card_vision import CardVisionProcessor
from src.text_extractor import TextExtractor
from src.hash_matcher import HashMatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class InventorySaver:
    def __init__(self, file_path=INVENTORY_PATH):
        self.file_path = file_path
        self.queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def add_to_inventory(self, name, set_code, card_id):
        item = {
            "nome": name,
            "edicao": set_code.upper() if set_code else "UNKNOWN",
            "scryfall_id": card_id,
            "timestamp_scan": datetime.now().isoformat()
        }
        self.queue.put(item)

    def _worker(self):
        while True:
            item = self.queue.get()
            if item is None:
                break
            self._save_item(item)
            self.queue.task_done()

    def _save_item(self, item):
        data = []
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
            except Exception as e:
                logging.error(f"Error reading inventory file: {e}")

        data.append(item)
        
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logging.info(f"Successfully recorded card in inventory: {item['nome']} [{item['edicao']}]")
        except Exception as e:
            logging.error(f"Failed to write to inventory file: {e}")

def main():
    logging.info("Starting MagScan application...")
    
    # 1. Initialize SQLite Database Manager
    db = DatabaseManager()
    
    # 2. Pre-load unique names for extremely fast memory fuzzy-matching
    unique_names = db.get_all_unique_names()
    
    # 3. Instantiate pipeline components
    vision = CardVisionProcessor()
    extractor = TextExtractor(unique_names)
    matcher = HashMatcher()
    saver = InventorySaver()

    # 4. Open video capture
    logging.info(f"Accessing video input source (camera index {CAMERA_INDEX})...")
    cap = cv2.VideoCapture(CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
    
    if not cap.isOpened():
        logging.error("Failed to open camera interface. Exiting.")
        return

    # Track processed/detected card to prevent registering duplicate scans continuously
    last_registered_card = None
    frames_since_last_detection = 0

    logging.info("MagScan Pipeline ready. Place a card in the viewing area.")
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logging.warning("Failed to receive video frame.")
                break

            # Clone frame for UI drawing
            display_frame = frame.copy()
            
            # Detect card geometry
            card_points = vision.find_card_contour(frame)
            
            if card_points is not None:
                frames_since_last_detection = 0
                
                # Draw green contour around the card on the visual display
                pts_int = card_points.astype(int)
                cv2.polylines(display_frame, [pts_int], True, (0, 255, 0), 3)
                
                # Flatten the perspective to a 744x1039 card image
                warped = vision.warp_card(frame, card_points)
                
                # Extract regions of interest (ROI)
                title_box = vision.crop_title_box(warped)
                art_box = vision.crop_art_box(warped)
                
                # Run OCR
                raw_ocr_text = extractor.extract_title(title_box)
                
                if raw_ocr_text:
                    # Fuzzy match OCR text against clean name catalogue
                    official_name, confidence = extractor.fuzzy_match(raw_ocr_text)
                    
                    if official_name:
                        # Avoid double scans of the same card in immediate succession
                        if official_name != last_registered_card:
                            logging.info(f"Detected card name candidate: '{official_name}' (Confidence: {confidence:.1f}%)")
                            
                            # Retrieve print variants from database
                            variants = db.get_card_variants(official_name)
                            
                            # Match print artwork via Difference Hash
                            best_variant, hamming_dist = matcher.match_best_variant(art_box, variants)
                            
                            if best_variant:
                                set_code = best_variant.get("set_code", "UNKNOWN")
                                card_id = best_variant.get("card_id")
                                
                                # Save card to inventory asynchronously
                                saver.add_to_inventory(official_name, set_code, card_id)
                                last_registered_card = official_name
                            else:
                                # Fallback: if dHash mapping doesn't exist yet, register default/first variant
                                if variants:
                                    first_var = variants[0]
                                    logging.warning("No precise dHash match. Registering default variant.")
                                    saver.add_to_inventory(
                                        official_name, 
                                        first_var.get("set_code", "UNKNOWN"), 
                                        first_var.get("card_id")
                                    )
                                    last_registered_card = official_name
            else:
                frames_since_last_detection += 1
                # If no card is seen for 30 frames, reset memory to allow scanning the card again later
                if frames_since_last_detection > 30:
                    last_registered_card = None

            # Render live camera feed window
            cv2.imshow("MagScan Active Monitor", cv2.resize(display_frame, (960, 540)))
            
            # Allow quit on 'q' key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                logging.info("Exiting application loop.")
                break

    except KeyboardInterrupt:
        logging.info("Program interrupted by keyboard command.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        db.close()
        logging.info("Application cleanly shut down.")

if __name__ == "__main__":
    main()
