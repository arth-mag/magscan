import sqlite3
import logging
from src.config import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._ensure_indexes_and_tables()

    def _connect(self):
        try:
            # Connect to SQLite. Using check_same_thread=False since main thread handles video
            # and database queries can be executed in helper functions or async callbacks.
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logging.error(f"Failed to connect to SQLite database at {self.db_path}: {e}")
            raise e

    def _ensure_indexes_and_tables(self):
        cursor = self.conn.cursor()
        try:
            # 1. Ensure high-performance index on card names exists for faster matching
            logging.info("Checking database indexes...")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cards_name ON cards(name);")
            
            # 2. Ensure custom relational table for dHashes exists (as specified in SDD 6.3)
            # This table links a card's unique `card_id` to its visual dHash representation.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS card_hashes (
                    card_id TEXT PRIMARY KEY,
                    dhash TEXT,
                    FOREIGN KEY(card_id) REFERENCES cards(card_id)
                );
            """)
            
            # 3. Create index on the hashes relational table
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_card_hashes_id ON card_hashes(card_id);")
            
            self.conn.commit()
            logging.info("Database index and structure verification complete.")
        except sqlite3.Error as e:
            logging.error(f"Error checking/creating indexes and tables: {e}")
            self.conn.rollback()

    def get_all_unique_names(self):
        """
        Retrieves all distinct card names from the database.
        Highly optimized for loading into fuzzy matching engines (RapidFuzz) in memory.
        """
        cursor = self.conn.cursor()
        try:
            # Query unique names
            cursor.execute("SELECT DISTINCT name FROM cards WHERE name IS NOT NULL;")
            names = [row['name'] for row in cursor.fetchall()]
            logging.info(f"Loaded {len(names)} unique card names from database.")
            return names
        except sqlite3.Error as e:
            logging.error(f"Error fetching unique card names: {e}")
            return []

    def get_card_variants(self, card_name):
        """
        Given a validated card name, returns all available printed variants and their hashes.
        """
        cursor = self.conn.cursor()
        try:
            # We perform a join between the main cards table and our custom card_hashes table
            cursor.execute("""
                SELECT 
                    c.card_id, 
                    c.name, 
                    c.set_code, 
                    c.set_name, 
                    c.collector_number, 
                    c.rarity,
                    c.sha256 as card_sha256,
                    h.dhash
                FROM cards c
                LEFT JOIN card_hashes h ON c.card_id = h.card_id
                WHERE c.name = ?;
            """, (card_name,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error fetching variants for card '{card_name}': {e}")
            return []

    def save_card_dhash(self, card_id, dhash_value):
        """
        Saves or updates a card's visual dHash in the card_hashes table.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO card_hashes (card_id, dhash) 
                VALUES (?, ?)
                ON CONFLICT(card_id) DO UPDATE SET dhash=excluded.dhash;
            """, (card_id, dhash_value))
            self.conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Error saving dHash for card ID {card_id}: {e}")
            self.conn.rollback()

    def close(self):
        if self.conn:
            self.conn.close()
            logging.info("Database connection closed.")
