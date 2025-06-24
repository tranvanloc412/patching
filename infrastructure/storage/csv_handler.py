"""CSV handler for reading and writing CSV files."""

import csv
import logging
from typing import List, Dict, Any, Optional, Union
from pathlib import Path
from io import StringIO

from .file_storage import FileStorage


class CSVHandler:
    """Handler for CSV file operations."""

    def __init__(self, file_storage: Optional[FileStorage] = None):
        self.file_storage = file_storage or FileStorage()
        self.logger = logging.getLogger(__name__)

    def write_csv(
        self,
        file_path: str,
        data: List[Dict[str, Any]],
        fieldnames: Optional[List[str]] = None,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ) -> bool:
        """Write data to CSV file."""
        try:
            if not data:
                self.logger.warning(f"No data to write to CSV: {file_path}")
                return False

            # Determine fieldnames if not provided
            if fieldnames is None:
                fieldnames = list(data[0].keys())

            # Create CSV content
            output = StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=fieldnames,
                delimiter=delimiter,
                quotechar=quotechar,
                quoting=csv.QUOTE_MINIMAL,
            )

            # Write header
            writer.writeheader()

            # Write data rows
            for row in data:
                # Filter row to only include fieldnames
                filtered_row = {k: v for k, v in row.items() if k in fieldnames}
                writer.writerow(filtered_row)

            # Write to file
            csv_content = output.getvalue()
            self.file_storage.write_file(file_path, csv_content, encoding=encoding)

            self.logger.info(f"CSV file written: {file_path} ({len(data)} rows)")
            return True

        except Exception as e:
            self.logger.error(f"Failed to write CSV file {file_path}: {str(e)}")
            raise

    def read_csv(
        self,
        file_path: str,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
        skip_header: bool = False,
    ) -> List[Dict[str, Any]]:
        """Read data from CSV file."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"CSV file not found: {file_path}")

            # Read file content
            content = self.file_storage.read_file(file_path, encoding=encoding)

            # Parse CSV
            input_stream = StringIO(content)

            if skip_header:
                # Read as list of lists
                reader = csv.reader(
                    input_stream, delimiter=delimiter, quotechar=quotechar
                )

                rows = list(reader)
                if not rows:
                    return []

                # Skip header if present
                data_rows = rows[1:] if len(rows) > 1 else []

                # Convert to list of dictionaries using first row as headers
                if rows and data_rows:
                    headers = rows[0]
                    data = []
                    for row in data_rows:
                        row_dict = {}
                        for i, value in enumerate(row):
                            header = headers[i] if i < len(headers) else f"column_{i}"
                            row_dict[header] = value
                        data.append(row_dict)
                    return data
                else:
                    return []
            else:
                # Read as dictionary
                reader = csv.DictReader(
                    input_stream, delimiter=delimiter, quotechar=quotechar
                )

                data = list(reader)

            self.logger.info(f"CSV file read: {file_path} ({len(data)} rows)")
            return data

        except Exception as e:
            self.logger.error(f"Failed to read CSV file {file_path}: {str(e)}")
            raise

    def append_to_csv(
        self,
        file_path: str,
        data: List[Dict[str, Any]],
        fieldnames: Optional[List[str]] = None,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ) -> bool:
        """Append data to existing CSV file."""
        try:
            if not data:
                self.logger.warning(f"No data to append to CSV: {file_path}")
                return False

            file_exists = self.file_storage.file_exists(file_path)

            # Determine fieldnames if not provided
            if fieldnames is None:
                if file_exists:
                    # Read existing file to get fieldnames
                    existing_data = self.read_csv(
                        file_path,
                        delimiter=delimiter,
                        quotechar=quotechar,
                        encoding=encoding,
                    )
                    if existing_data:
                        fieldnames = list(existing_data[0].keys())
                    else:
                        fieldnames = list(data[0].keys())
                else:
                    fieldnames = list(data[0].keys())

            if file_exists:
                # Append to existing file
                existing_content = self.file_storage.read_file(
                    file_path, encoding=encoding
                )

                # Create new content to append
                output = StringIO()
                writer = csv.DictWriter(
                    output,
                    fieldnames=fieldnames,
                    delimiter=delimiter,
                    quotechar=quotechar,
                    quoting=csv.QUOTE_MINIMAL,
                )

                # Write data rows (no header)
                for row in data:
                    filtered_row = {k: v for k, v in row.items() if k in fieldnames}
                    writer.writerow(filtered_row)

                # Append to existing content
                new_content = existing_content + output.getvalue()
                self.file_storage.write_file(file_path, new_content, encoding=encoding)
            else:
                # Create new file with header
                self.write_csv(
                    file_path, data, fieldnames, delimiter, quotechar, encoding
                )

            self.logger.info(f"Data appended to CSV: {file_path} ({len(data)} rows)")
            return True

        except Exception as e:
            self.logger.error(f"Failed to append to CSV file {file_path}: {str(e)}")
            raise

    def filter_csv(
        self,
        input_path: str,
        output_path: str,
        filter_func: callable,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ) -> int:
        """Filter CSV file based on a function."""
        try:
            # Read input CSV
            data = self.read_csv(
                input_path, delimiter=delimiter, quotechar=quotechar, encoding=encoding
            )

            if not data:
                self.logger.warning(f"No data to filter in CSV: {input_path}")
                return 0

            # Apply filter
            filtered_data = [row for row in data if filter_func(row)]

            # Write filtered data
            if filtered_data:
                fieldnames = list(data[0].keys())
                self.write_csv(
                    output_path,
                    filtered_data,
                    fieldnames,
                    delimiter,
                    quotechar,
                    encoding,
                )
            else:
                # Create empty file with headers
                fieldnames = list(data[0].keys())
                self.write_csv(
                    output_path, [], fieldnames, delimiter, quotechar, encoding
                )

            self.logger.info(
                f"CSV filtered: {input_path} -> {output_path} ({len(filtered_data)}/{len(data)} rows)"
            )
            return len(filtered_data)

        except Exception as e:
            self.logger.error(f"Failed to filter CSV file {input_path}: {str(e)}")
            raise

    def merge_csv_files(
        self,
        input_paths: List[str],
        output_path: str,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ) -> int:
        """Merge multiple CSV files into one."""
        try:
            all_data = []
            all_fieldnames = set()

            # Read all input files
            for input_path in input_paths:
                if self.file_storage.file_exists(input_path):
                    data = self.read_csv(
                        input_path,
                        delimiter=delimiter,
                        quotechar=quotechar,
                        encoding=encoding,
                    )
                    all_data.extend(data)

                    if data:
                        all_fieldnames.update(data[0].keys())
                else:
                    self.logger.warning(f"Input CSV file not found: {input_path}")

            if not all_data:
                self.logger.warning("No data to merge")
                return 0

            # Write merged data
            fieldnames = sorted(list(all_fieldnames))
            self.write_csv(
                output_path, all_data, fieldnames, delimiter, quotechar, encoding
            )

            self.logger.info(
                f"CSV files merged: {len(input_paths)} files -> {output_path} ({len(all_data)} rows)"
            )
            return len(all_data)

        except Exception as e:
            self.logger.error(f"Failed to merge CSV files: {str(e)}")
            raise

    def sort_csv(
        self,
        input_path: str,
        output_path: str,
        sort_key: Union[str, callable],
        reverse: bool = False,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ) -> int:
        """Sort CSV file by a key."""
        try:
            # Read input CSV
            data = self.read_csv(
                input_path, delimiter=delimiter, quotechar=quotechar, encoding=encoding
            )

            if not data:
                self.logger.warning(f"No data to sort in CSV: {input_path}")
                return 0

            # Sort data
            if isinstance(sort_key, str):
                # Sort by column name
                sorted_data = sorted(
                    data, key=lambda x: x.get(sort_key, ""), reverse=reverse
                )
            else:
                # Sort by custom function
                sorted_data = sorted(data, key=sort_key, reverse=reverse)

            # Write sorted data
            fieldnames = list(data[0].keys())
            self.write_csv(
                output_path, sorted_data, fieldnames, delimiter, quotechar, encoding
            )

            self.logger.info(
                f"CSV sorted: {input_path} -> {output_path} ({len(sorted_data)} rows)"
            )
            return len(sorted_data)

        except Exception as e:
            self.logger.error(f"Failed to sort CSV file {input_path}: {str(e)}")
            raise

    def get_csv_info(self, file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Get information about a CSV file."""
        try:
            if not self.file_storage.file_exists(file_path):
                raise FileNotFoundError(f"CSV file not found: {file_path}")

            # Read file to analyze
            content = self.file_storage.read_file(file_path, encoding=encoding)

            # Count lines
            lines = content.split("\n")
            total_lines = len(lines)
            non_empty_lines = len([line for line in lines if line.strip()])

            # Try to detect delimiter and get column info
            input_stream = StringIO(content)
            sample = input_stream.read(1024)
            input_stream.seek(0)

            # Detect delimiter
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
                quotechar = dialect.quotechar
            except:
                delimiter = ","
                quotechar = '"'

            # Get column information
            reader = csv.DictReader(
                input_stream, delimiter=delimiter, quotechar=quotechar
            )
            fieldnames = reader.fieldnames or []

            # Count data rows
            data_rows = sum(1 for row in reader)

            # Get file info
            file_info = self.file_storage.get_file_info(file_path)

            info = {
                "file_path": file_path,
                "file_size": file_info["size"],
                "created": file_info["created"],
                "modified": file_info["modified"],
                "total_lines": total_lines,
                "non_empty_lines": non_empty_lines,
                "data_rows": data_rows,
                "columns": len(fieldnames),
                "column_names": fieldnames,
                "delimiter": delimiter,
                "quote_char": quotechar,
                "encoding": encoding,
            }

            return info

        except Exception as e:
            self.logger.error(f"Failed to get CSV info for {file_path}: {str(e)}")
            raise

    def validate_csv(
        self,
        file_path: str,
        required_columns: Optional[List[str]] = None,
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ) -> Dict[str, Any]:
        """Validate CSV file structure and content."""
        try:
            validation_result = {
                "valid": True,
                "errors": [],
                "warnings": [],
                "info": {},
            }

            # Check if file exists
            if not self.file_storage.file_exists(file_path):
                validation_result["valid"] = False
                validation_result["errors"].append(f"File not found: {file_path}")
                return validation_result

            # Get CSV info
            try:
                csv_info = self.get_csv_info(file_path, encoding=encoding)
                validation_result["info"] = csv_info
            except Exception as e:
                validation_result["valid"] = False
                validation_result["errors"].append(f"Failed to read CSV: {str(e)}")
                return validation_result

            # Check if file is empty
            if csv_info["data_rows"] == 0:
                validation_result["warnings"].append("CSV file contains no data rows")

            # Check required columns
            if required_columns:
                missing_columns = set(required_columns) - set(csv_info["column_names"])
                if missing_columns:
                    validation_result["valid"] = False
                    validation_result["errors"].append(
                        f"Missing required columns: {list(missing_columns)}"
                    )

            # Try to read a sample of data to check for parsing errors
            try:
                sample_data = self.read_csv(
                    file_path,
                    delimiter=delimiter,
                    quotechar=quotechar,
                    encoding=encoding,
                )
                if sample_data:
                    # Check for inconsistent row lengths
                    expected_columns = len(csv_info["column_names"])
                    for i, row in enumerate(sample_data[:100]):  # Check first 100 rows
                        if len(row) != expected_columns:
                            validation_result["warnings"].append(
                                f"Row {i+2} has {len(row)} columns, expected {expected_columns}"
                            )
            except Exception as e:
                validation_result["valid"] = False
                validation_result["errors"].append(
                    f"Failed to parse CSV data: {str(e)}"
                )

            return validation_result

        except Exception as e:
            self.logger.error(f"Failed to validate CSV file {file_path}: {str(e)}")
            raise

    def convert_to_dict_list(
        self, data: List[List[str]], headers: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Convert list of lists to list of dictionaries."""
        try:
            if not data:
                return []

            # Use first row as headers if not provided
            if headers is None:
                if len(data) > 1:
                    headers = data[0]
                    data_rows = data[1:]
                else:
                    return []
            else:
                data_rows = data

            # Convert to dictionaries
            result = []
            for row in data_rows:
                row_dict = {}
                for i, value in enumerate(row):
                    header = headers[i] if i < len(headers) else f"column_{i}"
                    row_dict[header] = value
                result.append(row_dict)

            return result

        except Exception as e:
            self.logger.error(f"Failed to convert data to dict list: {str(e)}")
            raise
