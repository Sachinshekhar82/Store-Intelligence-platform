import sqlite3

try:
    conn = sqlite3.connect("store_intelligence.db")
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    with open("scratch/db_info.txt", "w") as f:
        f.write(f"Tables: {tables}\n\n")
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            f.write(f"Table '{table_name}' row count: {count}\n")
            
        # Check camera-specific events
        cursor.execute("SELECT camera_id, COUNT(*) FROM events GROUP BY camera_id")
        cam_counts = cursor.fetchall()
        f.write(f"\nEvents by camera:\n{cam_counts}\n")
except Exception as e:
    with open("scratch/db_info.txt", "w") as f:
        f.write(f"Error querying SQLite: {e}\n")
