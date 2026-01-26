"""
Excel extraction services for both .xlsx and .xls formats
"""
import io
import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
from typing import Dict, Any
from datetime import datetime


class ExcelExtractor:
    """
    Extracts text from Excel files with row and column references for easy matching.
    Supports both .xlsx and .xls formats.
    """
    
    def __init__(self):
        pass
    
    def extract_from_bytes(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Extract Excel content with row/column references from bytes.
        
        Args:
            file_bytes: Excel file content as bytes
            filename: Name of the file (for format detection)
            
        Returns:
            Dictionary containing extracted data with structure:
            {
                "filename": str,
                "sheets": [
                    {
                        "name": str,
                        "data": [
                            {
                                "cell": str,  # e.g., "A1", "B2"
                                "row": int,
                                "col": int,
                                "col_letter": str,
                                "value": str,
                                "data_type": str  # "string", "number", "date", "formula", "empty"
                            }
                        ],
                        "summary": {
                            "total_rows": int,
                            "total_cols": int,
                            "non_empty_cells": int
                        }
                    }
                ]
            }
        """
        try:
            if filename.lower().endswith(('.xlsx', '.xlsm')):
                return self._extract_xlsx(file_bytes)
            elif filename.lower().endswith('.xls'):
                return self._extract_xls(file_bytes)
            else:
                raise ValueError(f"Unsupported Excel format: {filename}")
        except Exception as e:
            raise ValueError(f"Error extracting Excel data: {str(e)}")
    
    def _extract_xlsx(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract from modern Excel format (.xlsx) using openpyxl."""
        workbook = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        
        sheets_data = []
        
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            sheet_data = {}
            non_empty_count = 0
            
            # Get actual used range
            max_row = sheet.max_row or 1
            max_col = sheet.max_column or 1
            
            # Extract only non-empty cells
            for row_idx in range(1, max_row + 1):
                for col_idx in range(1, max_col + 1):
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    value = self._get_cell_value(cell)
                    data_type = self._get_cell_type(cell)
                    
                    # Convert value to string properly
                    if value is None:
                        value_str = ""
                    elif isinstance(value, datetime):
                        value_str = value.strftime("%Y-%m-%d %H:%M:%S")
                    else:
                        value_str = str(value)
                    
                    # Skip empty cells
                    if not value_str.strip():
                        continue
                    
                    non_empty_count += 1
                    
                    # Store as key-value: cell_ref -> [value, type]
                    cell_ref = f"{get_column_letter(col_idx)}{row_idx}"
                    sheet_data[cell_ref] = [value_str, data_type]
            
            sheets_data.append({
                "name": sheet_name,
                "data": sheet_data,
                "summary": {
                    "total_rows": max_row,
                    "total_cols": max_col,
                    "non_empty_cells": non_empty_count
                }
            })
        
        return {
            "filename": "excel_file",
            "sheets": sheets_data
        }
    
    def _extract_xls(self, file_bytes: bytes) -> Dict[str, Any]:
        """Extract from legacy Excel format (.xls) using pandas."""
        excel_file = io.BytesIO(file_bytes)
        
        try:
            # Read all sheets
            xls = pd.ExcelFile(excel_file, engine='xlrd')
            sheets_data = []
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                sheet_data = {}
                non_empty_count = 0
                
                for row_idx in range(len(df)):
                    for col_idx in range(len(df.columns)):
                        value = df.iloc[row_idx, col_idx]
                        
                        # Convert value to string properly
                        if pd.isna(value):
                            value_str = ""
                        elif isinstance(value, datetime):
                            value_str = value.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            value_str = str(value)
                        
                        # Skip empty cells
                        if not value_str.strip():
                            continue
                        
                        non_empty_count += 1
                        
                        # Store as key-value: cell_ref -> [value, type]
                        cell_ref = f"{get_column_letter(col_idx + 1)}{row_idx + 1}"
                        sheet_data[cell_ref] = [value_str, self._infer_data_type(value)]
                
                sheets_data.append({
                    "name": sheet_name,
                    "data": sheet_data,
                    "summary": {
                        "total_rows": len(df),
                        "total_cols": len(df.columns),
                        "non_empty_cells": non_empty_count
                    }
                })
            
            return {
                "filename": "excel_file",
                "sheets": sheets_data
            }
            
        except Exception as e:
            raise ValueError(f"Error reading .xls file: {str(e)}")
    
    def _get_cell_value(self, cell) -> Any:
        """Get the actual value from an openpyxl cell."""
        try:
            # Handle merged cells
            if isinstance(cell, openpyxl.cell.cell.MergedCell):
                return ""
            
            return cell.value
        except Exception:
            return ""
    
    def _get_cell_type(self, cell) -> str:
        """Determine the data type of a cell."""
        try:
            # Handle merged cells
            if isinstance(cell, openpyxl.cell.cell.MergedCell):
                return "merged"
            
            if cell.value is None:
                return "empty"
            
            if cell.data_type == 'f':
                return "formula"
            elif cell.is_date:
                return "date"
            elif cell.data_type == 'n':
                return "number"
            elif cell.data_type == 's':
                return "string"
            elif cell.data_type == 'b':
                return "boolean"
            else:
                return "empty"
        except Exception:
            return "unknown"
    
    def extract_as_text(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract Excel content and return it in CELL-BY-CELL text format.
        
        Args:
            file_bytes: Excel file content as bytes
            filename: Name of the file (for format detection)
            
        Returns:
            Formatted text string with cell-by-cell data
        """
        from .text_extractor import clean_text
        
        excel_data = self.extract_from_bytes(file_bytes, filename)
        
        # Convert Excel data to CELL-BY-CELL FORMAT text
        all_text = []
        for sheet in excel_data["sheets"]:
            all_text.append(f"=== Sheet: {sheet['name']} ===")
            all_text.append(f"Dimensions: {sheet['summary']['total_rows']} rows × {sheet['summary']['total_cols']} cols")
            all_text.append(f"Non-empty cells: {sheet['summary']['non_empty_cells']}")
            all_text.append("")
            
            # Show ALL non-empty cells in cell-by-cell format
            non_empty_cells = [c for c in sheet['data'] if c['value'].strip()]
            
            for cell in non_empty_cells:
                value_display = cell['value'].replace('\n', '\\n')  # Show newlines
                all_text.append(f"{cell['cell']:6} = {value_display} [{cell['data_type']}]")
            
            all_text.append("")  # Add spacing between sheets
        
        return clean_text("\n".join(all_text))

    def _infer_data_type(self, value) -> str:
        """Infer data type for pandas-based extraction."""
        if pd.isna(value) or value == "":
            return "empty"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, datetime):
            return "date"
        elif isinstance(value, str):
            # Try to detect if it's a date
            try:
                pd.to_datetime(value)
                return "date"
            except:
                return "string"
        else:
            return "unknown"
