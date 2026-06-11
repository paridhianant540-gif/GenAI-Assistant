import os
import sqlite3
import json
from contextlib import contextmanager
from typing import Generator
from app.utils.logger import get_logger

logger = get_logger("database")

# Default database path
DATABASE_PATH = os.getenv("DATABASE_PATH", "rag_store.db")

def init_db():
    """Initializes the database schema if tables do not exist."""
    logger.info(f"Initializing SQLite database at: {DATABASE_PATH}")
    with get_db_conn() as conn:
        cursor = conn.cursor()
        
        # 1. Users Table for JWT Auth
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Documents Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 3. Document Chunks Table with vector storage as JSON
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
            )
        """)
        
        # 4. Chat History Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                user_id INTEGER,
                role TEXT NOT NULL, -- 'user' or 'assistant'
                content TEXT NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)
        
        # Add index for session performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_history (session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunk_doc ON document_chunks (document_id)")
        
        conn.commit()
    logger.info("Database schemas verified and initialized successfully.")

@contextmanager
def get_db_conn() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager to yield a thread-safe connection to the SQLite database.
    Ensures the connection is always closed and transaction is committed or rolled back.
    """
    # check_same_thread=False is needed since FastAPI endpoints run on multiple threads
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # return rows as dict-like objects
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error occurred: {str(e)}")
        raise
    finally:
        conn.close()
