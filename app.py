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
        # Read the BytesIO object directly into Pandas
        df = pd.read_csv(uploaded_file)
        
        # Check for missing columns
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
# 3. RECONCILIATION ENGINE UI
# ==========================================
def render_reconciliation_report(df_plat, df_bank):
    """
    Compares Platform and Bank datasets for January to find discrepancies 
    and renders them using Streamlit components.
    """
    st.header("Discrepancy Report")
    
    # Ensure dates are datetime objects before filtering (Crucial for user uploads)
    df_plat['date'] = pd.to_datetime(df_plat['date'])
    df_bank['settlement_date'] = pd.to_datetime(df_bank['settlement_date'])
    
    # Isolate January Platform Data
    jan_plat = df_plat[(df_plat['date'] >= '2024-01-01') & (df_plat['date'] <= '2024-01-31')].copy()
    
    # Include early Feb bank data to catch late settlements from Jan 31
    bank_recon_scope = df_bank[(df_bank['settlement_date'] >= '2024-01-01') & (df_bank['settlement_date'] <= '2024-02-05')].copy()

    # --- CATCH BUG 2: Rounding Difference on Totals ---
    plat_total = jan_plat['amount'].sum()
    bank_total = bank_recon_scope[bank_recon_scope['tx_id'].isin(jan_plat['tx_id'])]['amount'].sum()
    
    if not np.isclose(plat_total, bank_total, atol=0.001):
        st.warning(
            f"**Macro Discrepancy:** \n\n"
            f"Platform Total (`${plat_total:.3f}`) does not match Bank Total (`${bank_total:.2f}`). \n\n"
            f"*Investigation required: Likely fractional float accumulation.*",
            icon="⚠️"
        )

    # --- CATCH BUG 3: Duplicates ---
    plat_dups = jan_plat[jan_plat.duplicated('tx_id', keep=False)]
    
    if not plat_dups.empty:
        st.error("**Duplicate found in Platform Data:**", icon="🚨")
        st.dataframe(plat_dups[['tx_id', 'date', 'amount', 'type']], use_container_width=True, hide_index=True)
        # Drop duplicates for the rest of the 1:1 reconciliation
        jan_plat = jan_plat.drop_duplicates('tx_id')

    # Join the datasets for 1:1 line-item reconciliation
    recon = pd.merge(
        jan_plat, 
        bank_recon_scope, 
        on='tx_id', 
        how='outer', 
        suffixes=('_plat', '_bank'),
        indicator=True 
    )

    # --- CATCH BUG 1: Timing Gap ---
    timing_gaps = recon[
        (recon['_merge'] == 'both') & 
        (recon['date'].dt.month == 1) & 
        (recon['settlement_date'].dt.month == 2)
    ]
    if not timing_gaps.empty:
        st.info("**Timing Gap (Jan Platform -> Feb Bank Settlement):**", icon="⏱️")
        st.dataframe(timing_gaps[['tx_id', 'date', 'settlement_date', 'amount_plat']], use_container_width=True, hide_index=True)

    # --- CATCH BUG 4: Missing Refund ---
    missing_in_plat = recon[recon['_merge'] == 'right_only']
    ghost_refunds = missing_in_plat[missing_in_plat['type_bank'] == 'Refund']
    if not ghost_refunds.empty:
        st.error("**Bank Refund missing from Platform:**", icon="🚨")
        st.dataframe(ghost_refunds[['tx_id', 'settlement_date', 'amount_bank', 'type_bank']], use_container_width=True, hide_index=True)
        
    st.success("Reconciliation scan complete.", icon="✅")

# ==========================================
# 4. MAIN APP LAYOUT & UPLOAD UI
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
        
        with st.expander("🔍 Preview Uploaded Data", expanded=False):
            st.markdown("**Platform Data Head**")
            st.dataframe(df_plat.head(3), use_container_width=True)
            st.markdown("**Bank Data Head**")
            st.dataframe(df_bank.head(3), use_container_width=True)
            
        st.divider()
        
        if st.button("🚀 Run Reconciliation Engine", type="primary"):
            with st.spinner("Crunching the numbers..."):
                render_reconciliation_report(df_plat, df_bank)
                
elif platform_file or bank_file:
    st.info("ℹ️ Please upload both the Platform and Bank files to proceed.")