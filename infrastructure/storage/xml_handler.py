"""XML handler for reading and writing XML files."""

import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

from .file_storage import FileStorage


class XMLHandler:
    """Handler for XML file operations."""
    
    def __init__(self, file_storage: Optional[FileStorage] = None):
        self.file_storage = file_storage or FileStorage()
        self.logger = logging.getLogger(__name__)
    
    def write_xml(
        self,
        file_path: str,
        data: Union[Dict[str, Any], ET.Element],
        root_name: str = 'root',
        pretty_print: bool = True,
        encoding: str = 'utf-8',
        xml_declaration: bool = True
    ) -> bool:
        """Write data to XML file."""
        try:
            if isinstance(data, ET.Element):
                root = data
            else:
                # Convert dictionary to XML
                root = self._dict_to_xml(data, root_name)
            
            # Create XML string
            if pretty_print:
                # Use minidom for pretty printing
                rough_string = ET.tostring(root, encoding='unicode')
                reparsed = minidom.parseString(rough_string)
                xml_content = reparsed.toprettyxml(indent="  ", encoding=None)
                
                # Remove extra blank lines
                lines = [line for line in xml_content.split('\n') if line.strip()]
                xml_content = '\n'.join(lines)
                
                if not xml_declaration:
                    # Remove XML declaration if not wanted
                    lines = xml_content.split('\n')
                    if lines[0].startswith('<?xml'):
                        xml_content = '\n'.join(lines[1:])
            else:
                xml_content = ET.tostring(root, encoding='unicode')
                if xml_declaration:
                    xml_content = f'<?xml version="1.0" encoding="{encoding}"?>\n' + xml_content
            
            # Write to file
            self.file_storage.write_file(file_path, xml_content, encoding=encoding)
            
            self.logger.info(f"XML file written: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to write XML file {file_path}: {str(e)}")
            raise
    
    def read_xml(
        self,
        file_path: str,
        encoding: str = 'utf-8'
    ) -> ET.Element:
        """Read XML file and return root element."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"XML file not found: {file_path}")
            
            # Parse XML file
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            self.logger.info(f"XML file read: {file_path}")
            return root
            
        except ET.ParseError as e:
            self.logger.error(f"Invalid XML in file {file_path}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to read XML file {file_path}: {str(e)}")
            raise
    
    def xml_to_dict(
        self,
        file_path: str,
        encoding: str = 'utf-8'
    ) -> Dict[str, Any]:
        """Convert XML file to dictionary."""
        try:
            root = self.read_xml(file_path, encoding=encoding)
            return self._xml_to_dict(root)
            
        except Exception as e:
            self.logger.error(f"Failed to convert XML to dict {file_path}: {str(e)}")
            raise
    
    def dict_to_xml_file(
        self,
        file_path: str,
        data: Dict[str, Any],
        root_name: str = 'root',
        encoding: str = 'utf-8'
    ) -> bool:
        """Convert dictionary to XML file."""
        try:
            return self.write_xml(file_path, data, root_name, encoding=encoding)
            
        except Exception as e:
            self.logger.error(f"Failed to convert dict to XML {file_path}: {str(e)}")
            raise
    
    def find_elements(
        self,
        file_path: str,
        xpath: str,
        encoding: str = 'utf-8'
    ) -> List[ET.Element]:
        """Find elements using XPath."""
        try:
            root = self.read_xml(file_path, encoding=encoding)
            elements = root.findall(xpath)
            
            self.logger.debug(f"Found {len(elements)} elements with XPath '{xpath}'")
            return elements
            
        except Exception as e:
            self.logger.error(f"Failed to find elements in {file_path}: {str(e)}")
            raise
    
    def update_element(
        self,
        file_path: str,
        xpath: str,
        new_value: str,
        attribute: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> bool:
        """Update element value or attribute."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            elements = root.findall(xpath)
            if not elements:
                self.logger.warning(f"No elements found with XPath '{xpath}'")
                return False
            
            for element in elements:
                if attribute:
                    element.set(attribute, new_value)
                else:
                    element.text = new_value
            
            # Write back to file
            tree.write(file_path, encoding=encoding, xml_declaration=True)
            
            self.logger.info(f"Updated {len(elements)} elements in {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update XML file {file_path}: {str(e)}")
            raise
    
    def validate_xml(
        self,
        file_path: str,
        schema_path: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> Dict[str, Any]:
        """Validate XML file structure."""
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
            
            # Try to parse XML
            try:
                root = self.read_xml(file_path, encoding=encoding)
                validation_result['info']['root_tag'] = root.tag
                validation_result['info']['namespace'] = root.tag.split('}')[0][1:] if '}' in root.tag else None
                validation_result['info']['children_count'] = len(list(root))
                
                # Get all unique tags
                all_tags = set()
                for elem in root.iter():
                    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    all_tags.add(tag)
                validation_result['info']['unique_tags'] = sorted(list(all_tags))
                
            except ET.ParseError as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Invalid XML syntax: {str(e)}")
                return validation_result
            except Exception as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Failed to read XML: {str(e)}")
                return validation_result
            
            # Schema validation (if provided)
            if schema_path and self.file_storage.file_exists(schema_path):
                try:
                    # Basic schema validation would require additional libraries
                    # For now, just check if schema file exists
                    validation_result['info']['schema_provided'] = True
                    validation_result['warnings'].append("Schema validation not implemented (requires xmlschema library)")
                except Exception as e:
                    validation_result['warnings'].append(f"Schema validation error: {str(e)}")
            
            # Get file info
            try:
                file_info = self.file_storage.get_file_info(file_path)
                validation_result['info']['file_size'] = file_info['size']
                validation_result['info']['modified'] = file_info['modified']
            except Exception as e:
                validation_result['warnings'].append(f"Could not get file info: {str(e)}")
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Failed to validate XML file {file_path}: {str(e)}")
            raise
    
    def get_xml_info(self, file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Get information about an XML file."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"XML file not found: {file_path}")
            
            # Get file info
            file_info = self.file_storage.get_file_info(file_path)
            
            # Try to parse and analyze XML
            try:
                root = self.read_xml(file_path, encoding=encoding)
                
                # Count elements
                element_count = len(list(root.iter()))
                
                # Get depth
                max_depth = self._get_xml_depth(root)
                
                # Get attributes info
                total_attributes = sum(len(elem.attrib) for elem in root.iter())
                
                info = {
                    'file_path': file_path,
                    'file_size': file_info['size'],
                    'created': file_info['created'],
                    'modified': file_info['modified'],
                    'encoding': encoding,
                    'valid_xml': True,
                    'root_tag': root.tag,
                    'element_count': element_count,
                    'max_depth': max_depth,
                    'total_attributes': total_attributes
                }
                
                # Check for namespace
                if '}' in root.tag:
                    info['namespace'] = root.tag.split('}')[0][1:]
                
            except ET.ParseError as e:
                info = {
                    'file_path': file_path,
                    'file_size': file_info['size'],
                    'created': file_info['created'],
                    'modified': file_info['modified'],
                    'encoding': encoding,
                    'valid_xml': False,
                    'xml_error': str(e)
                }
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get XML info for {file_path}: {str(e)}")
            raise
    
    def pretty_print_xml(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> bool:
        """Pretty print XML file with formatting."""
        try:
            # Read XML
            root = self.read_xml(input_path, encoding=encoding)
            
            # Use input path as output if not specified
            if output_path is None:
                output_path = input_path
            
            # Write with pretty formatting
            self.write_xml(output_path, root, pretty_print=True, encoding=encoding)
            
            self.logger.info(f"XML pretty printed: {input_path} -> {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to pretty print XML file {input_path}: {str(e)}")
            raise
    
    def _dict_to_xml(self, data: Dict[str, Any], root_name: str) -> ET.Element:
        """Convert dictionary to XML element."""
        root = ET.Element(root_name)
        
        def _build_element(parent: ET.Element, data: Any, tag: str) -> None:
            if isinstance(data, dict):
                elem = ET.SubElement(parent, tag)
                for key, value in data.items():
                    _build_element(elem, value, key)
            elif isinstance(data, list):
                for item in data:
                    _build_element(parent, item, tag)
            else:
                elem = ET.SubElement(parent, tag)
                elem.text = str(data)
        
        for key, value in data.items():
            _build_element(root, value, key)
        
        return root
    
    def _xml_to_dict(self, element: ET.Element) -> Dict[str, Any]:
        """Convert XML element to dictionary."""
        result = {}
        
        # Add attributes
        if element.attrib:
            result['@attributes'] = element.attrib
        
        # Add text content
        if element.text and element.text.strip():
            if len(element) == 0:  # No children
                return element.text.strip()
            else:
                result['#text'] = element.text.strip()
        
        # Add children
        children = {}
        for child in element:
            child_data = self._xml_to_dict(child)
            
            if child.tag in children:
                # Multiple children with same tag - convert to list
                if not isinstance(children[child.tag], list):
                    children[child.tag] = [children[child.tag]]
                children[child.tag].append(child_data)
            else:
                children[child.tag] = child_data
        
        result.update(children)
        
        # If only text content, return just the text
        if len(result) == 1 and '#text' in result:
            return result['#text']
        
        return result if result else None
    
    def _get_xml_depth(self, element: ET.Element, current_depth: int = 0) -> int:
        """Get maximum depth of XML element."""
        if len(element) == 0:
            return current_depth
        
        max_child_depth = 0
        for child in element:
            child_depth = self._get_xml_depth(child, current_depth + 1)
            max_child_depth = max(max_child_depth, child_depth)
        
        return max_child_depth