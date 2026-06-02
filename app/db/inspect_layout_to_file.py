import pandas as pd
import json

def run():
    file_path = "data/store_layout.xlsx"
    out_path = "data/store_layout_summary.json"
    
    try:
        xls = pd.ExcelFile(file_path)
        summary = {
            "sheets": xls.sheet_names,
            "data": {}
        }
        for sheet in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet)
            # Remove entirely empty rows and columns
            cleaned_df = df.dropna(how='all').dropna(axis=1, how='all')
            
            summary["data"][sheet] = {
                "original_shape": df.shape,
                "cleaned_shape": cleaned_df.shape,
                "columns": list(cleaned_df.columns),
                "head": cleaned_df.head(20).to_dict(orient="records")
            }
        with open(out_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)
        print("Success! Summary written to", out_path)
    except Exception as e:
        with open(out_path, "w") as f:
            f.write(f"Error: {str(e)}")
        print("Error details written to", out_path)

if __name__ == "__main__":
    run()
