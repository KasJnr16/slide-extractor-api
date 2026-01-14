"""
Demonstration of Excel Table Extractor usage
"""
import pandas as pd
import openpyxl
from io import BytesIO
import sys
import os

# Add the test directory to path to import our extractor
sys.path.insert(0, os.path.dirname(__file__))

def create_sample_excel():
    """Create a sample Excel file for demonstration"""
    
    # Sample data with different types
    data = [
        ["Employee ID", "Name", "Department", "Salary", "Start Date"],
        ["E001", "Alice Johnson", "Engineering", 75000, "2022-01-15"],
        ["E002", "Bob Smith", "Marketing", 65000, "2021-03-20"],
        ["E003", "Carol Davis", "Sales", 55000, "2023-06-10"],
        ["E004", "David Wilson", "Engineering", 80000, "2020-11-01"]
    ]
    
    # Create Excel file in memory
    output = BytesIO()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.to_excel(output, index=False, sheet_name="Employees")
    
    # Add a second sheet
    with pd.ExcelWriter(output, engine='openpyxl', mode='a') as writer:
        departments_data = [
            ["Department", "Budget", "Headcount"],
            ["Engineering", 500000, 15],
            ["Marketing", 300000, 8],
            ["Sales", 250000, 12]
        ]
        dept_df = pd.DataFrame(departments_data[1:], columns=departments_data[0])
        dept_df.to_excel(writer, sheet_name="Departments", index=False)
    
    output.seek(0)
    return output

def demo_excel_extractor():
    """Demonstrate the Excel extractor functionality"""
    
    print("🔧 Excel Table Extractor Demo")
    print("=" * 50)
    
    try:
        # Import our extractor
        from excel_extractor import ExcelTableExtractor
        print("✅ ExcelTableExtractor imported successfully")
        
        # Create sample Excel file
        print("\n📊 Creating sample Excel file...")
        excel_file = create_sample_excel()
        print("✅ Sample Excel file created")
        
        # Initialize extractor
        extractor = ExcelTableExtractor()
        
        # Extract data
        print("\n🔍 Extracting Excel data...")
        result = extractor.extract_from_bytes(excel_file.getvalue(), "demo.xlsx")
        
        # Display results
        print(f"✅ Extraction completed!")
        print(f"📋 Found {len(result['sheets'])} sheets")
        
        for sheet in result['sheets']:
            print(f"\n📊 Sheet: {sheet['name']}")
            print(f"   Dimensions: {sheet['summary']['total_rows']} rows × {sheet['summary']['total_cols']} columns")
            print(f"   Non-empty cells: {sheet['summary']['non_empty_cells']}")
            
            print(f"\n   Cell-by-cell breakdown:")
            for cell in sheet['data']:
                value_display = cell['value'][:30] + "..." if len(str(cell['value'])) > 30 else cell['value']
                print(f"   {cell['cell']:>4} | Row {cell['row']:>2} | Col {cell['col']:>1} | {cell['data_type']:>8} | {value_display}")
        
        # Demonstrate table structure analysis
        print(f"\n🔍 Table Structure Analysis:")
        structure = extractor.get_table_structure(result)
        
        for sheet_name, analysis in structure.items():
            print(f"\n📋 Sheet '{sheet_name}':")
            print(f"   Tables detected: {len(analysis['tables'])}")
            
            for i, table in enumerate(analysis['tables'], 1):
                print(f"   Table {i}: {table['start_cell']} to {table['end_cell']} ({table['cell_count']} cells)")
                print(f"   Size: {table['end_row'] - table['start_row'] + 1} × {table['end_col'] - table['start_col'] + 1}")
        
        # Demonstrate easy matching capabilities
        print(f"\n🎯 Easy Matching Examples:")
        print("   Find all cells in row 3:")
        row_3_cells = [cell for cell in result['sheets'][0]['data'] if cell['row'] == 3]
        for cell in row_3_cells:
            print(f"     {cell['cell']}: {cell['value']}")
        
        print(f"\n   Find all cells in column B:")
        col_b_cells = [cell for cell in result['sheets'][0]['data'] if cell['col_letter'] == 'B']
        for cell in col_b_cells:
            print(f"     {cell['cell']}: {cell['value']}")
        
        print(f"\n   Find all numeric values:")
        numeric_cells = [cell for cell in result['sheets'][0]['data'] if cell['data_type'] == 'number']
        for cell in numeric_cells:
            print(f"     {cell['cell']}: {cell['value']}")
        
        print(f"\n🎉 Demo completed successfully!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure pandas and openpyxl are installed:")
        print("pip install pandas openpyxl")
        return False
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = demo_excel_extractor()
    sys.exit(0 if success else 1)
