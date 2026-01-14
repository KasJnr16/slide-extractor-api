"""
Minimal test for Excel extractor
"""

print("Starting Excel extractor test...")

# Test 1: Check if we can import the modules
try:
    import sys
    import os
    print("✅ Basic modules imported")
except Exception as e:
    print(f"❌ Basic import failed: {e}")
    exit(1)

# Test 2: Check if pandas and openpyxl are available
try:
    import pandas as pd
    import openpyxl
    from io import BytesIO
    print("✅ Excel libraries imported")
except ImportError as e:
    print(f"❌ Excel libraries not available: {e}")
    print("Please run: pip install pandas openpyxl")
    exit(1)

# Test 3: Create a simple Excel file
try:
    # Sample data
    data = [["Name", "Score"], ["Alice", 95], ["Bob", 87]]
    df = pd.DataFrame(data[1:], columns=data[0])
    
    # Create Excel in memory
    excel_buffer = BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    
    print("✅ Excel file created in memory")
    print(f"Data shape: {df.shape}")
    print("Sample data:")
    print(df.head().to_string())
    
except Exception as e:
    print(f"❌ Excel creation failed: {e}")
    exit(1)

# Test 4: Test our extractor
try:
    # Import our extractor (adjust path as needed)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)
    
    # Try to import from test directory first
    sys.path.insert(0, current_dir)
    
    from excel_extractor import ExcelTableExtractor
    print("✅ ExcelTableExtractor imported")
    
    # Extract data
    extractor = ExcelTableExtractor()
    result = extractor.extract_from_bytes(excel_buffer.getvalue(), "test.xlsx")
    
    print("✅ Excel extraction successful!")
    print(f"Number of sheets: {len(result['sheets'])}")
    
    # Display results
    for sheet in result['sheets']:
        print(f"\nSheet: {sheet['name']}")
        print(f"  Dimensions: {sheet['summary']['total_rows']} × {sheet['summary']['total_cols']}")
        print(f"  Non-empty cells: {sheet['summary']['non_empty_cells']}")
        
        print("  Cell details:")
        for cell in sheet['data']:
            print(f"    {cell['cell']}: '{cell['value']}' ({cell['data_type']})")
    
    print("\n🎉 All tests passed!")
    
except ImportError as e:
    print(f"❌ Could not import ExcelTableExtractor: {e}")
    print("Make sure excel_extractor.py is in the test directory")
except Exception as e:
    print(f"❌ Extractor test failed: {e}")
    import traceback
    traceback.print_exc()

print("\nTest completed.")
