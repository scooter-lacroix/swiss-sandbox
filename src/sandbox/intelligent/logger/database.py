"""
Database storage implementation for action logging with efficient indexing and retrieval.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager
from pathlib import Path

from ..types import ActionType, FileChange, CommandInfo, ErrorInfo
from .models import Action, LogQuery, LogSummary


class DatabaseActionLogger:
    """
    Database-backed action logger with efficient storage and retrieval.
    Uses SQLite with proper indexing for fast queries.
    """
    
    def __init__(self, db_path: str = None):
        """
        Initialize the database logger.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses in-memory database.
        """
        self.db_path = db_path or ":memory:"
        self._init_database()
    
    def _init_database(self):
        """Initialize the database schema with proper indexing."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Create main actions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS actions (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    details TEXT,  -- JSON string
                    session_id TEXT,
                    task_id TEXT
                )
            """)
            
            # Create file changes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS file_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    change_type TEXT NOT NULL,
                    before_content TEXT,
                    after_content TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (action_id) REFERENCES actions (id)
                )
            """)
            
            # Create command info table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS command_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL,
                    command TEXT NOT NULL,
                    working_directory TEXT NOT NULL,
                    output TEXT,
                    error_output TEXT,
                    exit_code INTEGER NOT NULL,
                    duration REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (action_id) REFERENCES actions (id)
                )
            """)
            
            # Create error info table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_id TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    stack_trace TEXT,
                    context TEXT,  -- JSON string
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (action_id) REFERENCES actions (id)
                )
            """)
            
            # Create indexes for fast queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_timestamp ON actions (timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_session_id ON actions (session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_task_id ON actions (task_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_actions_type ON actions (action_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_changes_action_id ON file_changes (action_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_command_info_action_id ON command_info (action_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_error_info_action_id ON error_info (action_id)")
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper error handling."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    def log_action(self, action_type: ActionType, description: str,
                  details: dict = None, session_id: str = None,
                  task_id: str = None) -> str:
        """Log a general action to the database."""
        action_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO actions (id, timestamp, action_type, description, details, session_id, task_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                action_id, timestamp, action_type.value, description,
                json.dumps(details) if details else None,
                session_id, task_id
            ))
            conn.commit()
        
        return action_id
    
    def log_file_change(self, file_path: str, change_type: str,
                       before_content: str = None, after_content: str = None,
                       session_id: str = None, task_id: str = None) -> str:
        """Log a file change operation to the database."""
        # Determine action type based on change type
        action_type_map = {
            "create": ActionType.FILE_CREATE,
            "modify": ActionType.FILE_MODIFY,
            "delete": ActionType.FILE_DELETE
        }
        action_type = action_type_map.get(change_type, ActionType.FILE_MODIFY)
        
        action_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert main action
            cursor.execute("""
                INSERT INTO actions (id, timestamp, action_type, description, session_id, task_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                action_id, timestamp, action_type.value,
                f"{change_type.title()} file: {file_path}",
                session_id, task_id
            ))
            
            # Insert file change details
            cursor.execute("""
                INSERT INTO file_changes (action_id, file_path, change_type, before_content, after_content, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (action_id, file_path, change_type, before_content, after_content, timestamp))
            
            conn.commit()
        
        return action_id
    
    def log_command(self, command: str, working_directory: str,
                   output: str, error_output: str, exit_code: int,
                   duration: float, session_id: str = None,
                   task_id: str = None) -> str:
        """Log a command execution to the database."""
        action_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert main action
            cursor.execute("""
                INSERT INTO actions (id, timestamp, action_type, description, session_id, task_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                action_id, timestamp, ActionType.COMMAND_EXECUTE.value,
                f"Execute command: {command}",
                session_id, task_id
            ))
            
            # Insert command details
            cursor.execute("""
                INSERT INTO command_info (action_id, command, working_directory, output, error_output, exit_code, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (action_id, command, working_directory, output, error_output, exit_code, duration, timestamp))
            
            conn.commit()
        
        return action_id
    
    def log_error(self, error_type: str, message: str, stack_trace: str = None,
                 context: dict = None, session_id: str = None,
                 task_id: str = None) -> str:
        """Log an error to the database."""
        action_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert main action
            cursor.execute("""
                INSERT INTO actions (id, timestamp, action_type, description, session_id, task_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                action_id, timestamp, ActionType.TASK_ERROR.value,
                f"Error: {message}",
                session_id, task_id
            ))
            
            # Insert error details
            cursor.execute("""
                INSERT INTO error_info (action_id, error_type, message, stack_trace, context, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (action_id, error_type, message, stack_trace, 
                  json.dumps(context) if context else None, timestamp))
            
            conn.commit()
        
        return action_id
    
    def get_actions(self, query: LogQuery) -> List[Action]:
        """Retrieve actions from database based on query parameters."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build the SQL query dynamically based on filters
            sql_parts = ["SELECT * FROM actions WHERE 1=1"]
            params = []
            
            if query.session_id:
                sql_parts.append("AND session_id = ?")
                params.append(query.session_id)
            
            if query.task_id:
                sql_parts.append("AND task_id = ?")
                params.append(query.task_id)
            
            if query.action_types:
                placeholders = ",".join("?" * len(query.action_types))
                sql_parts.append(f"AND action_type IN ({placeholders})")
                params.extend([at.value for at in query.action_types])
            
            if query.start_time:
                sql_parts.append("AND timestamp >= ?")
                params.append(query.start_time.isoformat())
            
            if query.end_time:
                sql_parts.append("AND timestamp <= ?")
                params.append(query.end_time.isoformat())
            
            # Add ordering and pagination
            sql_parts.append("ORDER BY timestamp ASC")
            
            if query.limit:
                sql_parts.append("LIMIT ?")
                params.append(query.limit)
            
            if query.offset:
                sql_parts.append("OFFSET ?")
                params.append(query.offset)
            
            sql = " ".join(sql_parts)
            cursor.execute(sql, params)
            
            actions = []
            for row in cursor.fetchall():
                action = self._row_to_action(row)
                
                # Load related data
                action.file_changes = self._get_file_changes(action.id)
                action.command_info = self._get_command_info(action.id)
                action.error_info = self._get_error_info(action.id)
                
                actions.append(action)
            
            return actions
    
    def _row_to_action(self, row) -> Action:
        """Convert a database row to an Action object."""
        return Action(
            id=row['id'],
            timestamp=datetime.fromisoformat(row['timestamp']),
            action_type=ActionType(row['action_type']),
            description=row['description'],
            details=json.loads(row['details']) if row['details'] else {},
            session_id=row['session_id'],
            task_id=row['task_id']
        )
    
    def _get_file_changes(self, action_id: str) -> List[FileChange]:
        """Get file changes for an action."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM file_changes WHERE action_id = ?
            """, (action_id,))
            
            file_changes = []
            for row in cursor.fetchall():
                file_changes.append(FileChange(
                    file_path=row['file_path'],
                    change_type=row['change_type'],
                    before_content=row['before_content'],
                    after_content=row['after_content'],
                    timestamp=datetime.fromisoformat(row['timestamp'])
                ))
            
            return file_changes
    
    def _get_command_info(self, action_id: str) -> Optional[CommandInfo]:
        """Get command info for an action."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM command_info WHERE action_id = ?
            """, (action_id,))
            
            row = cursor.fetchone()
            if row:
                return CommandInfo(
                    command=row['command'],
                    working_directory=row['working_directory'],
                    output=row['output'],
                    error_output=row['error_output'],
                    exit_code=row['exit_code'],
                    duration=row['duration'],
                    timestamp=datetime.fromisoformat(row['timestamp'])
                )
            
            return None
    
    def _get_error_info(self, action_id: str) -> Optional[ErrorInfo]:
        """Get error info for an action."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM error_info WHERE action_id = ?
            """, (action_id,))
            
            row = cursor.fetchone()
            if row:
                return ErrorInfo(
                    error_type=row['error_type'],
                    message=row['message'],
                    stack_trace=row['stack_trace'],
                    context=json.loads(row['context']) if row['context'] else {},
                    timestamp=datetime.fromisoformat(row['timestamp'])
                )
            
            return None
    
    def get_execution_history(self, session_id: str) -> List[Action]:
        """Get the complete execution history for a session."""
        query = LogQuery(session_id=session_id)
        return self.get_actions(query)
    
    def get_log_summary(self, session_id: str = None,
                       task_id: str = None) -> LogSummary:
        """Get a summary of logged actions with aggregated statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build base query for counting
            where_parts = ["1=1"]
            params = []
            
            if session_id:
                where_parts.append("session_id = ?")
                params.append(session_id)
            
            if task_id:
                where_parts.append("task_id = ?")
                params.append(task_id)
            
            where_clause = " AND ".join(where_parts)
            
            # Get total action count
            cursor.execute(f"SELECT COUNT(*) FROM actions WHERE {where_clause}", params)
            total_actions = cursor.fetchone()[0]
            
            # Get action counts by type
            cursor.execute(f"""
                SELECT action_type, COUNT(*) 
                FROM actions 
                WHERE {where_clause}
                GROUP BY action_type
            """, params)
            
            actions_by_type = {}
            for row in cursor.fetchall():
                actions_by_type[ActionType(row[0])] = row[1]
            
            # Get file modification count
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM file_changes fc
                JOIN actions a ON fc.action_id = a.id
                WHERE {where_clause}
            """, params)
            files_modified = cursor.fetchone()[0]
            
            # Get command execution count
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM command_info ci
                JOIN actions a ON ci.action_id = a.id
                WHERE {where_clause}
            """, params)
            commands_executed = cursor.fetchone()[0]
            
            # Get error count
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM error_info ei
                JOIN actions a ON ei.action_id = a.id
                WHERE {where_clause}
            """, params)
            errors_encountered = cursor.fetchone()[0]
            
            # Get time range
            cursor.execute(f"""
                SELECT MIN(timestamp), MAX(timestamp) 
                FROM actions 
                WHERE {where_clause}
            """, params)
            time_range_row = cursor.fetchone()
            time_range = None
            if time_range_row[0] and time_range_row[1]:
                time_range = (
                    datetime.fromisoformat(time_range_row[0]),
                    datetime.fromisoformat(time_range_row[1])
                )
            
            return LogSummary(
                total_actions=total_actions,
                actions_by_type=actions_by_type,
                files_modified=files_modified,
                commands_executed=commands_executed,
                errors_encountered=errors_encountered,
                time_range=time_range
            )
    
    def export_logs(self, query: LogQuery, format: str = "json") -> str:
        """Export logs in the specified format."""
        actions = self.get_actions(query)
        
        if format.lower() == "json":
            # Convert actions to dictionaries for JSON serialization
            actions_data = []
            for action in actions:
                action_dict = {
                    "id": action.id,
                    "timestamp": action.timestamp.isoformat(),
                    "action_type": action.action_type.value,
                    "description": action.description,
                    "details": action.details,
                    "session_id": action.session_id,
                    "task_id": action.task_id
                }
                
                if action.file_changes:
                    action_dict["file_changes"] = [
                        {
                            "file_path": fc.file_path,
                            "change_type": fc.change_type,
                            "before_content": fc.before_content,
                            "after_content": fc.after_content,
                            "timestamp": fc.timestamp.isoformat()
                        }
                        for fc in action.file_changes
                    ]
                
                if action.command_info:
                    action_dict["command_info"] = {
                        "command": action.command_info.command,
                        "working_directory": action.command_info.working_directory,
                        "output": action.command_info.output,
                        "error_output": action.command_info.error_output,
                        "exit_code": action.command_info.exit_code,
                        "duration": action.command_info.duration,
                        "timestamp": action.command_info.timestamp.isoformat()
                    }
                
                if action.error_info:
                    action_dict["error_info"] = {
                        "error_type": action.error_info.error_type,
                        "message": action.error_info.message,
                        "stack_trace": action.error_info.stack_trace,
                        "context": action.error_info.context,
                        "timestamp": action.error_info.timestamp.isoformat()
                    }
                
                actions_data.append(action_dict)
            
            return json.dumps(actions_data, indent=2)
        
        elif format.lower() == "csv":
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                "id", "timestamp", "action_type", "description", "session_id", "task_id",
                "file_path", "change_type", "command", "exit_code", "error_type", "error_message"
            ])
            
            # Write data rows
            for action in actions:
                base_row = [
                    action.id, action.timestamp.isoformat(), action.action_type.value,
                    action.description, action.session_id, action.task_id
                ]
                
                if action.file_changes:
                    for fc in action.file_changes:
                        row = base_row + [fc.file_path, fc.change_type, "", "", "", ""]
                        writer.writerow(row)
                elif action.command_info:
                    row = base_row + ["", "", action.command_info.command, 
                                    action.command_info.exit_code, "", ""]
                    writer.writerow(row)
                elif action.error_info:
                    row = base_row + ["", "", "", "", action.error_info.error_type, 
                                    action.error_info.message]
                    writer.writerow(row)
                else:
                    row = base_row + ["", "", "", "", "", ""]
                    writer.writerow(row)
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def clear_logs(self, session_id: str = None, before_date: str = None) -> int:
        """Clear logs based on criteria."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Count logs to be deleted
            count_sql_parts = ["SELECT COUNT(*) FROM actions WHERE 1=1"]
            params = []
            
            if session_id:
                count_sql_parts.append("AND session_id = ?")
                params.append(session_id)
            
            if before_date:
                count_sql_parts.append("AND timestamp < ?")
                params.append(before_date)
            
            count_sql = " ".join(count_sql_parts)
            cursor.execute(count_sql, params)
            count_to_delete = cursor.fetchone()[0]
            
            # Delete related records first (foreign key constraints)
            delete_sql_parts = ["DELETE FROM actions WHERE 1=1"]
            delete_params = []
            
            if session_id:
                delete_sql_parts.append("AND session_id = ?")
                delete_params.append(session_id)
            
            if before_date:
                delete_sql_parts.append("AND timestamp < ?")
                delete_params.append(before_date)
            
            delete_sql = " ".join(delete_sql_parts)
            
            # SQLite will handle cascading deletes if we set up foreign keys properly
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.execute(delete_sql, delete_params)
            
            conn.commit()
            
            return count_to_delete
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for performance monitoring."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Table row counts
            for table in ['actions', 'file_changes', 'command_info', 'error_info']:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]
            
            # Database size (for file-based databases)
            if self.db_path != ":memory:":
                try:
                    db_file = Path(self.db_path)
                    if db_file.exists():
                        stats["database_size_bytes"] = db_file.stat().st_size
                except Exception:
                    stats["database_size_bytes"] = 0
            
            # Index usage statistics
            cursor.execute("PRAGMA index_list(actions)")
            stats["indexes_count"] = len(cursor.fetchall())
            
            return stats