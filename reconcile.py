import pandas as pd
import numpy as np

# ==========================================
# 1. SYNTHETIC DATA GENERATION
# ==========================================

def generate_test_data():
    """
    Generates synthetic payment platform and bank settlement data 
    with 4 intentionally planted discrepancies.
    """
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

    # --- BUG 1: Timing Gap (Jan 31 transaction settling in Feb) ---
    platform_records.append({'tx_id': 'TX_TIMING', 'date': '2024-01-31', 'amount': 500.00, 'type': 'Payment'})
    bank_records.append({'tx_id': 'TX_TIMING', 'settlement_date': '2024-02-02', 'amount': 500.00, 'type': 'Payment'})

    # --- BUG 2: Rounding Difference (Platform stores float precision, bank strictly 2 decimals) ---
    # Three transactions of 33.334 sum to 100.002 (Platform) vs 99.99 (Bank)
    for i in range(4, 7):
        tx_id = f'TX_RND_00{i}'
        platform_records.append({'tx_id': tx_id, 'date': '2024-01-20', 'amount': 33.334, 'type': 'Payment'})
        bank_records.append({'tx_id': tx_id, 'settlement_date': '2024-01-21', 'amount': 33.33, 'type': 'Payment'})

    # --- BUG 3: Duplicate Entry (Platform retried and logged twice, bank only processed once) ---
    dup_record = {'tx_id': 'TX_DUP', 'date': '2024-01-25', 'amount': 75.00, 'type': 'Payment'}
    platform_records.append(dup_record)
    platform_records.append(dup_record) # The Duplicate
    bank_records.append({'tx_id': 'TX_DUP', 'settlement_date': '2024-01-26', 'amount': 75.00, 'type': 'Payment'})

    # --- BUG 4: Missing Refund (Bank processed a chargeback/refund not reflected in Platform) ---
    bank_records.append({'tx_id': 'TX_REFUND_99', 'settlement_date': '2024-01-28', 'amount': -45.00, 'type': 'Refund'})

    # Create DataFrames
    df_plat = pd.DataFrame(platform_records)
    df_bank = pd.DataFrame(bank_records)
    
    # Convert dates to datetime objects for accurate filtering
    df_plat['date'] = pd.to_datetime(df_plat['date'])
    df_bank['settlement_date'] = pd.to_datetime(df_bank['settlement_date'])
    
    return df_plat, df_bank


# ==========================================
# 2. RECONCILIATION ENGINE
# ==========================================

def reconcile_january(df_plat, df_bank):
    """
    Compares Platform and Bank datasets for January to find discrepancies.
    """
    print("=== STARTING RECONCILIATION FOR JANUARY ===")
    
    # Isolate January Platform Data
    jan_plat = df_plat[(df_plat['date'] >= '2024-01-01') & (df_plat['date'] <= '2024-01-31')].copy()
    
    # We include early Feb bank data to catch late settlements from Jan 31
    bank_recon_scope = df_bank[(df_bank['settlement_date'] >= '2024-01-01') & (df_bank['settlement_date'] <= '2024-02-05')].copy()

    # --- CATCH BUG 2: Rounding Difference on Totals ---
    plat_total = jan_plat['amount'].sum()
    bank_total = bank_recon_scope[bank_recon_scope['tx_id'].isin(jan_plat['tx_id'])]['amount'].sum()
    
    if not np.isclose(plat_total, bank_total, atol=0.001):
        print(f"\n[FLAG 2 Caught] Macro Discrepancy: Platform Total (${plat_total:.3f}) != Bank Total (${bank_total:.2f})")
        print("  -> Investigation required: Likely fractional float accumulation.")

    # --- CATCH BUG 3: Duplicates ---
    # We MUST strip duplicates before merging to avoid Cartesian explosions
    plat_dups = jan_plat[jan_plat.duplicated('tx_id', keep=False)]
    bank_dups = bank_recon_scope[bank_recon_scope.duplicated('tx_id', keep=False)]
    
    if not plat_dups.empty:
        print(f"\n[FLAG 3 Caught] Duplicate found in Platform Data:")
        print(plat_dups[['tx_id', 'date', 'amount']])
        # Drop duplicates for the rest of the 1:1 reconciliation
        jan_plat = jan_plat.drop_duplicates('tx_id')

    # Join the datasets for 1:1 line-item reconciliation
    # Using an outer join so we can see what's missing on either side
    recon = pd.merge(
        jan_plat, 
        bank_recon_scope, 
        on='tx_id', 
        how='outer', 
        suffixes=('_plat', '_bank'),
        indicator=True # This adds a '_merge' column telling us where the row came from
    )

    # --- CATCH BUG 1: Timing Gap ---
    # Exists in both, but Platform date is Jan and Bank date is Feb
    timing_gaps = recon[
        (recon['_merge'] == 'both') & 
        (recon['date'].dt.month == 1) & 
        (recon['settlement_date'].dt.month == 2)
    ]
    if not timing_gaps.empty:
        print(f"\n[FLAG 1 Caught] Timing Gap (Jan Platform -> Feb Bank Settlement):")
        print(timing_gaps[['tx_id', 'date', 'settlement_date', 'amount_plat']])

    # --- CATCH BUG 4: Missing Refund ---
    # Exists in Bank only (right_only) and type is Refund
    missing_in_plat = recon[recon['_merge'] == 'right_only']
    ghost_refunds = missing_in_plat[missing_in_plat['type_bank'] == 'Refund']
    if not ghost_refunds.empty:
        print(f"\n[FLAG 4 Caught] Bank Refund missing from Platform:")
        print(ghost_refunds[['tx_id', 'settlement_date', 'amount_bank', 'type_bank']])
        
    print("\n=== RECONCILIATION COMPLETE ===")


# ==========================================
# 3. EXECUTION & ASSERTIONS
# ==========================================

if __name__ == "__main__":
    # 1. Generate Data
    platform_data, bank_data = generate_test_data()
    
    # 2. Run Reconciliation
    reconcile_january(platform_data, bank_data)
    
    # 3. Code-level assertions to mathematically prove the states
    assert len(platform_data[platform_data.duplicated('tx_id')]) == 1, "Should be exactly 1 duplicate row"
    assert 'TX_REFUND_99' not in platform_data['tx_id'].values, "Refund should not exist in platform"
    assert platform_data['amount'].sum() != bank_data['amount'].sum(), "Totals should not match due to float rounding"