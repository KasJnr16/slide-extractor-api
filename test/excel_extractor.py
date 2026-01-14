import pandas as pd
import openpyxl
from openpyxl.utils import get_column_letter
import io
from typing import List, Dict, Any, Optional

class ExcelTableExtractor:
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
            sheet_data = []
            non_empty_count = 0
            
            for row_idx, row in enumerate(sheet.iter_rows(), 1):
                for col_idx, cell in enumerate(row, 1):
                    value = self._get_cell_value(cell)
                    data_type = self._get_cell_type(cell)
                    
                    if value is not None and str(value).strip():
                        non_empty_count += 1
                    
                    cell_info = {
                        "cell": f"{get_column_letter(col_idx)}{row_idx}",
                        "row": row_idx,
                        "col": col_idx,
                        "col_letter": get_column_letter(col_idx),
                        "value": str(value) if value is not None else "",
                        "data_type": data_type
                    }
                    sheet_data.append(cell_info)
            
            # Get dimensions
            max_row = sheet.max_row if sheet.max_row else 0
            max_col = sheet.max_column if sheet.max_column else 0
            
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
        # Use pandas as fallback for .xls files
        excel_file = io.BytesIO(file_bytes)
        
        try:
            # Read all sheets
            xls = pd.ExcelFile(excel_file)
            sheets_data = []
            
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
                sheet_data = []
                non_empty_count = 0
                
                for row_idx, row in df.iterrows():
                    for col_idx, value in enumerate(row, 1):
                        if pd.notna(value) and str(value).strip():
                            non_empty_count += 1
                        
                        cell_info = {
                            "cell": f"{get_column_letter(col_idx)}{row_idx + 1}",
                            "row": row_idx + 1,
                            "col": col_idx,
                            "col_letter": get_column_letter(col_idx),
                            "value": str(value) if pd.notna(value) else "",
                            "data_type": self._infer_data_type(value)
                        }
                        sheet_data.append(cell_info)
                
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
        if cell.is_date:
            return cell.value
        elif cell.data_type == 'f':  # formula
            return cell.value if cell.value is not None else ""
        else:
            return cell.value
    
    def _get_cell_type(self, cell) -> str:
        """Determine the data type of a cell."""
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
    
    def _infer_data_type(self, value) -> str:
        """Infer data type for pandas-based extraction."""
        if pd.isna(value) or value == "":
            return "empty"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, str):
            # Try to detect if it's a date
            try:
                pd.to_datetime(value)
                return "date"
            except:
                return "string"
        else:
            return "unknown"
    
    def get_table_structure(self, extracted_data: Dict[str, Any], sheet_name: str = None) -> Dict[str, Any]:
        """
        Analyze the structure of extracted data to identify tables and patterns.
        
        Args:
            extracted_data: Data from extract_from_bytes
            sheet_name: Specific sheet to analyze (optional)
            
        Returns:
            Dictionary with table structure analysis
        """
        if sheet_name:
            sheets_to_analyze = [s for s in extracted_data["sheets"] if s["name"] == sheet_name]
        else:
            sheets_to_analyze = extracted_data["sheets"]
        
        analysis = {}
        
        for sheet in sheets_to_analyze:
            sheet_name = sheet["name"]
            data = sheet["data"]
            
            # Create a grid representation
            max_row = max(item["row"] for item in data) if data else 0
            max_col = max(item["col"] for item in data) if data else 0
            
            grid = [[None for _ in range(max_col)] for _ in range(max_row)]
            
            for item in data:
                if item["value"].strip():
                    grid[item["row"] - 1][item["col"] - 1] = item
            
            # Identify potential tables (contiguous blocks of non-empty cells)
            tables = self._identify_tables(grid)
            
            analysis[sheet_name] = {
                "tables": tables,
                "total_rows": max_row,
                "total_cols": max_col,
                "non_empty_cells": sheet["summary"]["non_empty_cells"]
            }
        
        return analysis
    
    def _identify_tables(self, grid: List[List[Optional[Dict]]]) -> List[Dict[str, Any]]:
        """Identify contiguous blocks of data as tables."""
        if not grid or not grid[0]:
            return []
        
        rows = len(grid)
        cols = len(grid[0])
        visited = [[False for _ in range(cols)] for _ in range(rows)]
        tables = []
        
        for i in range(rows):
            for j in range(cols):
                if grid[i][j] is not None and not visited[i][j]:
                    # Found start of a new table
                    table_bounds = self._find_table_bounds(grid, visited, i, j)
                    if table_bounds:
                        tables.append(table_bounds)
        
        return tables
    
    def _find_table_bounds(self, grid: List[List[Optional[Dict]]], visited: List[List[bool]], 
                          start_row: int, start_col: int) -> Optional[Dict[str, Any]]:
        """Find the bounds of a contiguous table starting from a cell."""
        rows = len(grid)
        cols = len(grid[0])
        
        # Simple flood fill to find contiguous non-empty cells
        queue = [(start_row, start_col)]
        min_row, max_row = start_row, start_row
        min_col, max_col = start_col, start_col
        cells = []
        
        while queue:
            row, col = queue.pop(0)
            
            if (row < 0 or row >= rows or col < 0 or col >= cols or 
                visited[row][col] or grid[row][col] is None):
                continue
            
            visited[row][col] = True
            cells.append(grid[row][col])
            
            min_row = min(min_row, row)
            max_row = max(max_row, row)
            min_col = min(min_col, col)
            max_col = max(max_col, col)
            
            # Check adjacent cells (including diagonals for more flexible table detection)
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    queue.append((row + dr, col + dc))
        
        # Only consider it a table if it has multiple cells
        if len(cells) < 2:
            return None
        
        return {
            "start_cell": f"{get_column_letter(min_col + 1)}{min_row + 1}",
            "end_cell": f"{get_column_letter(max_col + 1)}{max_row + 1}",
            "start_row": min_row + 1,
            "end_row": max_row + 1,
            "start_col": min_col + 1,
            "end_col": max_col + 1,
            "cell_count": len(cells),
            "cells": cells
        }


# Test function
def test_excel_extractor():
    """Test the Excel extractor with sample data."""
    import os
    
    # Create a sample Excel file in memory for testing
    sample_data = {
        "Sheet1": [
            ["Name", "Age", "City"],
            ["John Doe", 30, "New York"],
            ["Jane Smith", 25, "Los Angeles"],
            ["Bob Johnson", 35, "Chicago"]
        ],
        "Sheet2": [
            ["Product", "Price", "Stock"],
            ["Laptop", 999.99, 50],
            ["Mouse", 29.99, 200],
            ["Keyboard", 79.99, 100]
        ]
    }
    
    # Create Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, data in sample_data.items():
            df = pd.DataFrame(data[1:], columns=data[0])
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    output.seek(0)
    
    # Test extraction
    extractor = ExcelTableExtractor()
    
    try:
        result = extractor.extract_from_bytes(output.getvalue(), "test.xlsx")
        
        print("✅ Excel extraction successful!")
        print(f"Found {len(result['sheets'])} sheets")
        
        for sheet in result['sheets']:
            print(f"\n📊 Sheet: {sheet['name']}")
            print(f"   Dimensions: {sheet['summary']['total_rows']} rows × {sheet['summary']['total_cols']} cols")
            print(f"   Non-empty cells: {sheet['summary']['non_empty_cells']}")
            
            # Show first few cells
            print("   Sample cells:")
            for i, cell in enumerate(sheet['data'][:5]):
                print(f"   {cell['cell']}: {cell['value']} ({cell['data_type']})")
            
            if len(sheet['data']) > 5:
                print(f"   ... and {len(sheet['data']) - 5} more cells")
        
        # Test table structure analysis
        print("\n🔍 Table structure analysis:")
        structure = extractor.get_table_structure(result)
        
        for sheet_name, analysis in structure.items():
            print(f"\n📋 {sheet_name}:")
            print(f"   Tables found: {len(analysis['tables'])}")
            
            for i, table in enumerate(analysis['tables'], 1):
                print(f"   Table {i}: {table['start_cell']} to {table['end_cell']} ({table['cell_count']} cells)")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False


if __name__ == "__main__":
    test_excel_extractor()
