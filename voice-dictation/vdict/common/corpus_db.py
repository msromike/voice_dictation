import sqlite3
from pathlib import Path

def get_corpus_db_path() -> Path:
    return Path(__file__).parent.parent.parent.parent / "userdata" / "dictation_history_PRIVATE.db"

def get_corpus_connection() -> sqlite3.Connection:
    """
    Returns a connection to the corpus SQLite database with optimized settings.
    Caller is responsible for closing the connection.
    """
    db_path = get_corpus_db_path()
    
    # Ensure userdata exists
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    
    # WAL lets readers work while a writer holds the file.
    conn.execute("PRAGMA journal_mode=WAL;")
    
    # synchronous=NORMAL takes the write from 7.5ms to 21us.
    # It must be set on EVERY connect because it reverts to FULL on reopen.
    conn.execute("PRAGMA synchronous=NORMAL;")
    
    return conn

def init_db():
    """Creates the necessary tables if they don't exist."""
    conn = get_corpus_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT,
                end_time TEXT,
                inject_time TEXT,
                file_timestamp TEXT,
                audio_path TEXT,
                duration_sec REAL,
                sample_rate INTEGER,
                model TEXT,
                compute_device TEXT,
                compute_type TEXT,
                transcript_text TEXT,
                outcome TEXT,
                app_version TEXT,
                speaker TEXT,
                mode TEXT,
                window_title TEXT,
                process_name TEXT,
                block_id INTEGER
            )
        """)
        # trace_ptt in dev-flags.toml: one row per raw PTT or Enter down/up. tick is
        # Windows' own millisecond clock; scan is NULL for a mouse button.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ptt_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wall_time TEXT,
                tick INTEGER,
                source TEXT,
                kind TEXT,
                repeat INTEGER,
                flags INTEGER,
                scan INTEGER,
                extra INTEGER
            )
        """)
        conn.commit()
    finally:
        conn.close()
