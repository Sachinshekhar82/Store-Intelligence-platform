import zipfile
import os

def run():
    xlsx_path = "data/store_layout.xlsx"
    out_path = "data/store_layout.png"
    
    if not os.path.exists(xlsx_path):
        print(f"Error: {xlsx_path} not found.")
        return
        
    try:
        with zipfile.ZipFile(xlsx_path, 'r') as z:
            target = "xl/media/image1.png"
            if target in z.namelist():
                data = z.read(target)
                with open(out_path, 'wb') as f:
                    f.write(data)
                print(f"Successfully extracted {target} to {out_path}!")
            else:
                print(f"Error: {target} not found in zip structure.")
    except Exception as e:
        print("Error extracting image:", e)

if __name__ == "__main__":
    run()
