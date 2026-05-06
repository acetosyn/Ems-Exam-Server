# user_credentials.py
import random
import string
import sqlite3
from pathlib import Path
from datetime import datetime
import csv

DB_PATH = Path("database.db")
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)


def init_db():
    """Ensure candidates table exists (without wiping existing data)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            subject TEXT NOT NULL,
            created_at TEXT NOT NULL,
            issued INTEGER DEFAULT 0,
            issued_at TEXT
        )
    """)

    conn.commit()
    conn.close()

