import hashlib
import os
import sqlite3
from typing import Optional, List, Dict, Any


class CacheManager:
    def __init__(self, db_path: str = "cache.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the SQLite database with cache table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_url TEXT NOT NULL,
                analysis_result TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                prompt_hash TEXT NOT NULL,
                knowledge_flags TEXT NOT NULL,
                UNIQUE(doc_url, prompt_hash, knowledge_flags)
            )
        ''')

        conn.commit()
        conn.close()

    def _generate_prompt_hash(self, prompt: str) -> str:
        """Generate hash for the prompt to track changes"""
        return hashlib.md5(prompt.encode()).hexdigest()

    def _generate_knowledge_flags(self, use_o1: bool, use_eb1: bool) -> str:
        """Generate knowledge flags string"""
        return f"O1:{str(use_o1)},EB1:{str(use_eb1)}"

    def get_cached_result(self, doc_url: str, prompt: str, use_o1: bool, use_eb1: bool) -> Optional[Dict[str, Any]]:
        """Get cached result if exists"""
        prompt_hash = self._generate_prompt_hash(prompt)
        knowledge_flags = self._generate_knowledge_flags(use_o1, use_eb1)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT analysis_result, created_at FROM cache 
            WHERE doc_url = ? AND prompt_hash = ? AND knowledge_flags = ?
            ORDER BY created_at DESC LIMIT 1
        ''', (doc_url, prompt_hash, knowledge_flags))

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'analysis_result': result[0],
                'created_at': result[1]
            }
        return None

    def save_to_cache(self, doc_url: str, analysis_result: str, prompt: str, use_o1: bool, use_eb1: bool) -> bool:
        """Save analysis result to cache"""
        prompt_hash = self._generate_prompt_hash(prompt)
        knowledge_flags = self._generate_knowledge_flags(use_o1, use_eb1)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT OR REPLACE INTO cache 
                (doc_url, analysis_result, prompt_hash, knowledge_flags)
                VALUES (?, ?, ?, ?)
            ''', (doc_url, analysis_result, prompt_hash, knowledge_flags))

            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error saving to cache: {e}")
            conn.close()
            return False

    def get_all_cached_results(self) -> List[Dict[str, Any]]:
        """Get all cached results for display"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, doc_url, analysis_result, created_at, knowledge_flags
            FROM cache 
            ORDER BY created_at DESC
        ''')

        results = []
        for row in cursor.fetchall():
            # Parse knowledge flags
            knowledge_flags = row[4]
            o1_enabled = "O1:True" in knowledge_flags
            eb1_enabled = "EB1:True" in knowledge_flags

            results.append({
                'id': row[0],
                'doc_url': row[1],
                'analysis_result': row[2],
                'created_at': row[3],
                'o1_enabled': o1_enabled,
                'eb1_enabled': eb1_enabled
            })

        conn.close()
        return results

    def delete_cache_entry(self, cache_id: int) -> bool:
        """Delete specific cache entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM cache WHERE id = ?', (cache_id,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting cache entry: {e}")
            conn.close()
            return False

    def clear_all_cache(self) -> bool:
        """Clear all cache entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM cache')
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing cache: {e}")
            conn.close()
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM cache')
        total_entries = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT doc_url) FROM cache')
        unique_urls = cursor.fetchone()[0]

        # Get database file size
        try:
            db_size = os.path.getsize(self.db_path)
            db_size_mb = db_size / (1024 * 1024)
        except:
            db_size_mb = 0

        conn.close()

        return {
            'total_entries': total_entries,
            'unique_urls': unique_urls,
            'db_size_mb': round(db_size_mb, 2)
        }
