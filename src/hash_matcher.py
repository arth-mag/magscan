import cv2
import numpy as np
import logging
from src.config import HAMMING_MAX_DISTANCE

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class HashMatcher:
    def __init__(self, hash_size=8):
        self.hash_size = hash_size

    def compute_dhash(self, image):
        """
        Computes the 64-bit Difference Hash (dHash) for an OpenCV image.
        Difference Hash focuses on gradients and is extremely resilient to brightness changes.
        """
        try:
            # 1. Resize to (hash_size + 1) x hash_size
            resized = cv2.resize(image, (self.hash_size + 1, self.hash_size), interpolation=cv2.INTER_AREA)
            
            # 2. Convert to grayscale if it is in color
            if len(resized.shape) == 3:
                gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
            else:
                gray = resized
                
            # 3. Calculate adjacent pixel differences (horizontal)
            diff = gray[:, 1:] > gray[:, :-1]
            
            # 4. Pack the boolean array into a 64-bit hexadecimal string
            decimal_value = 0
            for row in diff:
                for bit in row:
                    decimal_value = (decimal_value << 1) | int(bit)
            
            # Ensure it is represented as a 16-character hexadecimal string
            return f"{decimal_value:016x}"
        except Exception as e:
            logging.error(f"Error computing dHash: {e}")
            return ""

    def calculate_hamming_distance(self, hash1, hash2):
        """
        Computes the number of differing bits between two hex hash strings.
        """
        try:
            if not hash1 or not hash2:
                return 999
                
            h1 = int(hash1, 16)
            h2 = int(hash2, 16)
            
            # XOR the two integers and count the set bits (1s)
            return bin(h1 ^ h2).count('1')
        except ValueError:
            return 999

    def match_best_variant(self, current_art_image, variants):
        """
        Given the crop of the card art and a list of candidates from SQLite
        (each containing a precomputed 'dhash' value), returns the closest printed variant.
        """
        if not variants:
            return None, 999

        # Generate dHash of the live captured frame
        current_hash = self.compute_dhash(current_art_image)
        if not current_hash:
            return None, 999

        best_match = None
        min_distance = 999

        for variant in variants:
            db_hash = variant.get('dhash')
            if not db_hash:
                continue

            distance = self.calculate_hamming_distance(current_hash, db_hash)
            if distance < min_distance:
                min_distance = distance
                best_match = variant

        # Respect max hamming distance filter
        if min_distance <= HAMMING_MAX_DISTANCE:
            return best_match, min_distance
        else:
            logging.info(f"Best visual match too distant: distance={min_distance} (limit={HAMMING_MAX_DISTANCE})")
            return None, min_distance
class HashMatcherHelper:
    """
    Utility class for batch-processing and loading database hashes
    """
    @staticmethod
    def sha256_to_dhash_dummy(sha256_str):
        """
        Fallback converter: generates a deterministic 64-bit hex hash out of a SHA-256 string
        in case we don't have downloaded artwork yet.
        """
        if not sha256_str or len(sha256_str) < 16:
            return "0000000000000000"
        return sha256_str[:16]
