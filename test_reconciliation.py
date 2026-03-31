import pandas as pd
import pytest
from app import analyze_discrepancies

def test_clean_data_no_discrepancies():
    """Validates that perfectly matched data returns no flags."""
    df_plat = pd.DataFrame([
        {'tx_id': 'TX_1', 'date': '2024-01-05', 'amount': 100.00, 'type': 'Payment'}
    ])
    df_bank = pd.DataFrame([
        {'tx_id': 'TX_1', 'settlement_date': '2024-01-06', 'amount': 100.00, 'type': 'Payment'}
    ])
    
    results = analyze_discrepancies(df_plat, df_bank)
    
    assert results['macro_diff'] is False
    assert results['plat_dups'].empty
    assert results['timing_gaps'].empty
    assert results['ghost_refunds'].empty

def test_macro_discrepancy_rounding():
    """Validates Flag 2: Detects micro-cent differences on the aggregate total."""
    df_plat = pd.DataFrame([
        {'tx_id': 'TX_1', 'date': '2024-01-05', 'amount': 33.334, 'type': 'Payment'},
        {'tx_id': 'TX_2', 'date': '2024-01-05', 'amount': 33.334, 'type': 'Payment'},
        {'tx_id': 'TX_3', 'date': '2024-01-05', 'amount': 33.334, 'type': 'Payment'}
    ]) # Total: 100.002
    
    df_bank = pd.DataFrame([
        {'tx_id': 'TX_1', 'settlement_date': '2024-01-06', 'amount': 33.33, 'type': 'Payment'},
        {'tx_id': 'TX_2', 'settlement_date': '2024-01-06', 'amount': 33.33, 'type': 'Payment'},
        {'tx_id': 'TX_3', 'settlement_date': '2024-01-06', 'amount': 33.33, 'type': 'Payment'}
    ]) # Total: 99.99
    
    results = analyze_discrepancies(df_plat, df_bank)
    assert results['macro_diff'] is True

def test_duplicate_platform_record():
    """Validates Flag 3: Detects duplicate rows in the platform data."""
    df_plat = pd.DataFrame([
        {'tx_id': 'TX_DUP', 'date': '2024-01-10', 'amount': 50.00, 'type': 'Payment'},
        {'tx_id': 'TX_DUP', 'date': '2024-01-10', 'amount': 50.00, 'type': 'Payment'} # The duplicate
    ])
    df_bank = pd.DataFrame([
        {'tx_id': 'TX_DUP', 'settlement_date': '2024-01-11', 'amount': 50.00, 'type': 'Payment'}
    ])
    
    results = analyze_discrepancies(df_plat, df_bank)
    
    assert not results['plat_dups'].empty
    assert len(results['plat_dups']) == 2 # Identifies both rows making up the duplication
    assert results['plat_dups'].iloc[0]['tx_id'] == 'TX_DUP'

def test_timing_gap():
    """Validates Flag 1: Detects transactions originating in Jan but settling in Feb."""
    df_plat = pd.DataFrame([
        {'tx_id': 'TX_LATE', 'date': '2024-01-31', 'amount': 200.00, 'type': 'Payment'}
    ])
    df_bank = pd.DataFrame([
        {'tx_id': 'TX_LATE', 'settlement_date': '2024-02-02', 'amount': 200.00, 'type': 'Payment'}
    ])
    
    results = analyze_discrepancies(df_plat, df_bank)
    
    assert not results['timing_gaps'].empty
    assert len(results['timing_gaps']) == 1
    assert results['timing_gaps'].iloc[0]['tx_id'] == 'TX_LATE'

def test_missing_refund():
    """Validates Flag 4: Detects a refund in the bank that isn't logged in the platform."""
    df_plat = pd.DataFrame([
        {'tx_id': 'TX_1', 'date': '2024-01-05', 'amount': 100.00, 'type': 'Payment'}
    ])
    df_bank = pd.DataFrame([
        {'tx_id': 'TX_1', 'settlement_date': '2024-01-06', 'amount': 100.00, 'type': 'Payment'},
        {'tx_id': 'TX_REFUND', 'settlement_date': '2024-01-20', 'amount': -45.00, 'type': 'Refund'}
    ])
    
    results = analyze_discrepancies(df_plat, df_bank)
    
    assert not results['ghost_refunds'].empty
    assert len(results['ghost_refunds']) == 1
    assert results['ghost_refunds'].iloc[0]['tx_id'] == 'TX_REFUND'