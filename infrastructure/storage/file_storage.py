"""File storage handler for basic file operations."""

import os
import shutil
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path


class FileStorage:
    """File storage handler for managing files and directories."""
    
    def __init__(self, base_path: Optional[str] = None):
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.logger = logging.getLogger(__name__)
        
        # Ensure base path exists
        self.ensure_directory_exists(str(self.base_path))
    
    def ensure_directory_exists(self, directory_path: str) -> bool:
        """Ensure directory exists, create if it doesn't."""
        try:
            path = Path(directory_path)
            path.mkdir(parents=True, exist_ok=True)
            
            self.logger.debug(f"Directory ensured: {directory_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create directory {directory_path}: {str(e)}")
            raise
    
    def write_file(self, file_path: str, content: str, encoding: str = 'utf-8') -> bool:
        """Write content to a file."""
        try:
            path = Path(file_path)
            
            # Ensure parent directory exists
            self.ensure_directory_exists(str(path.parent))
            
            # Write content
            with open(path, 'w', encoding=encoding) as f:
                f.write(content)
            
            self.logger.debug(f"File written: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write file {file_path}: {str(e)}")
            raise
    
    def read_file(self, file_path: str, encoding: str = 'utf-8') -> str:
        """Read content from a file."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            
            self.logger.debug(f"File read: {file_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to read file {file_path}: {str(e)}")
            raise
    
    def write_binary_file(self, file_path: str, content: bytes) -> bool:
        """Write binary content to a file."""
        try:
            path = Path(file_path)
            
            # Ensure parent directory exists
            self.ensure_directory_exists(str(path.parent))
            
            # Write binary content
            with open(path, 'wb') as f:
                f.write(content)
            
            self.logger.debug(f"Binary file written: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write binary file {file_path}: {str(e)}")
            raise
    
    def read_binary_file(self, file_path: str) -> bytes:
        """Read binary content from a file."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            with open(path, 'rb') as f:
                content = f.read()
            
            self.logger.debug(f"Binary file read: {file_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to read binary file {file_path}: {str(e)}")
            raise
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists."""
        return Path(file_path).exists()
    
    def directory_exists(self, directory_path: str) -> bool:
        """Check if directory exists."""
        return Path(directory_path).is_dir()
    
    def delete_file(self, file_path: str) -> bool:
        """Delete a file."""
        try:
            path = Path(file_path)
            
            if path.exists():
                path.unlink()
                self.logger.debug(f"File deleted: {file_path}")
                return True
            else:
                self.logger.warning(f"File not found for deletion: {file_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to delete file {file_path}: {str(e)}")
            raise
    
    def delete_directory(self, directory_path: str, recursive: bool = False) -> bool:
        """Delete a directory."""
        try:
            path = Path(directory_path)
            
            if path.exists():
                if recursive:
                    shutil.rmtree(path)
                else:
                    path.rmdir()  # Only works if directory is empty
                
                self.logger.debug(f"Directory deleted: {directory_path}")
                return True
            else:
                self.logger.warning(f"Directory not found for deletion: {directory_path}")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to delete directory {directory_path}: {str(e)}")
            raise
    
    def copy_file(self, source_path: str, destination_path: str) -> bool:
        """Copy a file."""
        try:
            src = Path(source_path)
            dst = Path(destination_path)
            
            if not src.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            # Ensure destination directory exists
            self.ensure_directory_exists(str(dst.parent))
            
            # Copy file
            shutil.copy2(src, dst)
            
            self.logger.debug(f"File copied: {source_path} -> {destination_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to copy file {source_path} to {destination_path}: {str(e)}")
            raise
    
    def move_file(self, source_path: str, destination_path: str) -> bool:
        """Move a file."""
        try:
            src = Path(source_path)
            dst = Path(destination_path)
            
            if not src.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")
            
            # Ensure destination directory exists
            self.ensure_directory_exists(str(dst.parent))
            
            # Move file
            shutil.move(str(src), str(dst))
            
            self.logger.debug(f"File moved: {source_path} -> {destination_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to move file {source_path} to {destination_path}: {str(e)}")
            raise
    
    def list_files(
        self,
        directory_path: str,
        pattern: Optional[str] = None,
        recursive: bool = False
    ) -> List[str]:
        """List files in a directory."""
        try:
            path = Path(directory_path)
            
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {directory_path}")
            
            if not path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {directory_path}")
            
            files = []
            
            if recursive:
                if pattern:
                    files = [str(p) for p in path.rglob(pattern) if p.is_file()]
                else:
                    files = [str(p) for p in path.rglob('*') if p.is_file()]
            else:
                if pattern:
                    files = [str(p) for p in path.glob(pattern) if p.is_file()]
                else:
                    files = [str(p) for p in path.iterdir() if p.is_file()]
            
            self.logger.debug(f"Found {len(files)} files in {directory_path}")
            return sorted(files)
            
        except Exception as e:
            self.logger.error(f"Failed to list files in {directory_path}: {str(e)}")
            raise
    
    def list_directories(
        self,
        directory_path: str,
        recursive: bool = False
    ) -> List[str]:
        """List directories in a directory."""
        try:
            path = Path(directory_path)
            
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {directory_path}")
            
            if not path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {directory_path}")
            
            directories = []
            
            if recursive:
                directories = [str(p) for p in path.rglob('*') if p.is_dir()]
            else:
                directories = [str(p) for p in path.iterdir() if p.is_dir()]
            
            self.logger.debug(f"Found {len(directories)} directories in {directory_path}")
            return sorted(directories)
            
        except Exception as e:
            self.logger.error(f"Failed to list directories in {directory_path}: {str(e)}")
            raise
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information."""
        try:
            path = Path(file_path)
            
            if not path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            stat = path.stat()
            
            info = {
                'path': str(path.absolute()),
                'name': path.name,
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'accessed': datetime.fromtimestamp(stat.st_atime),
                'is_file': path.is_file(),
                'is_directory': path.is_dir(),
                'is_symlink': path.is_symlink(),
                'permissions': oct(stat.st_mode)[-3:]
            }
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get file info for {file_path}: {str(e)}")
            raise
    
    def cleanup_old_files(
        self,
        directory_path: str,
        max_age_days: int,
        pattern: Optional[str] = None,
        dry_run: bool = False
    ) -> List[str]:
        """Clean up old files based on age."""
        try:
            self.logger.info(f"Cleaning up files older than {max_age_days} days in {directory_path}")
            
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            files_to_delete = []
            
            # Get list of files
            files = self.list_files(directory_path, pattern=pattern, recursive=True)
            
            for file_path in files:
                try:
                    file_info = self.get_file_info(file_path)
                    
                    if file_info['modified'] < cutoff_date:
                        files_to_delete.append(file_path)
                        
                        if not dry_run:
                            self.delete_file(file_path)
                            
                except Exception as e:
                    self.logger.warning(f"Error processing file {file_path}: {str(e)}")
            
            if dry_run:
                self.logger.info(f"Dry run: Would delete {len(files_to_delete)} files")
            else:
                self.logger.info(f"Deleted {len(files_to_delete)} old files")
            
            return files_to_delete
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old files: {str(e)}")
            raise
    
    def create_backup(
        self,
        source_path: str,
        backup_directory: str,
        timestamp_suffix: bool = True
    ) -> str:
        """Create a backup of a file or directory."""
        try:
            src = Path(source_path)
            backup_dir = Path(backup_directory)
            
            if not src.exists():
                raise FileNotFoundError(f"Source not found: {source_path}")
            
            # Ensure backup directory exists
            self.ensure_directory_exists(str(backup_dir))
            
            # Generate backup name
            backup_name = src.name
            if timestamp_suffix:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                if src.is_file():
                    stem = src.stem
                    suffix = src.suffix
                    backup_name = f"{stem}_{timestamp}{suffix}"
                else:
                    backup_name = f"{backup_name}_{timestamp}"
            
            backup_path = backup_dir / backup_name
            
            # Create backup
            if src.is_file():
                shutil.copy2(src, backup_path)
            else:
                shutil.copytree(src, backup_path)
            
            self.logger.info(f"Backup created: {source_path} -> {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Failed to create backup of {source_path}: {str(e)}")
            raise
    
    def get_directory_size(self, directory_path: str) -> int:
        """Get total size of directory in bytes."""
        try:
            path = Path(directory_path)
            
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {directory_path}")
            
            if not path.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {directory_path}")
            
            total_size = 0
            for file_path in path.rglob('*'):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
            
            return total_size
            
        except Exception as e:
            self.logger.error(f"Failed to get directory size for {directory_path}: {str(e)}")
            raise
    
    def compress_directory(self, directory_path: str, output_path: str, format: str = 'zip') -> str:
        """Compress a directory to an archive."""
        try:
            src = Path(directory_path)
            output = Path(output_path)
            
            if not src.exists():
                raise FileNotFoundError(f"Directory not found: {directory_path}")
            
            if not src.is_dir():
                raise NotADirectoryError(f"Path is not a directory: {directory_path}")
            
            # Ensure output directory exists
            self.ensure_directory_exists(str(output.parent))
            
            # Create archive
            if format.lower() == 'zip':
                archive_path = shutil.make_archive(
                    str(output.with_suffix('')),
                    'zip',
                    str(src.parent),
                    str(src.name)
                )
            elif format.lower() in ['tar', 'gztar', 'bztar', 'xztar']:
                archive_path = shutil.make_archive(
                    str(output.with_suffix('')),
                    format.lower(),
                    str(src.parent),
                    str(src.name)
                )
            else:
                raise ValueError(f"Unsupported archive format: {format}")
            
            self.logger.info(f"Directory compressed: {directory_path} -> {archive_path}")
            return archive_path
            
        except Exception as e:
            self.logger.error(f"Failed to compress directory {directory_path}: {str(e)}")
            raise
    
    def extract_archive(self, archive_path: str, extract_to: str) -> str:
        """Extract an archive to a directory."""
        try:
            archive = Path(archive_path)
            extract_dir = Path(extract_to)
            
            if not archive.exists():
                raise FileNotFoundError(f"Archive not found: {archive_path}")
            
            # Ensure extraction directory exists
            self.ensure_directory_exists(str(extract_dir))
            
            # Extract archive
            shutil.unpack_archive(str(archive), str(extract_dir))
            
            self.logger.info(f"Archive extracted: {archive_path} -> {extract_to}")
            return str(extract_dir)
            
        except Exception as e:
            self.logger.error(f"Failed to extract archive {archive_path}: {str(e)}")
            raise