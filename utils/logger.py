"""Logging utilities for action tracking."""

import os
from datetime import datetime
from typing import Optional, Dict, Any


class ActionLogger:
    """Logger for user actions."""
    
    def __init__(self, log_dir: str = "logs", log_file: Optional[str] = None):
        """
        Initialize logger.
        
        Args:
            log_dir: Directory to store log files
            log_file: Path to log file (if None, uses date-based filename)
        """
        self.log_dir = log_dir
        self._ensure_log_dir()
        
        if log_file is None:
            # Use date-based filename: YYYY-MM-DD.log
            date_str = datetime.now().strftime("%Y-%m-%d")
            log_file = os.path.join(log_dir, f"{date_str}.log")
        
        self.log_file = log_file
    
    def _ensure_log_dir(self):
        """Create log directory if it doesn't exist."""
        if not os.path.exists(self.log_dir):
            try:
                os.makedirs(self.log_dir, exist_ok=True)
            except Exception as e:
                print(f"Warning: Failed to create log directory {self.log_dir}: {e}")
    
    def _get_log_file_for_date(self, date: Optional[datetime] = None) -> str:
        """
        Get log file path for a specific date.
        
        Args:
            date: Date to get log file for (defaults to today)
            
        Returns:
            Path to log file
        """
        if date is None:
            date = datetime.now()
        date_str = date.strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{date_str}.log")
    
    def log(self, action: str, doc_id: Optional[int] = None, 
            details: Optional[Dict[str, Any]] = None, 
            user: Optional[str] = None, 
            status: str = "success"):
        """
        Log an action.
        
        Args:
            action: Action description (e.g., "approve", "block", "save_grades")
            doc_id: Document ID (if applicable)
            details: Additional details dictionary
            user: User identifier (if available)
            status: Action status ("success", "error", "warning")
        """
        try:
            timestamp = datetime.now()
            timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Get log file for current date (may change during long-running sessions)
            log_file = self._get_log_file_for_date(timestamp)
            
            log_entry = {
                "timestamp": timestamp_str,
                "action": action,
                "status": status
            }
            
            if doc_id is not None:
                log_entry["doc_id"] = doc_id
            
            if user:
                log_entry["user"] = user
            
            if details:
                log_entry["details"] = details
            
            # Format log entry as readable text
            log_parts = [f"[{timestamp_str}]"]
            log_parts.append(f"Action: {action}")
            
            if doc_id is not None:
                log_parts.append(f"Doc ID: {doc_id}")
            
            if user:
                log_parts.append(f"User: {user}")
            
            if details:
                # Format details nicely, handling complex types
                details_list = []
                for k, v in details.items():
                    if isinstance(v, (dict, list)):
                        import json
                        v_str = json.dumps(v, ensure_ascii=False)
                        # Truncate very long JSON strings
                        if len(v_str) > 200:
                            v_str = v_str[:200] + "..."
                        details_list.append(f"{k}={v_str}")
                    else:
                        details_list.append(f"{k}={v}")
                details_str = ", ".join(details_list)
                log_parts.append(f"Details: {details_str}")
            
            log_parts.append(f"Status: {status}")
            
            log_line = " | ".join(log_parts) + "\n"
            
            # Ensure log directory exists (in case it was deleted)
            self._ensure_log_dir()
            
            # Append to log file
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
        
        except Exception as e:
            # Silently fail - don't break the application if logging fails
            print(f"Warning: Failed to write to log file: {e}")


# Global logger instance
_logger_instance: Optional[ActionLogger] = None


def get_logger() -> ActionLogger:
    """Get global logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ActionLogger(log_dir="logs")
    return _logger_instance


def log_action(action: str, doc_id: Optional[int] = None, 
               details: Optional[Dict[str, Any]] = None, 
               user: Optional[str] = None, 
               status: str = "success"):
    """
    Convenience function to log an action.
    
    Args:
        action: Action description
        doc_id: Document ID (if applicable)
        details: Additional details dictionary
        user: User identifier (if available)
        status: Action status ("success", "error", "warning")
    """
    logger = get_logger()
    logger.log(action, doc_id, details, user, status)
