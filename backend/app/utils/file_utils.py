# ai-report-generator/backend/app/utils/file_utils.py
import os
import shutil
import logging
from typing import List
from pathlib import Path

logger = logging.getLogger(__name__)

class FileUtils:
    """Utility class for file operations."""
    
    @staticmethod
    def ensure_directory(directory_path: str) -> bool:
        """
        Ensure a directory exists, create if it doesn't.
        
        Args:
            directory_path: Path to directory
            
        Returns:
            True if directory exists or was created, False on error
        """
        try:
            Path(directory_path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            logger.error(f"Failed to create directory {directory_path}: {e}")
            return False
    
    @staticmethod
    def cleanup_file(file_path: str) -> bool:
        """
        Delete a file if it exists.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if file was deleted or doesn't exist, False on error
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    @staticmethod
    def cleanup_files(file_paths: List[str]) -> bool:
        """
        Delete multiple files.
        
        Args:
            file_paths: List of file paths to delete
            
        Returns:
            True if all files were processed successfully
        """
        success = True
        for file_path in file_paths:
            if not FileUtils.cleanup_file(file_path):
                success = False
        return success
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """
        Get file size in bytes.
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes, or 0 if file doesn't exist
        """
        try:
            return os.path.getsize(file_path)
        except Exception as e:
            logger.error(f"Failed to get file size for {file_path}: {e}")
            return 0
    
    @staticmethod
    def get_unique_filename(directory: str, base_name: str, extension: str) -> str:
        """
        Generate a unique filename in the specified directory.
        
        Args:
            directory: Target directory
            base_name: Base name for the file
            extension: File extension (including dot)
            
        Returns:
            Unique file path
        """
        counter = 1
        while True:
            if counter == 1:
                filename = f"{base_name}{extension}"
            else:
                filename = f"{base_name}_{counter}{extension}"
            
            filepath = os.path.join(directory, filename)
            if not os.path.exists(filepath):
                return filepath
            counter += 1
    
    @staticmethod
    def cleanup_old_files(directory: str, max_age_hours: int = 24):
        """
        Delete files older than specified hours.
        
        Args:
            directory: Directory to clean
            max_age_hours: Maximum age in hours
        """
        try:
            import time
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    file_age = current_time - os.path.getmtime(filepath)
                    if file_age > max_age_seconds:
                        os.remove(filepath)
                        logger.info(f"Cleaned up old file: {filepath}")
                        
        except Exception as e:
            logger.error(f"Failed to cleanup old files in {directory}: {e}")