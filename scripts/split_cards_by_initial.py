import os
import re
import sqlite3

# Paths
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
ORIGINAL_DB = os.path.join(BASE_DIR, 'cards.db')
TARGET_DIR = os.path.join(BASE_DIR, 'cards_db')

# Ensure target directory exists
os.makedirs(TARGET_DIR, exist_ok=True)

# Schema definition (same as original cards table and card_hashes table)
SCHEMA_SQL = '''
CREATE TABLE IF NOT EXISTS cards (
    card_id TEXT PRIMARY KEY,
    name TEXT,
    set_code TEXT,
    collector_number TEXT
);

-- Indexes for fast look‑ups
CREATE INDEX IF NOT EXISTS idx_name ON cards(name);
CREATE INDEX IF NOT EXISTS idx_set_code ON cards(set_code);
CREATE INDEX IF NOT EXISTS idx_collector ON cards(collector_number);
CREATE INDEX IF NOT EXISTS idx_lookup ON cards(name, set_code, collector_number);
'''

TARGET_COLUMNS = ['card_id', 'name', 'set_code', 'collector_number']



def ensure_schema(db_path: str):
    # If a DB already exists with a previous (larger) schema, remove it to enforce the reduced schema.
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError as e:
            print(f"Warning: could not delete existing DB {db_path}: {e}")
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()

def get_target_db(name: str) -> str:
    """Return the path of the DB file based on the first alphabetical character of name.
    Non‑alphabetic or missing leads to 'others.db'.
    """
    if not name:
        return os.path.join(TARGET_DIR, 'others.db')
    # Find first alphabetical character
    match = re.search(r'[A-Za-z]', name)
    if not match:
        return os.path.join(TARGET_DIR, 'others.db')
    letter = match.group(0).upper()
    return os.path.join(TARGET_DIR, f"{letter}.db")


def main():
    if not os.path.exists(ORIGINAL_DB):
        return

    src_conn = sqlite3.connect(ORIGINAL_DB)
    src_cur = src_conn.cursor()

    # Iterate over cards table
    src_cur.execute('SELECT * FROM cards')
    rows = src_cur.fetchall()
    col_names = [description[0] for description in src_cur.description]

    for row in rows:
        row_dict = dict(zip(col_names, row))
        name = row_dict.get('name', '')
        target_db = get_target_db(name)
        # Ensure target schema exists
        ensure_schema(target_db)
        # Insert card row
        # Insert only the needed columns
        tgt_conn = sqlite3.connect(target_db)
        tgt_cur = tgt_conn.cursor()
        values = tuple(row_dict.get(col) for col in TARGET_COLUMNS)
        placeholders = ','.join('?' * len(TARGET_COLUMNS))
        insert_sql = f"INSERT OR REPLACE INTO cards ({', '.join(TARGET_COLUMNS)}) VALUES ({placeholders})"
        tgt_cur.execute(insert_sql, values)
        tgt_conn.commit()
        tgt_conn.close()

        # Skipping card_hashes copy to keep reduced DB size

    src_conn.close()
    # Delete original database after successful split
    try:
        os.remove(ORIGINAL_DB)
    except OSError as e:
        print(f"Warning: could not delete original DB: {e}")
    print(f"Split completed. Created databases in {TARGET_DIR}")

if __name__ == '__main__':
    main()
