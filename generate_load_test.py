import pandas as pd
import numpy as np
import uuid
from datetime import datetime, timedelta
import random

def generate_load_test_csvs(num_records=10000):
    print(f"Generating {num_records} baseline records...")
    
    platform_records = []
    bank_records = []
    
    # 1. Generate Valid Baseline Data
    start_date = datetime(2024, 1, 1)
    
    for _ in range(num_records):
        tx_id = f"TX_{uuid.uuid4().hex[:8].upper()}"
        
        # Random date in Jan 2024
        random_days = random.randint(0, 29)
        plat_date = start_date + timedelta(days=random_days)
        
        # Bank settles 1-2 days later
        settle_delay = random.randint(1, 2)
        bank_date = plat_date + timedelta(days=settle_delay)
        
        amount = round(random.uniform(10.0, 500.0), 2)
        
        platform_records.append({
            'tx_id': tx_id, 'date': plat_date.strftime('%Y-%m-%d'), 
            'amount': amount, 'type': 'Payment'
        })
        
        bank_records.append({
            'tx_id': tx_id, 'settlement_date': bank_date.strftime('%Y-%m-%d'), 
            'amount': amount, 'type': 'Payment'
        })

    print("Injecting the 4 core discrepancies...")

    # --- BUG 1: Timing Gap (Jan 31 transaction settling in Feb) ---
    platform_records.append({'tx_id': 'TX_TIMING_LATE', 'date': '2024-01-31', 'amount': 999.00, 'type': 'Payment'})
    bank_records.append({'tx_id': 'TX_TIMING_LATE', 'settlement_date': '2024-02-02', 'amount': 999.00, 'type': 'Payment'})

    # --- BUG 2: Rounding Difference (Micro-cents) ---
    tx_id_rnd = f"TX_RND_{uuid.uuid4().hex[:6].upper()}"
    platform_records.append({'tx_id': tx_id_rnd, 'date': '2024-01-15', 'amount': 100.004, 'type': 'Payment'})
    bank_records.append({'tx_id': tx_id_rnd, 'settlement_date': '2024-01-16', 'amount': 100.00, 'type': 'Payment'})

    # --- BUG 3: Duplicate Entry ---
    tx_id_dup = f"TX_DUP_{uuid.uuid4().hex[:6].upper()}"
    dup_record = {'tx_id': tx_id_dup, 'date': '2024-01-20', 'amount': 250.00, 'type': 'Payment'}
    platform_records.append(dup_record)
    platform_records.append(dup_record) # The Duplicate
    bank_records.append({'tx_id': tx_id_dup, 'settlement_date': '2024-01-21', 'amount': 250.00, 'type': 'Payment'})

    # --- BUG 4: Missing Refund ---
    bank_records.append({
        'tx_id': f"TX_REF_{uuid.uuid4().hex[:6].upper()}", 
        'settlement_date': '2024-01-25', 'amount': -85.50, 'type': 'Refund'
    })

    # 2. Shuffle data so the bugs aren't sitting neatly at the bottom
    random.shuffle(platform_records)
    random.shuffle(bank_records)

    # 3. Create DataFrames & Export
    df_plat = pd.DataFrame(platform_records)
    df_bank = pd.DataFrame(bank_records)
    
    plat_filename = f'load_test_platform_{num_records}.csv'
    bank_filename = f'load_test_bank_{num_records}.csv'
    
    df_plat.to_csv(plat_filename, index=False)
    df_bank.to_csv(bank_filename, index=False)
    
    print(f"✅ Success! Generated '{plat_filename}' and '{bank_filename}'.")

if __name__ == "__main__":
    # Change this number to test how much data Streamlit Cloud can handle
    generate_load_test_csvs(num_records=25000)