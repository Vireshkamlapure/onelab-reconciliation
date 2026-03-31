import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(page_title="Reconciliation Engine", layout="wide")
st.title("Month-End Reconciliation Engine")
st.markdown("This tool compares internal platform transactions against bank settlement records to identify month-end discrepancies.")

# ==========================================
# 1. DEFINE EXPECTED SCHEMAS
# ==========================================
REQUIRED_PLATFORM_COLS = {'tx_id', 'date', 'amount', 'type'}
REQUIRED_BANK_COLS = {'tx_id', 'settlement_date', 'amount', 'type'}

# ==========================================
# 2. HELPER: VALIDATE AND LOAD
# ==========================================
def load_and_validate_csv(uploaded_file, required_cols, source_name):
    """Reads a Streamlit uploaded file into Pandas and validates its schema."""
    try:
        df = pd.read_csv(uploaded_file)
        missing_cols = required_cols - set(df.columns)
        if missing_cols:
            st.error(f"**Schema Error in {source_name} Data:** Missing required columns: `{', '.join(missing_cols)}`")
            return None
        return df
    except pd.errors.EmptyDataError:
        st.error(f"**Error:** The uploaded {source_name} file is empty.")
        return None
    except pd.errors.ParserError:
        st.error(f"**Error:** The {source_name} file is corrupted or not a valid CSV.")
        return None
    except Exception as e:
        st.error(f"**Unexpected Error reading {source_name} file:** {e}")
        return None

# ==========================================
# 3. CORE LOGIC (Decoupled for Testing & Export)
# ==========================================
def analyze_discrepancies(df_plat, df_bank):
    """
    Pure data function containing the reconciliation math. 
    Returns a dictionary of discrepancy dataframes and flags.
    """
    # Ensure dates are datetime objects
    df_plat['date'] = pd.to_datetime(df_plat['date'])
    df_bank['settlement_date'] = pd.to_datetime(df_bank['settlement_date'])
    
    # Isolate scopes
    jan_plat = df_plat[(df_plat['date'] >= '2024-01-01') & (df_plat['date'] <= '2024-01-31')].copy()
    bank_recon_scope = df_bank[(df_bank['settlement_date'] >= '2024-01-01') & (df_bank['settlement_date'] <= '2024-02-05')].copy()

    # --- FLAG 2: Macro Discrepancy ---
    plat_total = jan_plat['amount'].sum()
    bank_total = bank_recon_scope[bank_recon_scope['tx_id'].isin(jan_plat['tx_id'])]['amount'].sum()
    macro_diff = not np.isclose(plat_total, bank_total, atol=0.001)

    # --- FLAG 3: Duplicates ---
    plat_dups = jan_plat[jan_plat.duplicated('tx_id', keep=False)]
    jan_plat_dedup = jan_plat.drop_duplicates('tx_id')

    # Join datasets for 1:1 line-item reconciliation
    recon = pd.merge(
        jan_plat_dedup, 
        bank_recon_scope, 
        on='tx_id', 
        how='outer', 
        suffixes=('_plat', '_bank'),
        indicator=True 
    )

    # --- FLAG 1: Timing Gap ---
    timing_gaps = recon[
        (recon['_merge'] == 'both') & 
        (recon['date'].dt.month == 1) & 
        (recon['settlement_date'].dt.month == 2)
    ]

    # --- FLAG 4: Missing Refund ---
    missing_in_plat = recon[recon['_merge'] == 'right_only']
    ghost_refunds = missing_in_plat[missing_in_plat['type_bank'] == 'Refund']

    return {
        'macro_diff': macro_diff,
        'plat_total': plat_total,
        'bank_total': bank_total,
        'plat_dups': plat_dups,
        'timing_gaps': timing_gaps,
        'ghost_refunds': ghost_refunds
    }

def generate_export_csv(results):
    """Converts the results dictionary into a single, downloadable CSV string."""
    export_rows = []
    
    if results['macro_diff']:
        export_rows.append({
            'Transaction ID': 'SUMMARY_MACRO_DIFF',
            'Issue Type': 'Total Discrepancy (Rounding/Float)',
            'Platform Amount': round(results['plat_total'], 3),
            'Bank Amount': round(results['bank_total'], 2),
            'Platform Date': '', 'Bank Date': ''
        })
        
    for _, row in results['plat_dups'].iterrows():
        export_rows.append({
            'Transaction ID': row['tx_id'], 'Issue Type': 'Duplicate Platform Record',
            'Platform Amount': row['amount'], 'Bank Amount': '',
            'Platform Date': row['date'].strftime('%Y-%m-%d'), 'Bank Date': ''
        })
        
    for _, row in results['timing_gaps'].iterrows():
        export_rows.append({
            'Transaction ID': row['tx_id'], 'Issue Type': 'Timing Gap (Jan -> Feb)',
            'Platform Amount': row['amount_plat'], 'Bank Amount': row['amount_bank'],
            'Platform Date': row['date'].strftime('%Y-%m-%d'), 'Bank Date': row['settlement_date'].strftime('%Y-%m-%d')
        })
        
    for _, row in results['ghost_refunds'].iterrows():
        export_rows.append({
            'Transaction ID': row['tx_id'], 'Issue Type': 'Missing Platform Refund',
            'Platform Amount': '', 'Bank Amount': row['amount_bank'],
            'Platform Date': '', 'Bank Date': row['settlement_date'].strftime('%Y-%m-%d')
        })
        
    if not export_rows:
        return pd.DataFrame([{'Status': 'All records matched perfectly. No discrepancies found.'}]).to_csv(index=False)
        
    return pd.DataFrame(export_rows).to_csv(index=False)

# ==========================================
# 4. UI RENDERING
# ==========================================
def render_reconciliation_report(results):
    st.header("Discrepancy Report")
    
    if results['macro_diff']:
        st.warning(f"**Macro Discrepancy:** \n\nPlatform Total (`${results['plat_total']:.3f}`) does not match Bank Total (`${results['bank_total']:.2f}`). \n\n*Investigation required: Likely fractional float accumulation.*", icon="⚠️")

    if not results['plat_dups'].empty:
        st.error("**Duplicate found in Platform Data:**", icon="🚨")
        st.dataframe(results['plat_dups'][['tx_id', 'date', 'amount', 'type']], use_container_width=True, hide_index=True)

    if not results['timing_gaps'].empty:
        st.info("**Timing Gap (Jan Platform -> Feb Bank Settlement):**", icon="⏱️")
        st.dataframe(results['timing_gaps'][['tx_id', 'date', 'settlement_date', 'amount_plat']], use_container_width=True, hide_index=True)

    if not results['ghost_refunds'].empty:
        st.error("**Bank Refund missing from Platform:**", icon="🚨")
        st.dataframe(results['ghost_refunds'][['tx_id', 'settlement_date', 'amount_bank', 'type_bank']], use_container_width=True, hide_index=True)
        
    st.success("Reconciliation scan complete.", icon="✅")

# ==========================================
# 5. MAIN APP LAYOUT & EXECUTION
# ==========================================
st.markdown("### 📥 Upload Reconciliation Data")

col1, col2 = st.columns(2)
with col1:
    platform_file = st.file_uploader("Upload Platform Data (CSV)", type=['csv'], key="plat_upload")
with col2:
    bank_file = st.file_uploader("Upload Bank Settlement Data (CSV)", type=['csv'], key="bank_upload")

if platform_file and bank_file:
    df_plat = load_and_validate_csv(platform_file, REQUIRED_PLATFORM_COLS, "Platform")
    df_bank = load_and_validate_csv(bank_file, REQUIRED_BANK_COLS, "Bank")
    
    if df_plat is not None and df_bank is not None:
        st.success("✅ Files validated successfully. Ready for reconciliation.")
        
        if st.button("🚀 Run Reconciliation Engine", type="primary"):
            with st.spinner("Crunching the numbers..."):
                # 1. Run Logic
                results = analyze_discrepancies(df_plat, df_bank)
                
                # 2. Render UI
                render_reconciliation_report(results)
                
                # 3. Provide Export
                csv_data = generate_export_csv(results)
                st.download_button(
                    label="📥 Download Discrepancy Report (CSV)",
                    data=csv_data,
                    file_name="reconciliation_discrepancies.csv",
                    mime="text/csv"
                )
                
elif platform_file or bank_file:
    st.info("ℹ️ Please upload both the Platform and Bank files to proceed.")