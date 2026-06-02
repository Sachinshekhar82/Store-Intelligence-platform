import zipfile

def run():
    try:
        with zipfile.ZipFile("data/store_layout.xlsx", 'r') as z:
            media_files = [name for name in z.namelist() if "media" in name]
            if media_files:
                print("Found media files:")
                for name in media_files:
                    print(f" - {name}")
            else:
                print("No media/image files found inside Excel.")
    except Exception as e:
        print("Error unzipping Excel file:", e)

if __name__ == "__main__":
    run()
