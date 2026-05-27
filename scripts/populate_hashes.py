#!/usr/bin/env python3
"""populate_hashes.py

Utility script that scans the existing `cards.db` SQLite database and ensures every
card has an associated visual hash (dHash) stored in the auxiliary table
`card_hashes`.  In the initial prototype we do not have the actual artwork images
available on the edge device; therefore we generate a deterministic **dummy**
64‑bit hash derived from the existing `sha256` column (first 16 hex characters).
This allows the rest of the pipeline (visual matching) to function out‑of‑the‑
box while the real image‑hash generation can be added later when the assets are
available.

Usage:
    $ python scripts/populate_hashes.py

The script is safe to run multiple times – it will only insert missing entries
or update an existing hash if the computed dummy value differs.
"""

import logging
import sqlite3
import os
import sys

# Ensure the project root is in PYTHONPATH so we can import src modules
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database import DatabaseManager
from src.hash_matcher import HashMatcherHelper

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    logging.info("Starting dHash population script...")
    db = DatabaseManager()

    # 1. Fetch all cards (id, sha256) that do NOT yet have a dHash entry.
    query = """
        SELECT c.card_id, c.sha256
        FROM cards c
        LEFT JOIN card_hashes h ON c.card_id = h.card_id
        WHERE h.card_id IS NULL;
    """
    cursor = db.conn.cursor()
    cursor.execute(query)
    missing = cursor.fetchall()

    if not missing:
        logging.info("All cards already have a dHash entry. Nothing to do.")
        db.close()
        return

    logging.info(f"Found {len(missing)} cards without dHash. Computing dummy hashes...")
    for row in missing:
        card_id = row[0]
        sha256 = row[1]
        dummy_hash = HashMatcherHelper.sha256_to_dhash_dummy(sha256)
        db.save_card_dhash(card_id, dummy_hash)
        logging.debug(f"Inserted dummy dHash for card_id {card_id}: {dummy_hash}")

    logging.info("dHash population complete.")
    db.close()

if __name__ == "__main__":
    main()
