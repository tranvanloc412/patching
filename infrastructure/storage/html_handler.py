"""HTML handler for generating and managing HTML reports."""

import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from datetime import datetime
import html
import json

from .file_storage import FileStorage


class HTMLHandler:
    """Handler for HTML file operations and report generation."""
    
    def __init__(self, file_storage: Optional[FileStorage] = None):
        self.file_storage = file_storage or FileStorage()
        self.logger = logging.getLogger(__name__)
    
    def generate_report_html(
        self,
        file_path: str,
        title: str,
        data: Dict[str, Any],
        template: Optional[str] = None,
        css_style: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> bool:
        """Generate HTML report from data."""
        try:
            if template:
                html_content = self._apply_template(template, title, data)
            else:
                html_content = self._generate_default_report(title, data, css_style)
            
            # Write to file
            self.file_storage.write_file(file_path, html_content, encoding=encoding)
            
            self.logger.info(f"HTML report generated: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate HTML report {file_path}: {str(e)}")
            raise
    
    def generate_table_html(
        self,
        file_path: str,
        title: str,
        headers: List[str],
        rows: List[List[Any]],
        css_style: Optional[str] = None,
        encoding: str = 'utf-8'
    ) -> bool:
        """Generate HTML table from headers and rows."""
        try:
            html_content = self._generate_table_html(title, headers, rows, css_style)
            
            # Write to file
            self.file_storage.write_file(file_path, html_content, encoding=encoding)
            
            self.logger.info(f"HTML table generated: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate HTML table {file_path}: {str(e)}")
            raise
    
    def generate_workflow_report(
        self,
        file_path: str,
        workflow_data: Dict[str, Any],
        encoding: str = 'utf-8'
    ) -> bool:
        """Generate workflow-specific HTML report."""
        try:
            html_content = self._generate_workflow_html(workflow_data)
            
            # Write to file
            self.file_storage.write_file(file_path, html_content, encoding=encoding)
            
            self.logger.info(f"Workflow HTML report generated: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to generate workflow HTML report {file_path}: {str(e)}")
            raise
    
    def read_html(
        self,
        file_path: str,
        encoding: str = 'utf-8'
    ) -> str:
        """Read HTML file content."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"HTML file not found: {file_path}")
            
            content = self.file_storage.read_file(file_path, encoding=encoding)
            
            self.logger.info(f"HTML file read: {file_path}")
            return content
            
        except Exception as e:
            self.logger.error(f"Failed to read HTML file {file_path}: {str(e)}")
            raise
    
    def update_html_content(
        self,
        file_path: str,
        updates: Dict[str, str],
        encoding: str = 'utf-8'
    ) -> bool:
        """Update HTML content by replacing placeholders."""
        try:
            content = self.read_html(file_path, encoding=encoding)
            
            # Replace placeholders
            for placeholder, value in updates.items():
                content = content.replace(f"{{{{{placeholder}}}}}", str(value))
            
            # Write back to file
            self.file_storage.write_file(file_path, content, encoding=encoding)
            
            self.logger.info(f"HTML content updated: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update HTML content {file_path}: {str(e)}")
            raise
    
    def validate_html(
        self,
        file_path: str,
        encoding: str = 'utf-8'
    ) -> Dict[str, Any]:
        """Validate HTML file structure."""
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
            
            # Read content
            try:
                content = self.read_html(file_path, encoding=encoding)
                validation_result['info']['content_length'] = len(content)
                
                # Basic HTML structure checks
                content_lower = content.lower()
                
                # Check for basic HTML structure
                if '<html' not in content_lower:
                    validation_result['warnings'].append("Missing <html> tag")
                
                if '<head' not in content_lower:
                    validation_result['warnings'].append("Missing <head> section")
                
                if '<body' not in content_lower:
                    validation_result['warnings'].append("Missing <body> section")
                
                if '<title' not in content_lower:
                    validation_result['warnings'].append("Missing <title> tag")
                
                # Check for unclosed tags (basic check)
                open_tags = content_lower.count('<') - content_lower.count('</')
                if open_tags > 10:  # Allow some self-closing tags
                    validation_result['warnings'].append(f"Potentially unclosed tags detected ({open_tags} more opening than closing tags)")
                
                # Check for common issues
                if '&' in content and '&amp;' not in content and '&lt;' not in content:
                    validation_result['warnings'].append("Unescaped ampersands detected")
                
                validation_result['info']['has_doctype'] = '<!doctype' in content_lower
                validation_result['info']['has_charset'] = 'charset=' in content_lower
                
            except Exception as e:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Failed to read HTML: {str(e)}")
                return validation_result
            
            # Get file info
            try:
                file_info = self.file_storage.get_file_info(file_path)
                validation_result['info']['file_size'] = file_info['size']
                validation_result['info']['modified'] = file_info['modified']
            except Exception as e:
                validation_result['warnings'].append(f"Could not get file info: {str(e)}")
            
            return validation_result
            
        except Exception as e:
            self.logger.error(f"Failed to validate HTML file {file_path}: {str(e)}")
            raise
    
    def get_html_info(self, file_path: str, encoding: str = 'utf-8') -> Dict[str, Any]:
        """Get information about an HTML file."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"HTML file not found: {file_path}")
            
            # Get file info
            file_info = self.file_storage.get_file_info(file_path)
            
            # Read and analyze content
            content = self.read_html(file_path, encoding=encoding)
            content_lower = content.lower()
            
            info = {
                'file_path': file_path,
                'file_size': file_info['size'],
                'created': file_info['created'],
                'modified': file_info['modified'],
                'encoding': encoding,
                'content_length': len(content),
                'line_count': content.count('\n') + 1,
                'has_html_tag': '<html' in content_lower,
                'has_head_tag': '<head' in content_lower,
                'has_body_tag': '<body' in content_lower,
                'has_title_tag': '<title' in content_lower,
                'has_doctype': '<!doctype' in content_lower,
                'has_charset': 'charset=' in content_lower
            }
            
            # Extract title if present
            title_start = content_lower.find('<title')
            if title_start != -1:
                title_start = content.find('>', title_start) + 1
                title_end = content_lower.find('</title>', title_start)
                if title_end != -1:
                    info['title'] = content[title_start:title_end].strip()
            
            return info
            
        except Exception as e:
            self.logger.error(f"Failed to get HTML info for {file_path}: {str(e)}")
            raise
    
    def _generate_default_report(self, title: str, data: Dict[str, Any], css_style: Optional[str] = None) -> str:
        """Generate default HTML report template."""
        css = css_style or self._get_default_css()
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{html.escape(title)}</h1>
            <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <main>
{self._generate_data_sections(data)}
        </main>
        
        <footer>
            <p>Report generated by Patching System</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html_content
    
    def _generate_table_html(self, title: str, headers: List[str], rows: List[List[Any]], css_style: Optional[str] = None) -> str:
        """Generate HTML table."""
        css = css_style or self._get_default_css()
        
        # Generate table headers
        header_html = "\n".join([f"                <th>{html.escape(str(header))}</th>" for header in headers])
        
        # Generate table rows
        rows_html = []
        for row in rows:
            row_cells = "\n".join([f"                <td>{html.escape(str(cell))}</td>" for cell in row])
            rows_html.append(f"            <tr>\n{row_cells}\n            </tr>")
        
        table_rows = "\n".join(rows_html)
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{html.escape(title)}</h1>
            <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <main>
            <table class="data-table">
                <thead>
                    <tr>
{header_html}
                    </tr>
                </thead>
                <tbody>
{table_rows}
                </tbody>
            </table>
        </main>
        
        <footer>
            <p>Report generated by Patching System</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html_content
    
    def _generate_workflow_html(self, workflow_data: Dict[str, Any]) -> str:
        """Generate workflow-specific HTML report."""
        title = f"Workflow Report - {workflow_data.get('workflow_id', 'Unknown')}"
        css = self._get_workflow_css()
        
        # Extract workflow information
        workflow_id = workflow_data.get('workflow_id', 'N/A')
        status = workflow_data.get('status', 'Unknown')
        start_time = workflow_data.get('start_time', 'N/A')
        end_time = workflow_data.get('end_time', 'N/A')
        duration = workflow_data.get('duration', 'N/A')
        
        # Generate phases section
        phases_html = self._generate_phases_html(workflow_data.get('phases', []))
        
        # Generate metrics section
        metrics_html = self._generate_metrics_html(workflow_data.get('metrics', {}))
        
        # Generate errors section
        errors_html = self._generate_errors_html(workflow_data.get('errors', []))
        
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
{css}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{html.escape(title)}</h1>
            <p class="timestamp">Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <main>
            <section class="workflow-summary">
                <h2>Workflow Summary</h2>
                <div class="summary-grid">
                    <div class="summary-item">
                        <label>Workflow ID:</label>
                        <span>{html.escape(str(workflow_id))}</span>
                    </div>
                    <div class="summary-item">
                        <label>Status:</label>
                        <span class="status status-{status.lower()}">{html.escape(str(status))}</span>
                    </div>
                    <div class="summary-item">
                        <label>Start Time:</label>
                        <span>{html.escape(str(start_time))}</span>
                    </div>
                    <div class="summary-item">
                        <label>End Time:</label>
                        <span>{html.escape(str(end_time))}</span>
                    </div>
                    <div class="summary-item">
                        <label>Duration:</label>
                        <span>{html.escape(str(duration))}</span>
                    </div>
                </div>
            </section>
            
{phases_html}
{metrics_html}
{errors_html}
        </main>
        
        <footer>
            <p>Report generated by Patching System</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html_content
    
    def _generate_data_sections(self, data: Dict[str, Any], level: int = 0) -> str:
        """Generate HTML sections from data dictionary."""
        sections = []
        
        for key, value in data.items():
            if isinstance(value, dict):
                sections.append(f"{'    ' * (level + 3)}<section class='data-section'>")
                sections.append(f"{'    ' * (level + 4)}<h{min(level + 2, 6)}>{html.escape(str(key))}</h{min(level + 2, 6)}>")
                sections.append(self._generate_data_sections(value, level + 1))
                sections.append(f"{'    ' * (level + 3)}</section>")
            elif isinstance(value, list):
                sections.append(f"{'    ' * (level + 3)}<section class='data-section'>")
                sections.append(f"{'    ' * (level + 4)}<h{min(level + 2, 6)}>{html.escape(str(key))}</h{min(level + 2, 6)}>")
                sections.append(f"{'    ' * (level + 4)}<ul class='data-list'>")
                for item in value:
                    if isinstance(item, (dict, list)):
                        sections.append(f"{'    ' * (level + 5)}<li><pre>{html.escape(json.dumps(item, indent=2))}</pre></li>")
                    else:
                        sections.append(f"{'    ' * (level + 5)}<li>{html.escape(str(item))}</li>")
                sections.append(f"{'    ' * (level + 4)}</ul>")
                sections.append(f"{'    ' * (level + 3)}</section>")
            else:
                sections.append(f"{'    ' * (level + 3)}<div class='data-item'>")
                sections.append(f"{'    ' * (level + 4)}<label>{html.escape(str(key))}:</label>")
                sections.append(f"{'    ' * (level + 4)}<span>{html.escape(str(value))}</span>")
                sections.append(f"{'    ' * (level + 3)}</div>")
        
        return "\n".join(sections)
    
    def _generate_phases_html(self, phases: List[Dict[str, Any]]) -> str:
        """Generate HTML for workflow phases."""
        if not phases:
            return ""
        
        phases_html = ["            <section class='phases-section'>"]
        phases_html.append("                <h2>Workflow Phases</h2>")
        
        for phase in phases:
            phase_name = phase.get('name', 'Unknown')
            phase_status = phase.get('status', 'Unknown')
            phase_duration = phase.get('duration', 'N/A')
            
            phases_html.append(f"                <div class='phase-item'>")
            phases_html.append(f"                    <h3>{html.escape(str(phase_name))}</h3>")
            phases_html.append(f"                    <div class='phase-details'>")
            phases_html.append(f"                        <span class='status status-{phase_status.lower()}'>{html.escape(str(phase_status))}</span>")
            phases_html.append(f"                        <span class='duration'>Duration: {html.escape(str(phase_duration))}</span>")
            phases_html.append(f"                    </div>")
            phases_html.append(f"                </div>")
        
        phases_html.append("            </section>")
        return "\n".join(phases_html)
    
    def _generate_metrics_html(self, metrics: Dict[str, Any]) -> str:
        """Generate HTML for metrics."""
        if not metrics:
            return ""
        
        metrics_html = ["            <section class='metrics-section'>"]
        metrics_html.append("                <h2>Metrics</h2>")
        metrics_html.append("                <div class='metrics-grid'>")
        
        for key, value in metrics.items():
            metrics_html.append(f"                    <div class='metric-item'>")
            metrics_html.append(f"                        <label>{html.escape(str(key))}:</label>")
            metrics_html.append(f"                        <span>{html.escape(str(value))}</span>")
            metrics_html.append(f"                    </div>")
        
        metrics_html.append("                </div>")
        metrics_html.append("            </section>")
        return "\n".join(metrics_html)
    
    def _generate_errors_html(self, errors: List[Dict[str, Any]]) -> str:
        """Generate HTML for errors."""
        if not errors:
            return ""
        
        errors_html = ["            <section class='errors-section'>"]
        errors_html.append("                <h2>Errors</h2>")
        
        for error in errors:
            error_message = error.get('message', 'Unknown error')
            error_phase = error.get('phase', 'Unknown')
            error_timestamp = error.get('timestamp', 'N/A')
            
            errors_html.append(f"                <div class='error-item'>")
            errors_html.append(f"                    <div class='error-header'>")
            errors_html.append(f"                        <span class='error-phase'>{html.escape(str(error_phase))}</span>")
            errors_html.append(f"                        <span class='error-timestamp'>{html.escape(str(error_timestamp))}</span>")
            errors_html.append(f"                    </div>")
            errors_html.append(f"                    <div class='error-message'>{html.escape(str(error_message))}</div>")
            errors_html.append(f"                </div>")
        
        errors_html.append("            </section>")
        return "\n".join(errors_html)
    
    def _get_default_css(self) -> str:
        """Get default CSS styles."""
        return """        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background-color: #f5f5f5;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: white;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        
        header {
            border-bottom: 2px solid #007acc;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        
        h1 {
            color: #007acc;
            margin: 0;
            font-size: 2.5em;
        }
        
        .timestamp {
            color: #666;
            font-style: italic;
            margin: 10px 0 0 0;
        }
        
        .data-section {
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #fafafa;
        }
        
        .data-item {
            margin: 10px 0;
            display: flex;
            align-items: center;
        }
        
        .data-item label {
            font-weight: bold;
            margin-right: 10px;
            min-width: 150px;
        }
        
        .data-list {
            margin: 10px 0;
            padding-left: 20px;
        }
        
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        
        .data-table th,
        .data-table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }
        
        .data-table th {
            background-color: #007acc;
            color: white;
            font-weight: bold;
        }
        
        .data-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        
        .data-table tr:hover {
            background-color: #f5f5f5;
        }
        
        footer {
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
        }
        
        pre {
            background-color: #f4f4f4;
            padding: 10px;
            border-radius: 3px;
            overflow-x: auto;
        }"""
    
    def _get_workflow_css(self) -> str:
        """Get workflow-specific CSS styles."""
        return self._get_default_css() + """        
        .workflow-summary {
            background-color: #e8f4fd;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .summary-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background-color: white;
            border-radius: 5px;
            border: 1px solid #ddd;
        }
        
        .summary-item label {
            font-weight: bold;
            color: #555;
        }
        
        .status {
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.8em;
        }
        
        .status-completed {
            background-color: #d4edda;
            color: #155724;
        }
        
        .status-running {
            background-color: #fff3cd;
            color: #856404;
        }
        
        .status-failed {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .status-pending {
            background-color: #e2e3e5;
            color: #383d41;
        }
        
        .phases-section,
        .metrics-section,
        .errors-section {
            margin: 30px 0;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 8px;
        }
        
        .phase-item {
            margin: 15px 0;
            padding: 15px;
            background-color: #f8f9fa;
            border-radius: 5px;
            border-left: 4px solid #007acc;
        }
        
        .phase-details {
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .metric-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background-color: #f8f9fa;
            border-radius: 5px;
            border: 1px solid #e9ecef;
        }
        
        .error-item {
            margin: 15px 0;
            padding: 15px;
            background-color: #fff5f5;
            border: 1px solid #fed7d7;
            border-radius: 5px;
            border-left: 4px solid #e53e3e;
        }
        
        .error-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-weight: bold;
        }
        
        .error-phase {
            color: #e53e3e;
        }
        
        .error-timestamp {
            color: #666;
            font-size: 0.9em;
        }
        
        .error-message {
            color: #333;
            font-family: monospace;
            background-color: #f7fafc;
            padding: 10px;
            border-radius: 3px;
        }"""
    
    def _apply_template(self, template: str, title: str, data: Dict[str, Any]) -> str:
        """Apply custom template with data."""
        # Simple template replacement
        template = template.replace('{{title}}', html.escape(title))
        template = template.replace('{{timestamp}}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        # Replace data placeholders
        for key, value in data.items():
            placeholder = f'{{{{{key}}}}}'
            if isinstance(value, (dict, list)):
                template = template.replace(placeholder, html.escape(json.dumps(value, indent=2)))
            else:
                template = template.replace(placeholder, html.escape(str(value)))
        
        return template