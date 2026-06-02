import os
import sys
from datetime import datetime
import pandas as pd
from sqlalchemy import text
from app.db.session import SessionLocal

def import_csv(file_path: str):
    print(f"Reading transaction sheet from {file_path}...")
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} does not exist.")
        return

    try:
        # Load CSV using pandas
        df = pd.read_csv(file_path)
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return

    db = SessionLocal()
    try:
        # 1. Seeding Stores from file data
        unique_stores = df[['store_id', 'store_name']].drop_duplicates().dropna()
        for _, row in unique_stores.iterrows():
            store_code = str(row['store_id']).strip()
            store_name = str(row['store_name']).strip()
            db.execute(
                text("""
                    INSERT INTO stores (id, name, timezone)
                    VALUES (:id, :name, 'UTC')
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": store_code, "name": store_name}
            )
        db.commit()
        print("Stores synced to database.")

        # 2. Syncing Transactions (grouped by invoice_number)
        # Because one invoice can have multiple items (multiple rows in CSV), 
        # we roll up by invoice_number to create a single transaction record.
        invoice_group = df.groupby('invoice_number').agg({
            'store_id': 'first',
            'total_amount': 'sum',
            'order_date': 'first',
            'order_time': 'first',
            'employee_code': 'first'
        }).reset_index()

        print(f"Processing {len(invoice_group)} unique transactions...")
        success_count = 0
        duplicate_count = 0

        for _, row in invoice_group.iterrows():
            pos_id = str(row['invoice_number']).strip()
            store_id = str(row['store_id']).strip()
            amount = float(row['total_amount'])
            register_id = str(row['employee_code']).strip() if pd.notna(row['employee_code']) else "unknown"

            # Parse time and force date to today's date for simulation sync
            time_val = str(row['order_time']).strip()

            try:
                # Format: HH:MM:SS
                t_obj = datetime.strptime(time_val, "%H:%M:%S").time()
                # Use current UTC date
                from datetime import timezone
                today_date = datetime.now(timezone.utc).date()
                timestamp = datetime.combine(today_date, t_obj)
            except Exception as e:
                timestamp = datetime.utcnow()

            try:
                db.execute(
                    text("""
                        INSERT INTO transactions (pos_transaction_id, store_id, amount, timestamp, register_id)
                        VALUES (:pos_id, :store_id, :amount, :timestamp, :register_id)
                        ON CONFLICT (pos_transaction_id) DO NOTHING
                    """),
                    {
                        "pos_id": pos_id,
                        "store_id": store_id,
                        "amount": amount,
                        "timestamp": timestamp,
                        "register_id": register_id
                    }
                )
                success_count += 1
            except Exception as e:
                print(f"Error inserting {pos_id}: {e}")
                duplicate_count += 1

        db.commit()
        print(f"Import Complete: Loaded {success_count} unique transactions. ({duplicate_count} skipped/duplicates)")

    except Exception as e:
        db.rollback()
        print(f"Transaction Import failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import_csv("data/transactions.csv")
