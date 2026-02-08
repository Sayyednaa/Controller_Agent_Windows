"""
SQLite-based persistent queue manager for offline operation.
Handles queuing and retry of failed operations.
"""

import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Persistent queue manager using SQLite for offline operation.
    Supports metadata sync, upload retry, and keylog sync queues.
    """
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default to agent/data directory
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, 'data')
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, 'agent.db')
        
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Queue table for generic operations
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS queue (
                    id TEXT PRIMARY KEY,
                    queue_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    retry_count INTEGER DEFAULT 0,
                    max_retries INTEGER DEFAULT 3,
                    created_at TEXT NOT NULL,
                    next_retry_at TEXT,
                    status TEXT DEFAULT 'pending'
                )
            ''')
            
            # Config cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS config_cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            ''')
            
            # Auth token storage
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS auth (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            
            # Create indexes
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_queue_type_status 
                ON queue(queue_type, status)
            ''')
            
            conn.commit()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        return sqlite3.connect(self.db_path, timeout=10)
    
    # ==================== Queue Operations ====================
    
    def enqueue(
        self, 
        queue_type: str, 
        data: Dict[str, Any],
        priority: int = 0,
        max_retries: int = 3
    ) -> str:
        """Add an item to the queue."""
        item_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO queue (id, queue_type, data, priority, max_retries, created_at, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                ''', (item_id, queue_type, json.dumps(data), priority, max_retries, now))
                conn.commit()
        
        logger.debug(f"Enqueued item {item_id} to {queue_type}")
        return item_id
    
    def dequeue(self, queue_type: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending items from queue."""
        now = datetime.utcnow().isoformat()
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, data, retry_count 
                    FROM queue 
                    WHERE queue_type = ? 
                      AND status = 'pending'
                      AND (next_retry_at IS NULL OR next_retry_at <= ?)
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                ''', (queue_type, now, limit))
                
                items = []
                for row in cursor.fetchall():
                    items.append({
                        'id': row[0],
                        'data': json.loads(row[1]),
                        'retry_count': row[2]
                    })
                
                return items
    
    def mark_completed(self, item_id: str):
        """Mark a queue item as completed and remove it."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM queue WHERE id = ?', (item_id,))
                conn.commit()
        
        logger.debug(f"Completed and removed queue item {item_id}")
    
    def mark_failed(self, item_id: str, delay_seconds: int = 60):
        """Mark a queue item as failed and schedule retry."""
        from datetime import timedelta
        next_retry = (datetime.utcnow() + timedelta(seconds=delay_seconds)).isoformat()
        
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if max retries exceeded
                cursor.execute(
                    'SELECT retry_count, max_retries FROM queue WHERE id = ?', 
                    (item_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    retry_count, max_retries = row
                    if retry_count >= max_retries:
                        # Max retries exceeded, mark as dead
                        cursor.execute(
                            "UPDATE queue SET status = 'dead' WHERE id = ?",
                            (item_id,)
                        )
                        logger.warning(f"Queue item {item_id} exceeded max retries")
                    else:
                        # Schedule retry with exponential backoff
                        new_delay = delay_seconds * (2 ** retry_count)
                        next_retry = (datetime.utcnow() + timedelta(seconds=new_delay)).isoformat()
                        cursor.execute('''
                            UPDATE queue 
                            SET retry_count = retry_count + 1, next_retry_at = ?
                            WHERE id = ?
                        ''', (next_retry, item_id))
                        logger.debug(f"Scheduled retry for {item_id} at {next_retry}")
                
                conn.commit()
    
    def get_queue_stats(self, queue_type: str = None) -> Dict[str, int]:
        """Get queue statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if queue_type:
                cursor.execute('''
                    SELECT status, COUNT(*) 
                    FROM queue 
                    WHERE queue_type = ?
                    GROUP BY status
                ''', (queue_type,))
            else:
                cursor.execute('''
                    SELECT status, COUNT(*) 
                    FROM queue 
                    GROUP BY status
                ''')
            
            stats = dict(cursor.fetchall())
            return stats
    
    # ==================== Config Cache Operations ====================
    
    def get_cached_config(self) -> Optional[Dict[str, Any]]:
        """Get cached configuration."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM config_cache WHERE key = 'device_config'")
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    
    def set_cached_config(self, config: Dict[str, Any]):
        """Cache device configuration."""
        now = datetime.utcnow().isoformat()
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO config_cache (key, value, updated_at)
                    VALUES ('device_config', ?, ?)
                ''', (json.dumps(config), now))
                conn.commit()
    
    # ==================== Auth Token Operations ====================
    
    def get_auth_token(self) -> Optional[str]:
        """Get stored auth token."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM auth WHERE key = 'token'")
            row = cursor.fetchone()
            return row[0] if row else None
    
    def set_auth_token(self, token: str):
        """Store auth token."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO auth (key, value)
                    VALUES ('token', ?)
                ''', (token,))
                conn.commit()
    
    def get_device_id(self) -> Optional[str]:
        """Get stored device ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM auth WHERE key = 'device_id'")
            row = cursor.fetchone()
            return row[0] if row else None
    
    def set_device_id(self, device_id: str):
        """Store device ID."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO auth (key, value)
                    VALUES ('device_id', ?)
                ''', (device_id,))
                conn.commit()


# Singleton instance
_queue_manager: Optional[QueueManager] = None


def get_queue_manager(db_path: str = None) -> QueueManager:
    """Get the singleton queue manager instance."""
    global _queue_manager
    if _queue_manager is None:
        _queue_manager = QueueManager(db_path)
    return _queue_manager
