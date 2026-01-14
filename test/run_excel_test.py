"""
Simple test runner for Excel extractor
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def main():
    print("🔧 Testing Excel Table Extractor...")
    
    try:
        # Import required modules
        import pandas as pd
        import openpyxl
        from io import BytesIO
        print("✅ Dependencies loaded successfully")
        
        # Import our extractor
        from excel_extractor import ExcelTableExtractor
        print("✅ Excel extractor imported successfully")
        
        # Create test data
        sample_data = [
            ["Name", "Age", "City"],
            ["John Doe", 30, "New York"],
            ["Jane Smith", 25, "Los Angeles"]
        ]
        
        # Create Excel file in memory
        output = BytesIO()
        df = pd.DataFrame(sample_data[1:], columns=sample_data[0])
        df.to_excel(output, index=False)
        output.seek(0)
        
        # Test extraction
        extractor = ExcelTableExtractor()
        result = extractor.extract_from_bytes(output.getvalue(), "test.xlsx")
        
        print(f"\n📊 Extraction Results:")
        print(f"   Sheets found: {len(result['sheets'])}")
        
        for sheet in result['sheets']:
            print(f"\n   📋 Sheet: {sheet['name']}")
            print(f"   Dimensions: {sheet['summary']['total_rows']} × {sheet['summary']['total_cols']}")
            print(f"   Non-empty cells: {sheet['summary']['non_empty_cells']}")
            
            print("   Cell data:")
            for cell in sheet['data']:
                print(f"     {cell['cell']}: '{cell['value']}' ({cell['data_type']})")
        
        print("\n🎉 Excel extractor test completed successfully!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Please install: pip install pandas openpyxl")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
