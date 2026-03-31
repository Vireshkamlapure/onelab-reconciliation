import pandas as pd

def create_test_csvs():
    print("Generating test data...")

    # Valid baseline data
    platform_records = [
        {'tx_id': 'TX_001', 'date': '2024-01-05', 'amount': 150.00, 'type': 'Payment'},
        {'tx_id': 'TX_002', 'date': '2024-01-12', 'amount': 200.00, 'type': 'Payment'},
        {'tx_id': 'TX_003', 'date': '2024-01-18', 'amount': 50.00,  'type': 'Payment'},
    ]
    
    bank_records = [
        {'tx_id': 'TX_001', 'settlement_date': '2024-01-06', 'amount': 150.00, 'type': 'Payment'},
        {'tx_id': 'TX_002', 'settlement_date': '2024-01-14', 'amount': 200.00, 'type': 'Payment'},
        {'tx_id': 'TX_003', 'settlement_date': '2024-01-19', 'amount': 50.00,  'type': 'Payment'},
    ]

    # --- BUG 1: Timing Gap ---
    platform_records.append({'tx_id': 'TX_TIMING', 'date': '2024-01-31', 'amount': 500.00, 'type': 'Payment'})
    bank_records.append({'tx_id': 'TX_TIMING', 'settlement_date': '2024-02-02', 'amount': 500.00, 'type': 'Payment'})

    # --- BUG 2: Rounding Difference ---
    for i in range(4, 7):
        tx_id = f'TX_RND_00{i}'
        platform_records.append({'tx_id': tx_id, 'date': '2024-01-20', 'amount': 33.334, 'type': 'Payment'})
        bank_records.append({'tx_id': tx_id, 'settlement_date': '2024-01-21', 'amount': 33.33, 'type': 'Payment'})

    # --- BUG 3: Duplicate Entry ---
    dup_record = {'tx_id': 'TX_DUP', 'date': '2024-01-25', 'amount': 75.00, 'type': 'Payment'}
    platform_records.append(dup_record)
    platform_records.append(dup_record) # The Duplicate
    bank_records.append({'tx_id': 'TX_DUP', 'settlement_date': '2024-01-26', 'amount': 75.00, 'type': 'Payment'})

    # --- BUG 4: Missing Refund ---
    bank_records.append({'tx_id': 'TX_REFUND_99', 'settlement_date': '2024-01-28', 'amount': -45.00, 'type': 'Refund'})

    # Create DataFrames
    df_plat = pd.DataFrame(platform_records)
    df_bank = pd.DataFrame(bank_records)
    
    # Export to CSV (index=False ensures we don't write the pandas row numbers)
    df_plat.to_csv('test_platform_data.csv', index=False)
    df_bank.to_csv('test_bank_data.csv', index=False)
    
    print("✅ Created 'test_platform_data.csv' and 'test_bank_data.csv'")

if __name__ == "__main__":
    create_test_csvs()