import json
import logging
import os
import sqlite3
from typing import Optional, List, Dict, Any


class DatabaseManager:
    def __init__(self, db_path: str = "analysis_history.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the SQLite database with analysis history table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_url TEXT NOT NULL,
                file_name TEXT NOT NULL,
                user_email TEXT NOT NULL,
                check_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                check_result TEXT NOT NULL
            )
        ''')

        conn.commit()
        conn.close()

    def save_analysis_result(self, file_url: str, file_name: str, user_email: str,
                             analysis_result: Dict[str, Any]) -> bool:
        """Save analysis result to database"""
        logging.info(f"Attempting to save analysis: file_url={file_url}, file_name={file_name}, user_email={user_email}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Convert analysis result to JSON string
            result_json = json.dumps(analysis_result, ensure_ascii=False, indent=2)
            
            logging.info(f"Analysis result JSON length: {len(result_json)}")

            cursor.execute('''
                INSERT INTO analysis_history 
                (file_url, file_name, user_email, check_result)
                VALUES (?, ?, ?, ?)
            ''', (file_url, file_name, user_email, result_json))

            conn.commit()
            logging.info("Analysis saved to database successfully")
            conn.close()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error saving analysis result: {e}")
            conn.close()
            return False
        except Exception as e:
            logging.error(f"Unexpected error saving analysis result: {e}")
            conn.close()
            return False

    def get_analysis_by_file(self, file_url: str, user_email: str) -> Optional[Dict[str, Any]]:
        """Get latest analysis result for specific file and user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, file_name, check_result, check_timestamp FROM analysis_history 
            WHERE file_url = ? AND user_email = ?
            ORDER BY check_timestamp DESC LIMIT 1
        ''', (file_url, user_email))

        result = cursor.fetchone()
        conn.close()

        if result:
            try:
                check_result = json.loads(result[2])
                return {
                    'id': result[0],
                    'file_name': result[1],
                    'check_result': check_result,
                    'check_timestamp': result[3]
                }
            except json.JSONDecodeError:
                print(f"Error decoding JSON for analysis ID {result[0]}")
                return None
        return None

    def get_all_analysis_history(self, user_email: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all analysis history, optionally filtered by user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if user_email:
            cursor.execute('''
                SELECT id, file_url, file_name, user_email, check_timestamp, check_result
                FROM analysis_history 
                WHERE user_email = ?
                ORDER BY check_timestamp DESC
            ''', (user_email,))
        else:
            cursor.execute('''
                SELECT id, file_url, file_name, user_email, check_timestamp, check_result
                FROM analysis_history 
                ORDER BY check_timestamp DESC
            ''')

        results = []
        for row in cursor.fetchall():
            try:
                check_result = json.loads(row[5])
                results.append({
                    'id': row[0],
                    'file_url': row[1],
                    'file_name': row[2],
                    'user_email': row[3],
                    'check_timestamp': row[4],
                    'check_result': check_result
                })
            except json.JSONDecodeError:
                print(f"Error decoding JSON for analysis ID {row[0]}")
                continue

        conn.close()
        return results

    def get_user_analysis_history(self, user_email: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get analysis history for specific user with limit"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, file_url, file_name, check_timestamp, check_result
            FROM analysis_history 
            WHERE user_email = ?
            ORDER BY check_timestamp DESC
            LIMIT ?
        ''', (user_email, limit))

        results = []
        for row in cursor.fetchall():
            try:
                check_result = json.loads(row[4])
                results.append({
                    'id': row[0],
                    'file_url': row[1],
                    'file_name': row[2],
                    'check_timestamp': row[3],
                    'check_result': check_result
                })
            except json.JSONDecodeError:
                print(f"Error decoding JSON for analysis ID {row[0]}")
                continue

        conn.close()
        return results

    def delete_analysis_entry(self, entry_id: int) -> bool:
        """Delete specific analysis entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM analysis_history WHERE id = ?', (entry_id,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting analysis entry: {e}")
            conn.close()
            return False

    def clear_user_history(self, user_email: str) -> bool:
        """Clear all analysis history for specific user"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM analysis_history WHERE user_email = ?', (user_email,))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing user history: {e}")
            conn.close()
            return False

    def clear_all_history(self) -> bool:
        """Clear all analysis history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM analysis_history')
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error clearing all history: {e}")
            conn.close()
            return False

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total entries
        cursor.execute('SELECT COUNT(*) FROM analysis_history')
        total_entries = cursor.fetchone()[0]

        # Unique files
        cursor.execute('SELECT COUNT(DISTINCT file_url) FROM analysis_history')
        unique_files = cursor.fetchone()[0]

        # Unique users
        cursor.execute('SELECT COUNT(DISTINCT user_email) FROM analysis_history')
        unique_users = cursor.fetchone()[0]

        # Recent activity (last 24 hours)
        cursor.execute('''
            SELECT COUNT(*) FROM analysis_history 
            WHERE datetime(check_timestamp) >= datetime('now', '-1 day')
        ''')
        recent_entries = cursor.fetchone()[0]

        # Database file size
        try:
            db_size = os.path.getsize(self.db_path)
            db_size_mb = db_size / (1024 * 1024)
        except:
            db_size_mb = 0

        conn.close()

        return {
            'total_entries': total_entries,
            'unique_files': unique_files,
            'unique_users': unique_users,
            'recent_entries_24h': recent_entries,
            'db_size_mb': round(db_size_mb, 2)
        }
