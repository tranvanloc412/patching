"""JSON handler for reading and writing JSON files."""

import json
import logging
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path

from .file_storage import FileStorage


class JSONHandler:
    """Handler for JSON file operations."""
    
    def __init__(self, file_storage: Optional[FileStorage] = None):
        self.file_storage = file_storage or FileStorage()
        self.logger = logging.getLogger(__name__)
    
    def write_json(
        self,
        file_path: str,
        data: Union[Dict[str, Any], List[Any]],
        indent: Optional[int] = 2,
        ensure_ascii: bool = False,
        sort_keys: bool = False,
        encoding: str = 'utf-8'
    ) -> bool:
        """Write data to JSON file."""
        try:
            # Convert data to JSON string
            json_content = json.dumps(
                data,
                indent=indent,
                ensure_ascii=ensure_ascii,
                sort_keys=sort_keys,
                default=self._json_serializer
            )
            
            # Write to file
            self.file_storage.write_file(file_path, json_content, encoding=encoding)
            
            self.logger.info(f"JSON file written: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write JSON file {file_path}: {str(e)}")
            raise
    
    def read_json(
        self,
        file_path: str,
        encoding: str = 'utf-8'
    ) -> Union[Dict[str, Any], List[Any]]:
        """Read data from JSON file."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"JSON file not found: {file_path}")
            
            # Read file content
            content = self.file_storage.read_file(file_path, encoding=encoding)
            
            # Parse JSON
            data = json.loads(content)
            
            self.logger.info(f"JSON file read: {file_path}")
            return data
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in file {file_path}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to read JSON file {file_path}: {str(e)}")
            raise
    
    def update_json(
        self,
        file_path: str,
        updates: Dict[str, Any],
        create_if_missing: bool = True,
        encoding: str = 'utf-8'
    ) -> bool:
        """Update existing JSON file with new data."""
        try:
            # Read existing data or create new
            if self.file_storage.file_exists(file_path):
                try:
                    data = self.read_json(file_path, encoding=encoding)
                    if not isinstance(data, dict):
                        raise ValueError(f"Cannot update non-dictionary JSON in {file_path}")
                except json.JSONDecodeError:
                    if create_if_missing:
                        data = {}
                    else:
                        raise
            else:
                if create_if_missing:
                    data = {}
                else:
                    raise FileNotFoundError(f"JSON file not found: {file_path}")
            
            # Update data
            data.update(updates)
            
            # Write updated data
            self.write_json(file_path, data, encoding=encoding)
            
            self.logger.info(f"JSON file updated: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update JSON file {file_path}: {str(e)}")
            raise
    
    def merge_json_files(
        self,
        input_paths: List[str],
        output_path: str,
        merge_strategy: str = 'update',
        encoding: str = 'utf-8'
    ) -> bool:
        """Merge multiple JSON files into one.
        
        Args:
            input_paths: List of input JSON file paths
            output_path: Output file path
            merge_strategy: 'update' (dict.update), 'deep' (deep merge), or 'list' (combine as list)
            encoding: File encoding
        """
        try:
            if merge_strategy == 'list':
                # Combine all JSON data into a list
                merged_data = []
                for input_path in input_paths:
                    if self.file_storage.file_exists(input_path):
                        data = self.read_json(input_path, encoding=encoding)
                        if isinstance(data, list):
                            merged_data.extend(data)
                        else:
                            merged_data.append(data)
                    else:
                        self.logger.warning(f"Input JSON file not found: {input_path}")
            
            else:
                # Merge dictionaries
                merged_data = {}
                for input_path in input_paths:
                    if self.file_storage.file_exists(input_path):
                        data = self.read_json(input_path, encoding=encoding)
                        if isinstance(data, dict):
                            if merge_strategy == 'deep':
                                merged_data = self._deep_merge(merged_data, data)
                            else:  # 'update'
                                merged_data.update(data)
                        else:
                            self.logger.warning(f"Skipping non-dictionary JSON: {input_path}")
                    else:
                        self.logger.warning(f"Input JSON file not found: {input_path}")
            
            # Write merged data
            self.write_json(output_path, merged_data, encoding=encoding)
            
            self.logger.info(f"JSON files merged: {len(input_paths)} files -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to merge JSON files: {str(e)}")
            raise
    
    def filter_json(
        self,
        input_path: str,
        output_path: str,
        filter_func: callable,
        encoding: str = 'utf-8'
    ) -> bool:
        """Filter JSON data based on a function."""
        try:
            # Read input JSON
            data = self.read_json(input_path, encoding=encoding)
            
            # Apply filter
            if isinstance(data, list):
                filtered_data = [item for item in data if filter_func(item)]
            elif isinstance(data, dict):
                filtered_data = {k: v for k, v in data.items() if filter_func({k: v})}
            else:
                # For other types, apply filter to the whole data
                filtered_data = data if filter_func(data) else None
            
            # Write filtered data
            self.write_json(output_path, filtered_data, encoding=encoding)
            
            self.logger.info(f"JSON filtered: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to filter JSON file {input_path}: {str(e)}")
            raise
    
    def validate_json(
        self,
        file_path: str,
        schema: Optional[Dict[str, Any]] = None,
        encoding: str = 'utf-8'
    ) -> Dict[str, Any]:
        """Validate JSON file structure and content."""
        try:
            validation_result = {
                'valid': True,
                'errors': [],
                'warnings': [],
                'info': {}
            }
            
            # Check if file exists
            if not self.file_storage.file_exists(file_path):
                validation_result['valid'] = False
                validation_result['errors'].append(f"File not found: {file_path}")
                return validation_result
            
            # Try to parse JSON
            try:
                data = self.read_json(file_path, encoding=encoding)
                validation_result['info']['data_type'] = type(data).__name__
                
                if isinstance(data, dict):
                    validation_result['info']['keys_count'] = len(data)
                    validation_result['info']['top_level_keys'] = list(data.keys())[:10]  # First 10 keys
                elif isinstance(data, list):
                    validation_result['info']['items_count'] = len(data)
                    if data:
                        validation_result['info']['first_item_type'] = type(data[0]).__name__
                
            except json.JSONDecodeError as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Invalid JSON syntax: {str(e)}")
                return validation_result
            except Exception as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Failed to read JSON: {str(e)}")
                return validation_result
            
            # Schema validation (basic)
            if schema:
                try:
                    self._validate_against_schema(data, schema, validation_result)
                except Exception as e:
                    validation_result['errors'].append(f"Schema validation error: {str(e)}")
            
            # Get file info
            try:
                file_info = self.file_storage.get_file_info(file_path)
                validation_result['info']['file_size'] = file_info['size']
                validation_result['info']['modified'] = file_info['modified']
            except Exception as e:
                validation_result['warnings'].append(f"Could not get file info: {str(e)}")
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Failed to validate JSON file {file_path}: {str(e)}")
            raise
    
    def get_json_info(self, file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Get information about a JSON file."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"JSON file not found: {file_path}")
            
            # Get file info
            file_info = self.file_storage.get_file_info(file_path)
            
            # Try to parse and analyze JSON
            try:
                data = self.read_json(file_path, encoding=encoding)
                
                info = {
                    'file_path': file_path,
                    'file_size': file_info['size'],
                    'created': file_info['created'],
                    'modified': file_info['modified'],
                    'encoding': encoding,
                    'data_type': type(data).__name__,
                    'valid_json': True
                }
                
                if isinstance(data, dict):
                    info['keys_count'] = len(data)
                    info['keys'] = list(data.keys())
                    info['nested_levels'] = self._get_max_depth(data)
                elif isinstance(data, list):
                    info['items_count'] = len(data)
                    if data:
                        info['first_item_type'] = type(data[0]).__name__
                        if isinstance(data[0], dict):
                            info['common_keys'] = self._get_common_keys(data)
                else:
                    info['value'] = str(data)[:100]  # First 100 chars
                
            except json.JSONDecodeError as e:
                info = {
                    'file_path': file_path,
                    'file_size': file_info['size'],
                    'created': file_info['created'],
                    'modified': file_info['modified'],
                    'encoding': encoding,
                    'valid_json': False,
                    'json_error': str(e)
                }
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get JSON info for {file_path}: {str(e)}")
            raise
    
    def pretty_print_json(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        indent: int = 2,
        sort_keys: bool = True,
        encoding: str = 'utf-8'
    ) -> bool:
        """Pretty print JSON file with formatting."""
        try:
            # Read JSON data
            data = self.read_json(input_path, encoding=encoding)
            
            # Use input path as output if not specified
            if output_path is None:
                output_path = input_path
            
            # Write with pretty formatting
            self.write_json(
                output_path,
                data,
                indent=indent,
                sort_keys=sort_keys,
                encoding=encoding
            )
            
            self.logger.info(f"JSON pretty printed: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to pretty print JSON file {input_path}: {str(e)}")
            raise
    
    def minify_json(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> bool:
        """Minify JSON file by removing whitespace."""
        try:
            # Read JSON data
            data = self.read_json(input_path, encoding=encoding)
            
            # Use input path as output if not specified
            if output_path is None:
                output_path = input_path
            
            # Write without formatting
            self.write_json(
                output_path,
                data,
                indent=None,
                sort_keys=False,
                encoding=encoding
            )
            
            self.logger.info(f"JSON minified: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to minify JSON file {input_path}: {str(e)}")
            raise
    
    def extract_keys(
        self,
        file_path: str,
        key_path: str,
        encoding: str = 'utf-8'
    ) -> Any:
        """Extract value from JSON using dot notation key path.
        
        Args:
            file_path: Path to JSON file
            key_path: Dot notation path (e.g., 'config.database.host')
            encoding: File encoding
        """
        try:
            data = self.read_json(file_path, encoding=encoding)
            
            # Navigate through the key path
            keys = key_path.split('.')
            current = data
            
            for key in keys:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list) and key.isdigit():
                    index = int(key)
                    if 0 <= index < len(current):
                        current = current[index]
                    else:
                        raise KeyError(f"List index {index} out of range")
                else:
                    raise KeyError(f"Key '{key}' not found in path '{key_path}'")
            
            return current
            
        except Exception as e:
            self.logger.error(f"Failed to extract key '{key_path}' from {file_path}: {str(e)}")
            raise
    
    def _json_serializer(self, obj: Any) -> str:
        """Custom JSON serializer for non-serializable objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        elif hasattr(obj, 'to_dict'):
            return obj.to_dict()
        else:
            return str(obj)
    
    def _deep_merge(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = dict1.copy()
        
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _get_max_depth(self, obj: Any, current_depth: int = 0) -> int:
        """Get maximum nesting depth of a JSON object."""
        if isinstance(obj, dict):
            if not obj:
                return current_depth
            return max(self._get_max_depth(value, current_depth + 1) for value in obj.values())
        elif isinstance(obj, list):
            if not obj:
                return current_depth
            return max(self._get_max_depth(item, current_depth + 1) for item in obj)
        else:
            return current_depth
    
    def _get_common_keys(self, data_list: List[Dict[str, Any]]) -> List[str]:
        """Get common keys from a list of dictionaries."""
        if not data_list:
            return []
        
        # Get keys from first dictionary
        common_keys = set(data_list[0].keys()) if isinstance(data_list[0], dict) else set()
        
        # Find intersection with all other dictionaries
        for item in data_list[1:]:
            if isinstance(item, dict):
                common_keys &= set(item.keys())
            else:
                common_keys = set()  # No common keys if not all items are dicts
                break
        
        return sorted(list(common_keys))
    
    def _validate_against_schema(self, data: Any, schema: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Basic schema validation (simplified)."""
        # This is a simplified schema validation
        # For production use, consider using jsonschema library
        
        if 'type' in schema:
            expected_type = schema['type']
            actual_type = type(data).__name__
            
            type_mapping = {
                'object': 'dict',
                'array': 'list',
                'string': 'str',
                'number': ['int', 'float'],
                'integer': 'int',
                'boolean': 'bool',
                'null': 'NoneType'
            }
            
            expected_python_types = type_mapping.get(expected_type, expected_type)
            
            if isinstance(expected_python_types, list):
                if actual_type not in expected_python_types:
                    result['errors'].append(f"Expected type {expected_type}, got {actual_type}")
            else:
                if actual_type != expected_python_types:
                    result['errors'].append(f"Expected type {expected_type}, got {actual_type}")
        
        if 'required' in schema and isinstance(data, dict):
            required_keys = schema['required']
            missing_keys = set(required_keys) - set(data.keys())
            if missing_keys:
                result['errors'].append(f"Missing required keys: {list(missing_keys)}")
        
        if 'properties' in schema and isinstance(data, dict):
            for key, value in data.items():
                if key in schema['properties']:
                    # Recursively validate nested objects
                    nested_result = {'errors': [], 'warnings': []}
                    self._validate_against_schema(value, schema['properties'][key], nested_result)
                    result['errors'].extend([f"{key}.{error}" for error in nested_result['errors']])
                    result['warnings'].extend([f"{key}.{warning}" for warning in nested_result['warnings']])