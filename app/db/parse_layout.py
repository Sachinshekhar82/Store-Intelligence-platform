import pandas as pd

def inspect_layout(file_path: str):
    print("=" * 60)
    print(f"INSPECTING STORE LAYOUT SHEET: {file_path}")
    print("=" * 60)
    
    # Load Excel File
    xls = pd.ExcelFile(file_path)
    print("Sheet Names in Excel:", xls.sheet_names)
    print("-" * 60)
    
    # Read each sheet and show head
    for sheet in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet)
        print(f"\nSheet name: {sheet}")
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print("\nFirst 3 rows:")
        print(df.head(3))
        print("-" * 60)

if __name__ == "__main__":
    inspect_layout("data/store_layout.xlsx")
