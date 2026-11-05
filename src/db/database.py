import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Any, List, Tuple, Dict, Optional
from src.config import settings


def get_db_path() -> Path:
    settings.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return settings.DATABASE_PATH


def create_connection(db_path: Optional[Path] = None, read_only: bool = False) -> sqlite3.Connection:
    target_path = str(db_path or get_db_path())
    uri = f"file:{target_path}?mode=ro" if read_only else target_path

    conn = sqlite3.connect(
        uri,
        uri=read_only,
        timeout=settings.QUERY_TIMEOUT_SECONDS,
        check_same_thread=False
    )
    conn.row_factory = sqlite3.Row

    # Performance optimizations
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA cache_size = -64000;")  # 64MB memory cache
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA mmap_size = 268435456;")  # 256MB memory-mapped I/O

    # Register Unicode-aware lowercase function for robust Cyrillic search
    conn.create_function("lower", 1, lambda s: s.lower() if s is not None else None, deterministic=True)

    return conn


@contextmanager
def get_db(read_only: bool = True) -> Generator[sqlite3.Connection, None, None]:
    conn = create_connection(read_only=read_only)
    try:
        yield conn
    finally:
        conn.close()


def execute_query(
    sql: str,
    params: Tuple[Any, ...] = (),
    read_only: bool = True
) -> List[Dict[str, Any]]:
    with get_db(read_only=read_only) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def execute_scalar(
    sql: str,
    params: Tuple[Any, ...] = ()
) -> Any:
    with get_db(read_only=True) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        return row[0] if row else None
