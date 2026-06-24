"""
Python Auditor Pro — Enterprise Financial Audit System
Main Streamlit Application
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
import warnings
import os
warnings.filterwarnings('ignore')

os.makedirs("data", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# ── Internal modules ────────────────────────────────
from modules.auth import AuthManager, render_login_page
from modules.assignment_manager import (
    AssignmentManager, render_assignment_selector
)
from modules.database import DatabaseManager
from modules.bin_card import BinCardManager
from modules.purchase_ledger import PurchaseLedgerManager
from modules.financial_statements import FinancialStatementsEngine
from modules.data_converter import DataConverter, DOUBLE_ENTRY_RULES
from modules.report_generator import ReportGenerator
from modules.templates import TemplateGenerator

# ── Page Config ─────────────────────────────────────
st.set_page_config(
    page_title="Python Auditor Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Global CSS ───────────────────────────────────────
st.markdown("""
<style>
.main{background:#f0f4f8}
.block-container{padding:1rem 1.5rem}
.audit-header{
    background:linear-gradient(135deg,#1f4e79,#2e75b6,#00b0f0);
    color:white;padding:1.5rem 2rem;border-radius:12px;
    margin-bottom:1rem;box-shadow:0 4px 15px rgba(31,78,121,.3)
}
.audit-header h1{margin:0;font-size:1.8rem;font-weight:800}
.audit-header p{margin:.3rem 0 0;font-size:.9rem;opacity:.88}
.kpi-card{
    background:white;border-radius:10px;
    padding:.9rem 1.1rem;text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.08);
    border-top:4px solid #2e75b6
}
.kpi-card.pass{border-top-color:#00b050}
.kpi-card.fail{border-top-color:#e74c3c}
.kpi-card.warn{border-top-color:#f39c12}
.kpi-value{font-size:1.6rem;font-weight:800;color:#1f4e79}
.kpi-label{font-size:.72rem;color:#6c757d;margin-top:.2rem;
    font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.section-card{
    background:white;border-radius:10px;
    padding:1.2rem 1.4rem;margin-bottom:1rem;
    box-shadow:0 2px 6px rgba(0,0,0,.06)
}
.section-title{
    color:#1f4e79;font-size:1rem;font-weight:700;
    margin-bottom:.7rem;border-bottom:2px solid #dce6f1;
    padding-bottom:.4rem
}
.badge-pass{background:#00b050;color:white;padding:2px 10px;
    border-radius:14px;font-size:.8rem;font-weight:700}
.badge-fail{background:#e74c3c;color:white;padding:2px 10px;
    border-radius:14px;font-size:.8rem;font-weight:700}
section[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#1f4e79,#2e75b6)
}
section[data-testid="stSidebar"] *{color:white!important}
section[data-testid="stSidebar"] .stSelectbox>div{
    background:rgba(255,255,255,.15)!important
}
</style>
""", unsafe_allow_html=True)


# ── Session State ────────────────────────────────────
def init_state():
    defaults = {
        'authenticated': False,
        'user': None,
        'current_assignment': None,
        'current_module': 'Dashboard'
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ────────────────────────────────────────────────────
# AUTHENTICATION GATE
# ────────────────────────────────────────────────────
if not st.session_state['authenticated']:
    render_login_page()
    st.stop()

user = st.session_state['user']
auth = AuthManager()


# ────────────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align:center;padding:.8rem 0">
            <div style="font-size:2rem">🔍</div>
            <div style="font-size:1.1rem;font-weight:800">
                Python Auditor Pro
            </div>
            <div style="font-size:.8rem;opacity:.8">
                Enterprise Audit System
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        # User info
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.15);
            border-radius:8px;padding:.5rem .8rem;margin-bottom:.5rem">
            <div style="font-weight:700;font-size:.85rem">
                👤 {user.get('full_name', user['username'])}
            </div>
            <div style="font-size:.75rem;opacity:.8">
                Role: {user.get('role', 'VIEWER')}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Assignment selector
        st.markdown("### 📂 Assignment")
        assign_id = render_assignment_selector(user)
        if assign_id:
            st.session_state['current_assignment'] = assign_id

        st.markdown("---")

        # Navigation
        st.markdown("### 🗺️ Navigation")
        modules = [
            ("🏠", "Dashboard"),
            ("📁", "Assignments"),
            ("📦", "Inventory & Bin Cards"),
            ("🛒", "Purchase Ledger"),
            ("💸", "Expenses"),
            ("📒", "Journal Entries"),
            ("🔄", "Data Converter"),
            ("📊", "Financial Statements"),
            ("⚖️", "Trial Balance"),
            ("🔍", "Audit Engine"),
            ("📋", "Data Manager"),
            ("📥", "Upload Templates"),
        ]

        if auth.has_permission(user.get('role', ''), 'all'):
            modules.append(("👥", "User Management"))

        for icon, mod in modules:
            if st.button(
                f"{icon} {mod}",
                use_container_width=True,
                key=f"nav_{mod}"
            ):
                st.session_state['current_module'] = mod
                st.rerun()

        st.markdown("---")
        if st.button("🚪 Sign Out", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()


render_sidebar()

# ── Get active DB ────────────────────────────────────
def get_db() -> DatabaseManager | None:
    aid = st.session_state.get('current_assignment')
    if aid:
        return DatabaseManager(aid)
    return None


def get_entity_name() -> str:
    db = get_db()
    if not db:
        return "No Assignment Selected"
    entity = db.execute_query(
        "SELECT entity_name FROM entity LIMIT 1"
    )
    return entity[0]['entity_name'] if entity else "Unknown Entity"


# ── Header ───────────────────────────────────────────
module = st.session_state.get('current_module', 'Dashboard')
entity_name = get_entity_name()

st.markdown(f"""
<div class="audit-header">
    <h1>🔍 {module}</h1>
    <p>
        Python Auditor Pro &nbsp;|&nbsp;
        Entity: <strong>{entity_name}</strong> &nbsp;|&nbsp;
        User: {user.get('full_name', user['username'])} &nbsp;|&nbsp;
        {datetime.now().strftime('%d %b %Y %H:%M')}
    </p>
</div>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# MODULE RENDERERS
# ════════════════════════════════════════════════════

# ── DASHBOARD ────────────────────────────────────────
def render_dashboard():
    db = get_db()

    if not db:
        st.info("👆 Select or create an assignment from the sidebar.")
        mgr = AssignmentManager()
        assignments = mgr.get_all_assignments()
        if assignments:
            st.markdown("### 📂 Recent Assignments")
            for a in assignments[:5]:
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                col1.write(f"**{a['entity_name']}**")
                col2.write(a['assignment_name'])
                col3.write(a['fiscal_year'])
                if col4.button("Open", key=f"open_{a['assignment_id']}"):
                    st.session_state['current_assignment'] = (
                        a['assignment_id']
                    )
                    st.rerun()
        return

    pm = PurchaseLedgerManager(db)
    bc = BinCardManager(db)

    # KPI Row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    kpis = [
        (c1, db.execute_query(
            "SELECT COUNT(*) cnt FROM purchases WHERE is_posted=1"
         )[0]['cnt'], "Posted Purchases", ""),
        (c2, db.execute_query(
            "SELECT COALESCE(SUM(net_amount),0) amt "
            "FROM purchases WHERE is_posted=1"
         )[0]['amt'], "Total Purchases $", ""),
        (c3, db.execute_query(
            "SELECT COUNT(*) cnt FROM expenses WHERE is_posted=1"
         )[0]['cnt'], "Posted Expenses", ""),
        (c4, db.execute_query(
            "SELECT COUNT(*) cnt FROM journal_entries"
         )[0]['cnt'], "Journal Entries", ""),
        (c5, db.execute_query(
            "SELECT COUNT(*) cnt FROM bin_cards"
         )[0]['cnt'], "Bin Card Entries", ""),
        (c6, db.execute_query(
            "SELECT COUNT(*) cnt FROM purchase_returns"
         )[0]['cnt'], "Purchase Returns", "warn")
    ]

    for col, val, label, cls in kpis:
        with col:
            display = (
                f"${val:,.0f}" if "Purchases $" in label
                else str(val)
            )
            st.markdown(f"""
            <div class="kpi-card {cls}">
                <div class="kpi-value">{display}</div>
                <div class="kpi-label">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    # Recent Journals
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 📒 Recent Journal Entries")
        recent_je = db.query_to_df("""
            SELECT entry_number, entry_date, description,
                   entry_type, source_module
            FROM journal_entries
            ORDER BY id DESC LIMIT 10
        """)
        if not recent_je.empty:
            st.dataframe(
                recent_je, use_container_width=True, height=280
            )
        else:
            st.info("No journal entries yet.")

    with col2:
        st.markdown("### ⚠️ Low Stock Alerts")
        low_stock = bc.get_low_stock_items()
        if not low_stock.empty:
            st.dataframe(
                low_stock, use_container_width=True, height=280
            )
        else:
            st.success("✅ All items above reorder level.")

    # Inventory value chart
    st.markdown("### 📦 Inventory Valuation")
    inv_summary = bc.get_inventory_summary()
    if not inv_summary.empty:
        import plotly.express as px
        fig = px.bar(
            inv_summary.head(15),
            x='Item Code',
            y='Total Value',
            color='Status',
            color_discrete_map={
                'OK': '#00b050',
                'REORDER': '#e74c3c'
            },
            title="Inventory Value by Item"
        )
        fig.update_layout(
            height=350,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True)


# ── ASSIGNMENTS ──────────────────────────────────────
def render_assignments():
    mgr = AssignmentManager()

    tabs = st.tabs([
        "📂 All Assignments",
        "➕ New Assignment",
        "✏️ Entity Particulars"
    ])

    with tabs[0]:
        assignments = mgr.get_all_assignments()
        if assignments:
            df = pd.DataFrame(assignments)
            st.dataframe(
                df[[
                    'assignment_id', 'assignment_name',
                    'entity_name', 'entity_type',
                    'fiscal_year', 'status', 'created_at'
                ]],
                use_container_width=True
            )
        else:
            st.info("No assignments yet. Create one below.")

    with tabs[1]:
        st.markdown("### 🏢 Create New Assignment")
        with st.form("new_assignment"):
            col1, col2 = st.columns(2)
            with col1:
                assignment_name = st.text_input(
                    "Assignment Name *",
                    placeholder="e.g. FY2024 Annual Audit"
                )
                entity_name_input = st.text_input(
                    "Entity / Company Name *",
                    placeholder="e.g. Acme Corporation Ltd"
                )
                entity_type = st.selectbox(
                    "Entity Type",
                    ["Company", "Partnership", "Sole Trader",
                     "Non-Profit", "Government", "Trust"]
                )
                registration_number = st.text_input(
                    "Registration Number",
                    placeholder="Company registration #"
                )
                tax_number = st.text_input(
                    "Tax / VAT Number",
                    placeholder="Tax identification number"
                )
                industry = st.selectbox(
                    "Industry",
                    ["Manufacturing", "Retail", "Services",
                     "Agriculture", "Construction", "Healthcare",
                     "Technology", "Finance", "Other"]
                )

            with col2:
                assignment_type = st.selectbox(
                    "Assignment Type",
                    ["AUDIT", "REVIEW", "COMPILATION",
                     "BOOKKEEPING", "TAX"]
                )
                fiscal_year = st.text_input(
                    "Fiscal Year",
                    placeholder="e.g. 2024 or 2023/2024"
                )
                fy_start = st.date_input(
                    "Fiscal Year Start",
                    value=date(date.today().year, 1, 1)
                )
                fy_end = st.date_input(
                    "Fiscal Year End",
                    value=date(date.today().year, 12, 31)
                )
                currency = st.selectbox(
                    "Reporting Currency",
                    ["USD", "EUR", "GBP", "ZAR", "CAD",
                     "AUD", "JPY", "CHF", "CNY", "INR"]
                )
                accounting_standard = st.selectbox(
                    "Accounting Standard",
                    ["GAAP (US)", "IFRS", "GAAP (UK)", "Other"]
                )

            st.markdown("### 📍 Entity Contact Details")
            c1, c2 = st.columns(2)
            with c1:
                address = st.text_area(
                    "Address", height=80
                )
                city = st.text_input("City")
                country = st.text_input("Country")
            with c2:
                phone = st.text_input("Phone")
                email = st.text_input("Email")
                website = st.text_input("Website")

            description = st.text_area(
                "Assignment Notes / Scope",
                height=80
            )

            submitted = st.form_submit_button(
                "🚀 Create Assignment",
                type="primary",
                use_container_width=True
            )

            if submitted:
                if not assignment_name or not entity_name_input:
                    st.error("Assignment name and entity name are required.")
                else:
                    aid = mgr.create_assignment(
                        assignment_name=assignment_name,
                        entity_name=entity_name_input,
                        entity_data={
                            'assignment_type': assignment_type,
                            'entity_type': entity_type,
                            'registration_number': registration_number,
                            'tax_number': tax_number,
                            'address': address,
                            'city': city,
                            'country': country,
                            'phone': phone,
                            'email': email,
                            'website': website,
                            'fiscal_year': fiscal_year,
                            'fiscal_year_start': str(fy_start),
                            'fiscal_year_end': str(fy_end),
                            'currency': currency,
                            'accounting_standard': accounting_standard,
                            'industry': industry,
                            'description': description
                        },
                        created_by=user['username']
                    )
                    st.success(
                        f"✅ Assignment created! ID: **{aid}**"
                    )
                    st.session_state['current_assignment'] = aid
                    st.rerun()

    with tabs[2]:
        db = get_db()
        if not db:
            st.warning("Select an assignment first.")
            return

        entity = db.execute_query("SELECT * FROM entity LIMIT 1")
        if entity:
            e = entity[0]
            st.markdown("### 🏢 Entity Particulars")
            with st.form("entity_particulars"):
                c1, c2 = st.columns(2)
                with c1:
                    en = st.text_input(
                        "Entity Name", value=e.get('entity_name', '')
                    )
                    et = st.text_input(
                        "Entity Type", value=e.get('entity_type', '')
                    )
                    reg = st.text_input(
                        "Registration #",
                        value=e.get('registration_number', '')
                    )
                    tax = st.text_input(
                        "Tax Number", value=e.get('tax_number', '')
                    )
                    curr = st.text_input(
                        "Currency", value=e.get('currency', 'USD')
                    )
                with c2:
                    addr = st.text_area(
                        "Address", value=e.get('address', ''),
                        height=80
                    )
                    phone_v = st.text_input(
                        "Phone", value=e.get('phone', '')
                    )
                    email_v = st.text_input(
                        "Email", value=e.get('email', '')
                    )
                    std = st.text_input(
                        "Accounting Standard",
                        value=e.get('accounting_standard', 'GAAP')
                    )

                if st.form_submit_button("💾 Update Entity"):
                    db.execute_write("""
                        UPDATE entity SET
                        entity_name=?, entity_type=?,
                        registration_number=?, tax_number=?,
                        currency=?, address=?, phone=?,
                        email=?, accounting_standard=?
                        WHERE id=1
                    """, (en, et, reg, tax, curr,
                          addr, phone_v, email_v, std))
                    st.success("✅ Entity particulars updated.")


# ── INVENTORY & BIN CARDS ────────────────────────────
def render_inventory():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    bc = BinCardManager(db)

    tabs = st.tabs([
        "📊 Inventory Summary",
        "🗂️ Bin Card Viewer",
        "➕ Register Item",
        "📤 Post Manual Movement",
        "⚠️ FIFO Layers",
        "📥 Download Bin Card"
    ])

    with tabs[0]:
        st.markdown("### 📊 Current Inventory Valuation")
        inv = bc.get_inventory_summary()
        if not inv.empty:
            # Summary KPIs
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Total Items",
                len(inv)
            )
            c2.metric(
                "Total Inventory Value",
                f"${inv['Total Value'].sum():,.2f}"
            )
            c3.metric(
                "Items at Reorder Level",
                len(inv[inv['Status'] == 'REORDER'])
            )

            st.dataframe(
                inv.style.applymap(
                    lambda v: 'background-color:#ffe0e0'
                    if v == 'REORDER' else '',
                    subset=['Status']
                ),
                use_container_width=True,
                height=420
            )
        else:
            st.info("No inventory items registered.")

    with tabs[1]:
        items = db.execute_query(
            "SELECT DISTINCT item_code FROM bin_cards"
        )
        item_codes = [r['item_code'] for r in items]

        if not item_codes:
            st.info("No bin card entries yet.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                selected_item = st.selectbox(
                    "Select Item Code", item_codes
                )
            with col2:
                warehouse = st.selectbox(
                    "Warehouse", ['MAIN', 'SECONDARY', 'ALL']
                )

            wh = None if warehouse == 'ALL' else warehouse
            bc_df = bc.get_bin_card(
                selected_item,
                wh if wh else 'MAIN'
            )

            if not bc_df.empty:
                st.markdown(
                    f"**Bin Card: {selected_item}**"
                )
                st.dataframe(
                    bc_df, use_container_width=True, height=400
                )

                # Running balance chart
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=bc_df['Date'],
                    y=bc_df['Balance Qty'],
                    name='Balance Qty',
                    line=dict(color='#2e75b6', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(46,117,182,.15)'
                ))
                fig.update_layout(
                    title=f"Running Balance - {selected_item}",
                    height=300,
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig, use_container_width=True)

    with tabs[2]:
        st.markdown("### ➕ Register New Item")
        with st.form("register_item"):
            c1, c2 = st.columns(2)
            with c1:
                item_code = st.text_input(
                    "Item Code *",
                    placeholder="e.g. ITM001"
                )
                item_description = st.text_input(
                    "Description *"
                )
                item_category = st.selectbox(
                    "Category",
                    ["Raw Materials", "Finished Goods",
                     "Work in Progress", "Consumables",
                     "Spare Parts", "Trading Stock"]
                )
                uom = st.selectbox(
                    "Unit of Measure",
                    ["UNIT", "KG", "LITRE", "METRE",
                     "BOX", "DOZEN", "TONNE"]
                )
            with c2:
                reorder_level = st.number_input(
                    "Reorder Level", min_value=0.0, value=0.0
                )
                reorder_qty = st.number_input(
                    "Reorder Quantity", min_value=0.0, value=0.0
                )
                warehouse = st.text_input(
                    "Warehouse", value="MAIN"
                )
                bin_loc = st.text_input(
                    "Bin Location", placeholder="e.g. A-01-01"
                )

            if st.form_submit_button(
                "Register Item", type="primary"
            ):
                bc.register_item({
                    'item_code': item_code,
                    'item_description': item_description,
                    'item_category': item_category,
                    'unit_of_measure': uom,
                    'reorder_level': reorder_level,
                    'reorder_quantity': reorder_qty,
                    'warehouse': warehouse,
                    'bin_location': bin_loc
                })
                st.success(f"✅ Item {item_code} registered.")

    with tabs[3]:
        st.markdown("### 📤 Post Manual Movement")
        with st.form("manual_movement"):
            c1, c2 = st.columns(2)
            with c1:
                mv_date = st.date_input("Date")
                mv_item = st.text_input("Item Code *")
                mv_desc = st.text_input("Description")
                mv_type = st.selectbox(
                    "Movement Type",
                    ["RECEIPT", "ISSUE", "ADJUSTMENT"]
                )
            with c2:
                mv_qty = st.number_input(
                    "Quantity *", min_value=0.01
                )
                mv_cost = st.number_input(
                    "Unit Cost *", min_value=0.01
                )
                mv_ref = st.text_input(
                    "Reference", value=f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                mv_wh = st.text_input("Warehouse", value="MAIN")
                mv_notes = st.text_input("Notes")

            if st.form_submit_button("Post Movement"):
                try:
                    if mv_type == "RECEIPT":
                        bc.post_receipt(
                            mv_item, mv_desc, mv_qty,
                            mv_cost, str(mv_date),
                            mv_ref, mv_wh, mv_notes
                        )
                    elif mv_type == "ISSUE":
                        bc.post_issue(
                            mv_item, mv_desc, mv_qty,
                            str(mv_date), mv_ref,
                            mv_wh, mv_notes
                        )
                    st.success("✅ Movement posted successfully.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

    with tabs[4]:
        items = db.execute_query(
            "SELECT DISTINCT item_code FROM fifo_layers"
        )
        if items:
            sel = st.selectbox(
                "Item Code",
                [r['item_code'] for r in items],
                key="fifo_item"
            )
            layers = bc.get_fifo_layers(sel)
            if not layers.empty:
                st.dataframe(layers, use_container_width=True)
        else:
            st.info("No FIFO layers found.")

    with tabs[5]:
        rpt = ReportGenerator()
        items2 = db.execute_query(
            "SELECT DISTINCT item_code FROM bin_cards"
        )
        if items2:
            sel2 = st.selectbox(
                "Item Code for Report",
                [r['item_code'] for r in items2],
                key="bc_rpt"
            )
            bc_df2 = bc.get_bin_card(sel2)
            if not bc_df2.empty:
                bc_bytes = rpt.generate_bin_card_report(
                    bc_df2, sel2, entity_name
                )
                st.download_button(
                    f"⬇️ Download Bin Card — {sel2}",
                    data=bc_bytes,
                    file_name=f"BinCard_{sel2}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )


# ── PURCHASE LEDGER ───────────────────────────────────
def render_purchase_ledger():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    pm = PurchaseLedgerManager(db)
    rpt = ReportGenerator()

    tabs = st.tabs([
        "📋 Purchase Ledger",
        "➕ New Purchase",
        "🔄 Purchase Returns",
        "📊 AP Aging",
        "📤 Bulk Upload",
        "📥 Reports"
    ])

    with tabs[0]:
        st.markdown("### 📋 Purchase Ledger (AP Ledger)")

        suppliers = db.execute_query(
            "SELECT DISTINCT supplier_name FROM purchase_ledger"
        )
        supplier_list = (
            ['ALL'] + [s['supplier_name'] for s in suppliers]
        )
        sel_sup = st.selectbox(
            "Filter by Supplier", supplier_list
        )

        ledger_df = pm.get_purchase_ledger(
            None if sel_sup == 'ALL' else sel_sup
        )

        if not ledger_df.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Total Transactions", len(ledger_df)
            )
            c2.metric(
                "Total Invoiced",
                f"${ledger_df['Credit'].sum():,.2f}"
            )
            c3.metric(
                "Current Balance",
                f"${ledger_df['Balance'].iloc[-1]:,.2f}"
            )
            st.dataframe(
                ledger_df, use_container_width=True, height=400
            )
        else:
            st.info("No purchase ledger entries yet.")

    with tabs[1]:
        st.markdown("### ➕ New Purchase")
        with st.form("new_purchase"):
            c1, c2 = st.columns(2)
            with c1:
                p_date = st.date_input("Purchase Date *")
                supplier_name = st.text_input("Supplier Name *")
                supplier_code = st.text_input(
                    "Supplier Code", placeholder="SUP001"
                )
                invoice_number = st.text_input("Invoice Number")
                inv_date = st.date_input("Invoice Date")
                due_date = st.date_input("Due Date")
            with c2:
                item_code = st.text_input("Item Code")
                item_desc = st.text_input("Item Description *")
                quantity = st.number_input(
                    "Quantity *", min_value=0.001, step=0.001
                )
                unit_cost = st.number_input(
                    "Unit Cost *", min_value=0.001, step=0.001
                )
                tax_amount = st.number_input(
                    "Tax Amount", min_value=0.0
                )
                discount = st.number_input(
                    "Discount Amount", min_value=0.0
                )
                warehouse = st.selectbox(
                    "Warehouse",
                    ["MAIN", "SECONDARY", "WAREHOUSE_A", "WAREHOUSE_B"]
                )

            accounts = db.execute_query(
                "SELECT account_code, account_name "
                "FROM chart_of_accounts "
                "WHERE account_type IN ('Asset','Expense') "
                "AND parent_code IS NOT NULL"
            )
            acct_opts = {
                f"{a['account_code']} - {a['account_name']}": a['account_code']
                for a in accounts
            }
            sel_acct = st.selectbox(
                "Debit Account",
                list(acct_opts.keys())
            )
            notes = st.text_area("Notes", height=60)

            col_sub, col_post = st.columns(2)
            save_btn = col_sub.form_submit_button(
                "💾 Save (Draft)", use_container_width=True
            )
            post_btn = col_post.form_submit_button(
                "✅ Save & Post", type="primary",
                use_container_width=True
            )

            if save_btn or post_btn:
                if not supplier_name or not item_desc:
                    st.error("Supplier and Item are required.")
                else:
                    pid = pm.create_purchase({
                        'purchase_date': str(p_date),
                        'supplier_code': supplier_code,
                        'supplier_name': supplier_name,
                        'invoice_number': invoice_number,
                        'invoice_date': str(inv_date),
                        'due_date': str(due_date),
                        'item_code': item_code,
                        'item_description': item_desc,
                        'quantity': quantity,
                        'unit_cost': unit_cost,
                        'tax_amount': tax_amount,
                        'discount_amount': discount,
                        'account_code': acct_opts.get(sel_acct, '1300'),
                        'warehouse': warehouse,
                        'notes': notes
                    })

                    if post_btn:
                        result = pm.post_purchase(
                            pid, user['username']
                        )
                        st.success(
                            f"✅ Posted! JE: {result['journal_entry']}"
                        )
                    else:
                        st.success(f"✅ Purchase saved as draft (ID: {pid})")

        # Unposted drafts
        st.markdown("### 📄 Unposted Purchases")
        drafts = db.query_to_df("""
            SELECT id, purchase_number, purchase_date,
                   supplier_name, item_description, net_amount, status
            FROM purchases WHERE is_posted=0
        """)
        if not drafts.empty:
            for _, row in drafts.iterrows():
                col_a, col_b = st.columns([5, 1])
                col_a.write(
                    f"**{row['purchase_number']}** | "
                    f"{row['supplier_name']} | "
                    f"{row['item_description']} | "
                    f"${row['net_amount']:,.2f}"
                )
                if col_b.button(
                    "Post",
                    key=f"post_{row['id']}"
                ):
                    result = pm.post_purchase(
                        int(row['id']), user['username']
                    )
                    st.success(
                        f"Posted: {result['journal_entry']}"
                    )
                    st.rerun()

    with tabs[2]:
        st.markdown("### 🔄 Purchase Returns")
        with st.form("purchase_return"):
            c1, c2 = st.columns(2)
            with c1:
                ret_date = st.date_input("Return Date *")
                ret_supplier = st.text_input("Supplier Name *")
                ret_item = st.text_input("Item Code")
                ret_desc = st.text_input("Item Description")
            with c2:
                ret_qty = st.number_input(
                    "Quantity Returned *", min_value=0.001
                )
                ret_cost = st.number_input(
                    "Unit Cost *", min_value=0.001
                )
                ret_reason = st.text_area(
                    "Reason for Return *", height=60
                )

                # Link to original purchase
                purchases = db.execute_query(
                    "SELECT id, purchase_number FROM purchases "
                    "WHERE is_posted=1 ORDER BY id DESC LIMIT 50"
                )
                po_opts = {
                    f"{p['purchase_number']}": p['id']
                    for p in purchases
                }
                po_opts = {'None': None, **po_opts}
                sel_po = st.selectbox(
                    "Original Purchase (Optional)",
                    list(po_opts.keys())
                )

            if st.form_submit_button(
                "✅ Post Return", type="primary"
            ):
                result = pm.create_purchase_return({
                    'return_date': str(ret_date),
                    'supplier_name': ret_supplier,
                    'item_code': ret_item,
                    'item_description': ret_desc,
                    'quantity_returned': ret_qty,
                    'unit_cost': ret_cost,
                    'reason': ret_reason,
                    'original_purchase_id': po_opts.get(sel_po)
                }, user['username'])
                st.success(
                    f"✅ Return posted: {result['return_number']} | "
                    f"JE: {result['journal_entry']}"
                )

        # Returns history
        st.markdown("### 📋 Purchase Returns History")
        returns = db.query_to_df("""
            SELECT return_number, return_date, supplier_name,
                   item_description, quantity_returned,
                   total_return_amount, reason, status
            FROM purchase_returns ORDER BY id DESC
        """)
        if not returns.empty:
            st.dataframe(returns, use_container_width=True)

    with tabs[3]:
        st.markdown("### 📊 AP Aging Analysis")
        aging = pm.get_ap_aging()
        if not aging.empty:
            st.dataframe(aging, use_container_width=True)
            import plotly.express as px
            fig = px.bar(
                aging,
                x='Supplier',
                y=['0-30 Days', '31-60 Days',
                   '61-90 Days', '90+ Days'],
                barmode='stack',
                title="AP Aging by Supplier",
                color_discrete_sequence=[
                    '#00b050', '#ffc000', '#f39c12', '#e74c3c'
                ]
            )
            fig.update_layout(height=380)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No AP balance data.")

    with tabs[4]:
        st.markdown("### 📤 Bulk Upload Purchases")
        tmpl = TemplateGenerator()
        tmpl_bytes = tmpl.generate_template('purchases')
        st.download_button(
            "⬇️ Download Purchase Template",
            data=tmpl_bytes,
            file_name="purchase_upload_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        uploaded = st.file_uploader(
            "Upload Completed Template",
            type=['xlsx', 'xls'],
            key='purchase_bulk'
        )
        if uploaded:
            df_upload = pd.read_excel(uploaded)
            df_upload.columns = [
                c.lower() for c in df_upload.columns
            ]
            st.dataframe(df_upload.head(10), use_container_width=True)

            if st.button("✅ Import All Purchases"):
                success = 0
                for _, row in df_upload.iterrows():
                    try:
                        pid = pm.create_purchase(row.to_dict())
                        pm.post_purchase(pid, user['username'])
                        success += 1
                    except Exception as e:
                        st.warning(f"Row error: {e}")
                st.success(
                    f"✅ Imported & posted {success} purchases."
                )

    with tabs[5]:
        st.markdown("### 📥 Purchase Ledger Reports")
        ledger_all = pm.get_purchase_ledger()
        if not ledger_all.empty:
            rpt_bytes = rpt.generate_purchase_ledger_report(
                ledger_all, entity_name
            )
            st.download_button(
                "⬇️ Download Purchase Ledger (Excel)",
                data=rpt_bytes,
                file_name=f"PurchaseLedger_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )


# ── EXPENSES ─────────────────────────────────────────
def render_expenses():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    tabs = st.tabs([
        "📋 Expense Ledger",
        "➕ New Expense",
        "📤 Bulk Upload"
    ])

    with tabs[0]:
        expenses = db.query_to_df("""
            SELECT expense_number, expense_date, expense_category,
                   description, vendor_name, amount, tax_amount,
                   total_amount, payment_method, status
            FROM expenses ORDER BY expense_date DESC
        """)
        if not expenses.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Expenses", len(expenses))
            c2.metric(
                "Total Amount",
                f"${expenses['total_amount'].sum():,.2f}"
            )
            posted = len(expenses[expenses['status'] == 'POSTED'])
            c3.metric("Posted", posted)

            import plotly.express as px
            if 'expense_category' in expenses.columns:
                fig = px.pie(
                    expenses,
                    names='expense_category',
                    values='total_amount',
                    title="Expenses by Category"
                )
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(expenses, use_container_width=True)
        else:
            st.info("No expenses recorded yet.")

    with tabs[1]:
        st.markdown("### ➕ Record New Expense")
        with st.form("new_expense"):
            c1, c2 = st.columns(2)

            rows = db.execute_query(
                "SELECT COUNT(*) cnt FROM expenses"
            )
            exp_num = f"EXP-{(rows[0]['cnt'] + 1):06d}"

            with c1:
                exp_date = st.date_input("Expense Date *")
                exp_cat = st.selectbox(
                    "Category *",
                    ["Utilities", "Salaries", "Rent", "Travel",
                     "Marketing", "Professional Fees",
                     "Office Supplies", "Maintenance",
                     "Insurance", "Other"]
                )
                exp_desc = st.text_input("Description *")
                vendor = st.text_input("Vendor Name")
                ref = st.text_input(
                    "Reference", value=exp_num
                )

            with c2:
                amount = st.number_input(
                    "Amount *", min_value=0.01, step=0.01
                )
                tax_amt = st.number_input(
                    "Tax Amount", min_value=0.0
                )
                payment_method = st.selectbox(
                    "Payment Method",
                    ["Bank Transfer", "Cash", "Credit Card",
                     "Cheque", "Mobile Payment"]
                )
                cost_center = st.text_input(
                    "Cost Center", placeholder="ADMIN"
                )

            accounts = db.execute_query(
                "SELECT account_code, account_name "
                "FROM chart_of_accounts "
                "WHERE account_code LIKE '6%' "
                "AND parent_code IS NOT NULL"
            )
            acct_opts = {
                f"{a['account_code']} - {a['account_name']}": a['account_code']
                for a in accounts
            }
            sel_acct = st.selectbox(
                "Expense Account",
                list(acct_opts.keys())
            )
            notes = st.text_area("Notes", height=60)

            if st.form_submit_button(
                "✅ Post Expense", type="primary"
            ):
                total = amount + tax_amt
                exp_id = db.execute_write("""
                    INSERT INTO expenses
                    (expense_number, expense_date, expense_category,
                     description, vendor_name, reference, amount,
                     tax_amount, total_amount, account_code,
                     cost_center, payment_method, notes, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    exp_num, str(exp_date), exp_cat,
                    exp_desc, vendor, ref,
                    amount, tax_amt, total,
                    acct_opts.get(sel_acct, '6900'),
                    cost_center, payment_method,
                    notes, 'PENDING'
                ))

                # Create journal entry
                rows2 = db.execute_query(
                    "SELECT COUNT(*) cnt FROM journal_entries"
                )
                je_num = f"JE-{(rows2[0]['cnt'] + 1):06d}"

                credit_acct = (
                    '1110' if payment_method == 'Cash'
                    else '1120'
                )

                je_id = db.execute_write("""
                    INSERT INTO journal_entries
                    (entry_number, entry_date, description,
                     reference, entry_type, source_module,
                     is_posted, created_by, posted_by, posted_at)
                    VALUES (?,?,?,?,?,?,1,?,?,?)
                """, (
                    je_num, str(exp_date),
                    f"Expense: {exp_desc}",
                    exp_num, 'EXPENSE', 'EXPENSE_MODULE',
                    user['username'], user['username'],
                    datetime.now().isoformat()
                ))

                db.execute_many("""
                    INSERT INTO journal_lines
                    (entry_id, line_number, account_code,
                     account_name, debit_amount, credit_amount,
                     description)
                    VALUES (?,?,?,?,?,?,?)
                """, [
                    (je_id, 1,
                     acct_opts.get(sel_acct, '6900'),
                     exp_cat, total, 0, exp_desc),
                    (je_id, 2, credit_acct,
                     'Cash/Bank', 0, total, exp_desc)
                ])

                db.execute_write("""
                    UPDATE expenses SET is_posted=1,
                    status='POSTED', journal_entry_id=?
                    WHERE id=?
                """, (je_id, exp_id))

                st.success(
                    f"✅ Expense posted! JE: {je_num}"
                )

    with tabs[2]:
        tmpl = TemplateGenerator()
        tmpl_bytes = tmpl.generate_template('expenses')
        st.download_button(
            "⬇️ Download Expense Template",
            data=tmpl_bytes,
            file_name="expense_upload_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# ── JOURNAL ENTRIES ───────────────────────────────────
def render_journals():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    tabs = st.tabs([
        "📒 General Ledger",
        "➕ New Journal",
        "🔄 Adjustment Journals",
        "↩️ Reverse Entry"
    ])

    with tabs[0]:
        st.markdown("### 📒 General Ledger")
        col1, col2, col3 = st.columns(3)
        with col1:
            from_date = st.date_input(
                "From Date",
                value=date(date.today().year, 1, 1),
                key="gl_from"
            )
        with col2:
            to_date = st.date_input(
                "To Date",
                value=date.today(),
                key="gl_to"
            )
        with col3:
            accts = db.execute_query(
                "SELECT DISTINCT account_code FROM journal_lines"
            )
            acct_filter = st.selectbox(
                "Filter Account",
                ['ALL'] + [a['account_code'] for a in accts]
            )

        fse = FinancialStatementsEngine(db)
        gl = fse.get_general_ledger(
            str(from_date), str(to_date),
            None if acct_filter == 'ALL' else acct_filter
        )

        if not gl.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric(
                "Total Debits",
                f"${gl['Debit'].sum():,.2f}"
            )
            c2.metric(
                "Total Credits",
                f"${gl['Credit'].sum():,.2f}"
            )
            balanced = abs(
                gl['Debit'].sum() - gl['Credit'].sum()
            ) < 0.01
            c3.markdown(
                f"**Balance:** "
                f"<span class='badge-{'pass' if balanced else 'fail'}'>"
                f"{'✅ BALANCED' if balanced else '❌ UNBALANCED'}"
                f"</span>",
                unsafe_allow_html=True
            )
            st.dataframe(gl, use_container_width=True, height=420)
        else:
            st.info("No ledger entries for selected period.")

    with tabs[1]:
        st.markdown("### ➕ Manual Journal Entry")
        st.info(
            "Add lines below. Each journal must balance "
            "(Total Debits = Total Credits)."
        )

        accounts = db.execute_query("""
            SELECT account_code, account_name, normal_balance
            FROM chart_of_accounts
            WHERE parent_code IS NOT NULL AND is_active=1
            ORDER BY account_code
        """)
        acct_map = {
            f"{a['account_code']} - {a['account_name']}": a['account_code']
            for a in accounts
        }
        acct_list = list(acct_map.keys())

        with st.form("manual_journal"):
            c1, c2 = st.columns(2)
            with c1:
                je_date = st.date_input("Journal Date *")
                je_desc = st.text_input("Description *")
            with c2:
                je_ref = st.text_input(
                    "Reference",
                    value=f"MJE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                )
                je_type = st.selectbox(
                    "Entry Type",
                    ["MANUAL", "ADJUSTMENT", "ACCRUAL",
                     "PREPAYMENT", "DEPRECIATION"]
                )

            st.markdown("**Journal Lines (minimum 2 lines):**")
            n_lines = st.number_input(
                "Number of Lines", min_value=2, max_value=20,
                value=2, step=1
            )

            lines = []
            total_dr = 0.0
            total_cr = 0.0

            for i in range(int(n_lines)):
                c1, c2, c3, c4 = st.columns([3, 2, 2, 3])
                with c1:
                    acct = st.selectbox(
                        f"Account Line {i+1}",
                        acct_list,
                        key=f"je_acct_{i}"
                    )
                with c2:
                    dr = st.number_input(
                        f"Debit {i+1}",
                        min_value=0.0, step=0.01,
                        key=f"je_dr_{i}"
                    )
                with c3:
                    cr = st.number_input(
                        f"Credit {i+1}",
                        min_value=0.0, step=0.01,
                        key=f"je_cr_{i}"
                    )
                with c4:
                    ln_desc = st.text_input(
                        f"Line Desc {i+1}",
                        key=f"je_ldesc_{i}"
                    )
                total_dr += dr
                total_cr += cr
                lines.append((acct, dr, cr, ln_desc))

            st.markdown(
                f"**Totals — Debit: ${total_dr:,.2f} | "
                f"Credit: ${total_cr:,.2f}** | "
                f"{'✅ Balanced' if abs(total_dr - total_cr) < 0.01 else '❌ Unbalanced'}"
            )

            if st.form_submit_button(
                "✅ Post Journal Entry", type="primary"
            ):
                if abs(total_dr - total_cr) > 0.01:
                    st.error(
                        "❌ Journal does not balance! "
                        "Debits must equal Credits."
                    )
                else:
                    rows = db.execute_query(
                        "SELECT COUNT(*) cnt FROM journal_entries"
                    )
                    je_num = f"JE-{(rows[0]['cnt'] + 1):06d}"

                    je_id = db.execute_write("""
                        INSERT INTO journal_entries
                        (entry_number, entry_date, description,
                         reference, entry_type, source_module,
                         is_posted, created_by, posted_by, posted_at)
                        VALUES (?,?,?,?,?,?,1,?,?,?)
                    """, (
                        je_num, str(je_date), je_desc,
                        je_ref, je_type, 'MANUAL_ENTRY',
                        user['username'], user['username'],
                        datetime.now().isoformat()
                    ))

                    for ln_no, (acct, dr, cr, ld) in enumerate(
                        lines, 1
                    ):
                        acct_code = acct_map.get(acct, acct[:4])
                        db.execute_write("""
                            INSERT INTO journal_lines
                            (entry_id, line_number, account_code,
                             account_name, debit_amount,
                             credit_amount, description)
                            VALUES (?,?,?,?,?,?,?)
                        """, (
                            je_id, ln_no, acct_code,
                            acct, dr, cr, ld
                        ))

                    st.success(
                        f"✅ Journal Entry {je_num} posted successfully!"
                    )

    with tabs[2]:
        st.markdown("### 🔄 Adjustment Journals")
        st.info(
            "Post period-end adjustments: accruals, "
            "prepayments, depreciation, etc."
        )
        adj_types = {
            "Depreciation": {
                "dr": "6400", "cr": "1590",
                "dr_name": "Depreciation Expense",
                "cr_name": "Accumulated Depreciation"
            },
            "Accrued Expense": {
                "dr": "6900", "cr": "2200",
                "dr_name": "Misc Expense",
                "cr_name": "Accrued Liabilities"
            },
            "Prepaid Expense": {
                "dr": "1400", "cr": "1120",
                "dr_name": "Prepaid Expenses",
                "cr_name": "Bank Account"
            }
        }

        with st.form("adjustment_journal"):
            c1, c2 = st.columns(2)
            with c1:
                adj_date = st.date_input("Adjustment Date")
                adj_type = st.selectbox(
                    "Adjustment Type",
                    list(adj_types.keys())
                )
                adj_amount = st.number_input(
                    "Amount *", min_value=0.01
                )
            with c2:
                adj_desc = st.text_input("Description *")
                adj_ref = st.text_input(
                    "Reference",
                    value=f"ADJ-{datetime.now().strftime('%Y%m%d')}"
                )

            if st.form_submit_button(
                "Post Adjustment", type="primary"
            ):
                rule = adj_types[adj_type]
                rows = db.execute_query(
                    "SELECT COUNT(*) cnt FROM journal_entries"
                )
                je_num = f"ADJ-{(rows[0]['cnt'] + 1):06d}"
                je_id = db.execute_write("""
                    INSERT INTO journal_entries
                    (entry_number, entry_date, description,
                     reference, entry_type, source_module,
                     is_posted, created_by, posted_by, posted_at)
                    VALUES (?,?,?,?,?,?,1,?,?,?)
                """, (
                    je_num, str(adj_date), adj_desc,
                    adj_ref, 'ADJUSTMENT', 'DATA_MANAGER',
                    user['username'], user['username'],
                    datetime.now().isoformat()
                ))
                db.execute_many("""
                    INSERT INTO journal_lines
                    (entry_id, line_number, account_code,
                     account_name, debit_amount, credit_amount,
                     description)
                    VALUES (?,?,?,?,?,?,?)
                """, [
                    (je_id, 1, rule['dr'],
                     rule['dr_name'], adj_amount, 0, adj_desc),
                    (je_id, 2, rule['cr'],
                     rule['cr_name'], 0, adj_amount, adj_desc)
                ])
                st.success(
                    f"✅ Adjustment {je_num} posted."
                )

    with tabs[3]:
        st.markdown("### ↩️ Reverse Journal Entry")
        je_list = db.execute_query("""
            SELECT id, entry_number, entry_date, description
            FROM journal_entries WHERE is_reversed=0
            ORDER BY id DESC LIMIT 50
        """)
        if je_list:
            opts = {
                f"{j['entry_number']} | {j['entry_date']} | "
                f"{j['description'][:40]}": j['id']
                for j in je_list
            }
            sel_je = st.selectbox("Select Entry to Reverse", list(opts.keys()))
            rev_date = st.date_input("Reversal Date")
            rev_reason = st.text_input("Reason for Reversal *")

            if st.button("↩️ Post Reversal", type="primary"):
                je_id = opts[sel_je]
                original_lines = db.execute_query(
                    "SELECT * FROM journal_lines WHERE entry_id=?",
                    (je_id,)
                )
                rows = db.execute_query(
                    "SELECT COUNT(*) cnt FROM journal_entries"
                )
                rev_num = f"REV-{(rows[0]['cnt'] + 1):06d}"

                rev_je_id = db.execute_write("""
                    INSERT INTO journal_entries
                    (entry_number, entry_date, description,
                     reference, entry_type, source_module,
                     is_posted, reversal_of, created_by,
                     posted_by, posted_at)
                    VALUES (?,?,?,?,?,?,1,?,?,?,?)
                """, (
                    rev_num, str(rev_date),
                    f"REVERSAL: {rev_reason}",
                    rev_num, 'REVERSAL', 'MANUAL_ENTRY',
                    je_id,
                    user['username'], user['username'],
                    datetime.now().isoformat()
                ))

                # Swap debits and credits
                for ln in original_lines:
                    db.execute_write("""
                        INSERT INTO journal_lines
                        (entry_id, line_number, account_code,
                         account_name, debit_amount, credit_amount,
                         description)
                        VALUES (?,?,?,?,?,?,?)
                    """, (
                        rev_je_id, ln['line_number'],
                        ln['account_code'], ln['account_name'],
                        ln['credit_amount'], ln['debit_amount'],
                        f"Reversal: {ln.get('description', '')}"
                    ))

                db.execute_write(
                    "UPDATE journal_entries SET is_reversed=1 WHERE id=?",
                    (je_id,)
                )
                st.success(f"✅ Reversal {rev_num} posted.")


# ── DATA CONVERTER ────────────────────────────────────
def render_data_converter():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    converter = DataConverter(db)
    tmpl_gen = TemplateGenerator()

    tabs = st.tabs([
        "🔄 Convert Transactions",
        "📋 Transaction Type Rules",
        "📤 Scanned Data Import",
        "📥 Download Templates"
    ])

    with tabs[0]:
        st.markdown("### 🔄 Single-Entry → Double-Entry Converter")

        # Download template
        tmpl_bytes = tmpl_gen.generate_template('single_entry')
        st.download_button(
            "⬇️ Download Single Entry Template",
            data=tmpl_bytes,
            file_name="single_entry_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        uploaded = st.file_uploader(
            "Upload Single Entry Data (Excel/CSV)",
            type=['xlsx', 'xls', 'csv'],
            key='single_entry_upload'
        )

        if uploaded:
            if uploaded.name.endswith('.csv'):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)

            st.markdown("**Preview (first 5 rows):**")
            st.dataframe(df.head(), use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                trans_type = st.selectbox(
                    "Transaction Type *",
                    list(DOUBLE_ENTRY_RULES.keys())
                )
                date_col = st.selectbox(
                    "Date Column",
                    df.columns.tolist()
                )
                amount_col = st.selectbox(
                    "Amount Column",
                    df.columns.tolist()
                )
            with col2:
                desc_col = st.selectbox(
                    "Description Column (optional)",
                    ['None'] + df.columns.tolist()
                )
                ref_col = st.selectbox(
                    "Reference Column (optional)",
                    ['None'] + df.columns.tolist()
                )

                # Account overrides
                accounts = db.execute_query(
                    "SELECT account_code, account_name "
                    "FROM chart_of_accounts "
                    "WHERE parent_code IS NOT NULL"
                )
                acct_opts = {
                    'Default': None,
                    **{
                        f"{a['account_code']} - {a['account_name']}":
                        a['account_code']
                        for a in accounts
                    }
                }
                override_dr = st.selectbox(
                    "Override Debit Account",
                    list(acct_opts.keys())
                )
                override_cr = st.selectbox(
                    "Override Credit Account",
                    list(acct_opts.keys())
                )

            if st.button(
                "🔄 Preview Conversion", use_container_width=True
            ):
                converted = converter.convert_single_entry(
                    df,
                    trans_type,
                    date_col,
                    amount_col,
                    desc_col if desc_col != 'None' else None,
                    ref_col if ref_col != 'None' else None,
                    acct_opts.get(override_dr),
                    acct_opts.get(override_cr)
                )
                st.session_state['converted_df'] = converted
                st.dataframe(converted, use_container_width=True)
                st.metric(
                    "Converted Entries",
                    f"{len(converted)//2} journal entries"
                )

            if (
                'converted_df' in st.session_state
                and st.button(
                    "✅ Post All Converted Entries",
                    type="primary",
                    use_container_width=True
                )
            ):
                count = converter.post_converted_entries(
                    st.session_state['converted_df'],
                    user['username']
                )
                st.success(
                    f"✅ {count} journal entries posted successfully!"
                )
                del st.session_state['converted_df']

    with tabs[1]:
        st.markdown("### 📋 Available Transaction Type Rules")
        rules = converter.get_available_rules()
        rules_df = pd.DataFrame(rules)
        st.dataframe(
            rules_df, use_container_width=True, height=400
        )

    with tabs[2]:
        st.markdown("### 📤 Scanned Data Import")
        st.info(
            "Upload CSV/Excel from scanned receipts, "
            "bank statements, or OCR output. "
            "The converter will map to double-entry."
        )
        scanned = st.file_uploader(
            "Upload Scanned/OCR Data",
            type=['csv', 'xlsx', 'xls'],
            key='scanned_upload'
        )
        if scanned:
            if scanned.name.endswith('.csv'):
                scan_df = pd.read_csv(scanned)
            else:
                scan_df = pd.read_excel(scanned)

            st.dataframe(scan_df.head(10), use_container_width=True)
            detected_type = converter.detect_transaction_type(scan_df)
            st.info(
                f"💡 Detected transaction type: **{detected_type}**"
            )

    with tabs[3]:
        st.markdown("### 📥 Download Upload Templates")
        tmpl_gen2 = TemplateGenerator()
        all_templates = tmpl_gen2.get_template_list()

        for tmpl in all_templates:
            col1, col2, col3 = st.columns([3, 2, 2])
            col1.write(f"**{tmpl['title']}**")
            col2.write(f"{tmpl['columns']} columns")
            tmpl_data = tmpl_gen2.generate_template(tmpl['key'])
            col3.download_button(
                f"⬇️ Download",
                data=tmpl_data,
                file_name=f"{tmpl['key']}_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"tmpl_dl_{tmpl['key']}"
            )


# ── FINANCIAL STATEMENTS ──────────────────────────────
def render_financial_statements():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    fse = FinancialStatementsEngine(db)
    rpt = ReportGenerator()

    entity = db.execute_query(
        "SELECT fiscal_year_start, fiscal_year_end FROM entity LIMIT 1"
    )
    fy_start = (
        entity[0]['fiscal_year_start']
        if entity else str(date(date.today().year, 1, 1))
    )
    fy_end = (
        entity[0]['fiscal_year_end']
        if entity else str(date.today())
    )

    col1, col2 = st.columns(2)
    from_date = col1.date_input(
        "Period From",
        value=pd.to_datetime(fy_start).date()
        if fy_start else date(date.today().year, 1, 1)
    )
    to_date = col2.date_input(
        "Period To",
        value=pd.to_datetime(fy_end).date()
        if fy_end else date.today()
    )

    tabs = st.tabs([
        "📊 Income Statement",
        "⚖️ Balance Sheet",
        "💧 Cash Flow",
        "📋 General Ledger",
        "📥 Download Reports"
    ])

    with tabs[0]:
        st.markdown("### 📊 Income Statement (P&L)")
        is_data = fse.get_income_statement(
            str(from_date), str(to_date)
        )
        totals = is_data['totals']

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Total Revenue",
            f"${totals['total_revenue']:,.2f}"
        )
        c2.metric(
            "Gross Profit",
            f"${totals['gross_profit']:,.2f}",
            f"{totals['gross_margin_pct']:.1f}%"
        )
        c3.metric(
            "Operating Expenses",
            f"${totals['total_expenses']:,.2f}"
        )
        color = (
            "normal" if totals['net_income'] >= 0
            else "inverse"
        )
        c4.metric(
            "Net Income",
            f"${totals['net_income']:,.2f}"
        )

        for section, df in [
            ("💰 REVENUE", is_data['revenue']),
            ("📦 COST OF SALES", is_data['cogs']),
            ("💸 EXPENSES", is_data['expenses'])
        ]:
            st.markdown(f"**{section}**")
            if not df.empty:
                disp_cols = [
                    c for c in [
                        'Account Code', 'Account Name',
                        'Closing Balance'
                    ]
                    if c in df.columns
                ]
                if disp_cols:
                    st.dataframe(
                        df[disp_cols], use_container_width=True,
                        height=180
                    )
            st.markdown("---")

    with tabs[1]:
        st.markdown(
            f"### ⚖️ Balance Sheet as at {to_date}"
        )
        bs = fse.get_balance_sheet(str(to_date))
        bs_totals = bs['totals']

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Total Assets",
            f"${bs_totals['total_assets']:,.2f}"
        )
        c2.metric(
            "Total Liabilities",
            f"${bs_totals['total_liabilities']:,.2f}"
        )
        c3.metric(
            "Total Equity",
            f"${bs_totals['total_equity']:,.2f}"
        )
        balanced = bs_totals['balanced']
        c4.markdown(
            f"**Balance Check:** "
            f"<span class='badge-{'pass' if balanced else 'fail'}'>"
            f"{'✅ BALANCED' if balanced else '❌ UNBALANCED'}"
            f"</span>",
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**ASSETS**")
            assets = bs['assets']
            if not assets.empty:
                disp = [
                    c for c in [
                        'Account Code', 'Account Name',
                        'Category', 'Closing Balance'
                    ] if c in assets.columns
                ]
                st.dataframe(assets[disp], use_container_width=True)

        with col2:
            st.markdown("**LIABILITIES & EQUITY**")
            liab = bs['liabilities']
            eq = bs['equity']
            combined = pd.concat([liab, eq], ignore_index=True)
            if not combined.empty:
                disp = [
                    c for c in [
                        'Account Code', 'Account Name',
                        'Account Type', 'Closing Balance'
                    ] if c in combined.columns
                ]
                st.dataframe(combined[disp], use_container_width=True)

        # Key ratios
        st.markdown("### 📐 Key Financial Ratios")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric(
            "Working Capital",
            f"${bs_totals['working_capital']:,.2f}"
        )
        r2.metric(
            "Current Ratio",
            f"{bs_totals['current_ratio']:.2f}x"
        )
        r3.metric(
            "Debt/Equity",
            f"{(bs_totals['total_liabilities'] / max(bs_totals['total_equity'], 1)):.2f}x"
        )
        r4.metric(
            "Equity Ratio",
            f"{(bs_totals['total_equity'] / max(bs_totals['total_assets'], 1) * 100):.1f}%"
        )

    with tabs[2]:
        st.markdown("### 💧 Cash Flow Statement")
        cf = fse.get_cash_flow_statement(
            str(from_date), str(to_date)
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Operating Cash Flow",
            f"${cf['operating']['net_operating']:,.2f}"
        )
        c2.metric(
            "Investing Cash Flow",
            f"${cf['investing']['net_investing']:,.2f}"
        )
        c3.metric(
            "Financing Cash Flow",
            f"${cf['financing']['net_financing']:,.2f}"
        )
        c4.metric(
            "Net Cash Change",
            f"${cf['net_change']:,.2f}"
        )

        st.markdown("**Operating Activities:**")
        op = cf['operating']
        for k, v in op.items():
            if k != 'net_operating':
                st.write(f"  • {k.replace('_', ' ').title()}: ${v:,.2f}")
        st.write(
            f"**Net Cash from Operations: ${op['net_operating']:,.2f}**"
        )

    with tabs[3]:
        gl_df = fse.get_general_ledger(
            str(from_date), str(to_date)
        )
        if not gl_df.empty:
            st.dataframe(
                gl_df, use_container_width=True, height=500
            )
        else:
            st.info("No ledger entries for selected period.")

    with tabs[4]:
        is_data2 = fse.get_income_statement(
            str(from_date), str(to_date)
        )
        bs_data2 = fse.get_balance_sheet(str(to_date))
        tb_data = fse.get_trial_balance(
            str(from_date), str(to_date)
        )

        col1, col2 = st.columns(2)
        with col1:
            fin_bytes = rpt.generate_financial_report(
                is_data2, bs_data2, entity_name
            )
            st.download_button(
                "⬇️ Download Financial Statements (Excel)",
                data=fin_bytes,
                file_name=f"Financial_Statements_{entity_name}_{to_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        with col2:
            if not tb_data.empty:
                tb_bytes = rpt.generate_trial_balance_report(
                    tb_data, entity_name,
                    f"{from_date} to {to_date}"
                )
                st.download_button(
                    "⬇️ Download Trial Balance (Excel)",
                    data=tb_bytes,
                    file_name=f"TrialBalance_{entity_name}_{to_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )


# ── TRIAL BALANCE ─────────────────────────────────────
def render_trial_balance():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    fse = FinancialStatementsEngine(db)
    rpt = ReportGenerator()

    col1, col2 = st.columns(2)
    from_d = col1.date_input(
        "From", value=date(date.today().year, 1, 1)
    )
    to_d = col2.date_input("To", value=date.today())

    tb = fse.get_trial_balance(str(from_d), str(to_d))

    if not tb.empty:
        total_dr = tb['Total Debits'].sum()
        total_cr = tb['Total Credits'].sum()
        balanced = abs(total_dr - total_cr) < 0.01

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Debits", f"${total_dr:,.2f}")
        c2.metric("Total Credits", f"${total_cr:,.2f}")
        c3.markdown(
            f"**Status:** "
            f"<span class='badge-{'pass' if balanced else 'fail'}'>"
            f"{'✅ BALANCED' if balanced else '❌ UNBALANCED'}"
            f"</span>",
            unsafe_allow_html=True
        )

        # Filter by type
        acct_types = ['ALL'] + tb['Account Type'].unique().tolist()
        filter_type = st.selectbox(
            "Filter by Account Type", acct_types
        )
        display_tb = (
            tb if filter_type == 'ALL'
            else tb[tb['Account Type'] == filter_type]
        )

        st.dataframe(
            display_tb.style.format({
                'Total Debits': '${:,.2f}',
                'Total Credits': '${:,.2f}',
                'Net Balance': '${:,.2f}',
                'Closing Balance': '${:,.2f}'
            }),
            use_container_width=True,
            height=500
        )

        tb_bytes = rpt.generate_trial_balance_report(
            tb, entity_name, f"{from_d} to {to_d}"
        )
        st.download_button(
            "⬇️ Download Trial Balance",
            data=tb_bytes,
            file_name=f"TB_{entity_name}_{to_d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    else:
        st.info(
            "No journal entries found for the selected period."
        )


# ── DATA MANAGER ──────────────────────────────────────
def render_data_manager():
    db = get_db()
    if not db:
        st.warning("⚠️ Select an assignment first.")
        return

    st.markdown(
        "### 🛠️ Data Manager — View, Edit & Correct Records"
    )
    tabs = st.tabs([
        "📋 View & Edit Purchases",
        "💸 View & Edit Expenses",
        "📒 View Journals",
        "🗑️ Void Transaction",
        "📊 Audit Trail"
    ])

    with tabs[0]:
        purchases = db.query_to_df("""
            SELECT id, purchase_number, purchase_date,
                   supplier_name, item_description,
                   quantity, unit_cost, net_amount,
                   status, is_posted
            FROM purchases ORDER BY id DESC
        """)
        if not purchases.empty:
            st.dataframe(purchases, use_container_width=True)

            st.markdown("**Edit Unposted Purchase:**")
            unposted = purchases[purchases['is_posted'] == 0]
            if not unposted.empty:
                edit_id = st.selectbox(
                    "Select Purchase to Edit",
                    unposted['id'].tolist(),
                    format_func=lambda x: (
                        purchases[purchases['id'] == x
                                  ]['purchase_number'].values[0]
                    )
                )
                row = purchases[purchases['id'] == edit_id].iloc[0]

                with st.form("edit_purchase"):
                    c1, c2 = st.columns(2)
                    with c1:
                        new_qty = st.number_input(
                            "Quantity",
                            value=float(row['quantity'])
                        )
                        new_cost = st.number_input(
                            "Unit Cost",
                            value=float(row['unit_cost'])
                        )
                    with c2:
                        new_supplier = st.text_input(
                            "Supplier",
                            value=str(row['supplier_name'])
                        )
                        new_desc = st.text_input(
                            "Description",
                            value=str(row['item_description'])
                        )

                    if st.form_submit_button(
                        "💾 Save Changes", type="primary"
                    ):
                        new_total = new_qty * new_cost
                        db.execute_write("""
                            UPDATE purchases
                            SET quantity=?, unit_cost=?,
                                net_amount=?, total_amount=?,
                                supplier_name=?,
                                item_description=?
                            WHERE id=? AND is_posted=0
                        """, (
                            new_qty, new_cost, new_total,
                            new_total, new_supplier, new_desc,
                            edit_id
                        ))
                        db.log_action(
                            user['username'], 'DATA_MANAGER',
                            'EDIT_PURCHASE', str(edit_id)
                        )
                        st.success("✅ Purchase updated.")
            else:
                st.info("No unposted purchases to edit.")

    with tabs[1]:
        expenses = db.query_to_df("""
            SELECT id, expense_number, expense_date,
                   expense_category, description, total_amount, status
            FROM expenses ORDER BY id DESC
        """)
        if not expenses.empty:
            st.dataframe(expenses, use_container_width=True)

    with tabs[2]:
        journals = db.query_to_df("""
            SELECT je.id, je.entry_number, je.entry_date,
                   je.description, je.entry_type,
                   je.source_module, je.is_reversed,
                   COUNT(jl.id) as line_count,
                   SUM(jl.debit_amount) as total_debits
            FROM journal_entries je
            LEFT JOIN journal_lines jl ON je.id=jl.entry_id
            GROUP BY je.id ORDER BY je.id DESC
        """)
        if not journals.empty:
            st.dataframe(journals, use_container_width=True)

            sel_je = st.selectbox(
                "View Journal Lines",
                journals['id'].tolist(),
                format_func=lambda x: (
                    journals[journals['id'] == x
                             ]['entry_number'].values[0]
                )
            )
            lines = db.query_to_df(
                "SELECT * FROM journal_lines WHERE entry_id=?",
                (sel_je,)
            )
            if not lines.empty:
                st.dataframe(lines, use_container_width=True)

    with tabs[3]:
        st.markdown("### 🗑️ Void Transaction")
        st.warning(
            "⚠️ Voiding creates a reversal entry. "
            "Original records are preserved for audit."
        )
        je_list = db.execute_query("""
            SELECT id, entry_number, entry_date, description
            FROM journal_entries WHERE is_reversed=0
            ORDER BY id DESC LIMIT 100
        """)
        if je_list:
            opts = {
                f"{j['entry_number']} | {j['description'][:50]}": j['id']
                for j in je_list
            }
            sel = st.selectbox(
                "Select Entry to Void",
                list(opts.keys())
            )
            void_reason = st.text_input("Void Reason *")
            if st.button("🗑️ Void Entry", type="primary"):
                if void_reason:
                    je_id = opts[sel]
                    orig_lines = db.execute_query(
                        "SELECT * FROM journal_lines WHERE entry_id=?",
                        (je_id,)
                    )
                    rows = db.execute_query(
                        "SELECT COUNT(*) cnt FROM journal_entries"
                    )
                    void_num = f"VOID-{rows[0]['cnt']+1:06d}"
                    void_je = db.execute_write("""
                        INSERT INTO journal_entries
                        (entry_number, entry_date, description,
                         entry_type, is_posted, reversal_of,
                         created_by, posted_by, posted_at)
                        VALUES (?,date('now'),?,?,1,?,?,?,?)
                    """, (
                        void_num,
                        f"VOID: {void_reason}",
                        'VOID', je_id,
                        user['username'], user['username'],
                        datetime.now().isoformat()
                    ))
                    for ln in orig_lines:
                        db.execute_write("""
                            INSERT INTO journal_lines
                            (entry_id, account_code, account_name,
                             debit_amount, credit_amount, description)
                            VALUES (?,?,?,?,?,?)
                        """, (
                            void_je, ln['account_code'],
                            ln['account_name'],
                            ln['credit_amount'], ln['debit_amount'],
                            f"VOID: {void_reason}"
                        ))
                    db.execute_write(
                        "UPDATE journal_entries SET is_reversed=1 WHERE id=?",
                        (je_id,)
                    )
                    st.success(f"✅ Entry voided: {void_num}")

    with tabs[4]:
        audit_log = db.query_to_df("""
            SELECT action_date, user_name, module,
                   action, record_id
            FROM audit_log ORDER BY id DESC LIMIT 200
        """)
        if not audit_log.empty:
            st.dataframe(audit_log, use_container_width=True)
        else:
            st.info("No audit trail entries yet.")


# ── USER MANAGEMENT ───────────────────────────────────
def render_user_management():
    if not auth.has_permission(
        user.get('role', ''), 'all'
    ):
        st.error("⛔ Access Denied")
        return

    auth_mgr = AuthManager()
    tabs = st.tabs(["👥 All Users", "➕ Create User", "🔑 Reset Password"])

    with tabs[0]:
        users = auth_mgr.get_all_users()
        if users:
            st.dataframe(
                pd.DataFrame(users), use_container_width=True
            )

    with tabs[1]:
        with st.form("create_user"):
            c1, c2 = st.columns(2)
            with c1:
                new_username = st.text_input("Username *")
                new_fullname = st.text_input("Full Name *")
                new_email = st.text_input("Email")
            with c2:
                new_pass = st.text_input("Password *", type="password")
                new_pass2 = st.text_input(
                    "Confirm Password *", type="password"
                )
                new_role = st.selectbox(
                    "Role",
                    ["ADMIN", "AUDITOR", "ACCOUNTANT", "VIEWER"]
                )

            if st.form_submit_button("Create User", type="primary"):
                if new_pass != new_pass2:
                    st.error("Passwords do not match.")
                elif not new_username or not new_pass:
                    st.error("Username and password are required.")
                else:
                    ok = auth_mgr.create_user(
                        new_username, new_pass,
                        new_fullname, new_email, new_role
                    )
                    if ok:
                        st.success(
                            f"✅ User '{new_username}' created."
                        )
                    else:
                        st.error("Username already exists.")

    with tabs[2]:
        with st.form("reset_password"):
            all_users = auth_mgr.get_all_users()
            target_user = st.selectbox(
                "Select User",
                [u['username'] for u in all_users]
            )
            new_p = st.text_input("New Password", type="password")
            new_p2 = st.text_input(
                "Confirm Password", type="password"
            )
            if st.form_submit_button("Reset Password"):
                if new_p != new_p2:
                    st.error("Passwords do not match.")
                else:
                    auth_mgr.update_password(target_user, new_p)
                    st.success(
                        f"✅ Password reset for {target_user}"
                    )


# ── UPLOAD TEMPLATES ──────────────────────────────────
def render_templates():
    tmpl_gen = TemplateGenerator()
    st.markdown(
        "### 📥 Download Upload Templates"
    )
    st.info(
        "Download these templates, fill with your data, "
        "and upload through the corresponding module."
    )

    for tmpl in tmpl_gen.get_template_list():
        with st.expander(
            f"📄 {tmpl['title']} ({tmpl['columns']} columns)"
        ):
            col1, col2 = st.columns([3, 1])
            col1.write(
                f"Template for uploading "
                f"**{tmpl['key'].replace('_', ' ').title()}** data."
            )
            data = tmpl_gen.generate_template(tmpl['key'])
            col2.download_button(
                "⬇️ Download",
                data=data,
                file_name=f"{tmpl['key']}_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"dl_{tmpl['key']}"
            )


# ── AUDIT ENGINE ──────────────────────────────────────
def render_audit_engine():
    db = get_db()
    st.markdown("### 🔍 Audit Engine — Excel Comparison")

    col1, col2 = st.columns(2)
    with col1:
        file1 = st.file_uploader(
            "📄 File 1 (Baseline)",
            type=['xlsx', 'xls'],
            key='audit_f1'
        )
    with col2:
        file2 = st.file_uploader(
            "📄 File 2 (Comparison)",
            type=['xlsx', 'xls'],
            key='audit_f2'
        )

    if file1 and file2:
        df1 = pd.read_excel(file1)
        df2 = pd.read_excel(file2)

        common_cols = list(set(df1.columns) & set(df2.columns))
        pkey = st.selectbox("Primary Key Column", common_cols)
        tolerance = st.slider(
            "Numeric Tolerance (%)", 0.0, 10.0, 1.0, 0.1
        )

        if st.button("🚀 Run Audit", type="primary"):
            df1[pkey] = df1[pkey].astype(str).str.strip()
            df2[pkey] = df2[pkey].astype(str).str.strip()

            merged = df1.merge(
                df2, on=pkey, how='outer',
                suffixes=('_File1', '_File2'),
                indicator=True
            )

            added = merged[merged['_merge'] == 'right_only']
            removed = merged[merged['_merge'] == 'left_only']
            common = merged[merged['_merge'] == 'both']

            differences = []
            for _, row in common.iterrows():
                for col in df1.columns:
                    if col == pkey:
                        continue
                    c1 = f"{col}_File1"
                    c2 = f"{col}_File2"
                    if c1 not in row or c2 not in row:
                        continue
                    v1, v2 = row[c1], row[c2]
                    if pd.isna(v1) and pd.isna(v2):
                        continue
                    if str(v1) != str(v2):
                        try:
                            pct = abs(
                                (float(v2) - float(v1))
                                / max(abs(float(v1)), 1e-10) * 100
                            )
                            sev = (
                                'HIGH' if pct > 10
                                else 'MEDIUM' if pct > tolerance
                                else 'LOW'
                            )
                        except Exception:
                            sev = 'MEDIUM'
                            pct = None

                        differences.append({
                            'Key': row[pkey],
                            'Column': col,
                            'File1': v1,
                            'File2': v2,
                            'Variance%': pct,
                            'Severity': sev
                        })

            diff_df = pd.DataFrame(differences)

            # KPIs
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Common Records", len(common))
            c2.metric("Differences", len(diff_df))
            c3.metric("Added", len(added))
            c4.metric("Removed", len(removed))

            if not diff_df.empty:
                st.markdown("### 🚨 Differences Found")
                import plotly.express as px
                fig = px.bar(
                    diff_df['Severity'].value_counts().reset_index(),
                    x='Severity',
                    y='count',
                    color='Severity',
                    color_discrete_map={
                        'HIGH': '#e74c3c',
                        'MEDIUM': '#f39c12',
                        'LOW': '#3498db'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(diff_df, use_container_width=True)
            else:
                st.success("✅ Files match within tolerance!")


# ════════════════════════════════════════════════════
# MAIN ROUTER
# ════════════════════════════════════════════════════
module_map = {
    'Dashboard': render_dashboard,
    'Assignments': render_assignments,
    'Inventory & Bin Cards': render_inventory,
    'Purchase Ledger': render_purchase_ledger,
    'Expenses': render_expenses,
    'Journal Entries': render_journals,
    'Data Converter': render_data_converter,
    'Financial Statements': render_financial_statements,
    'Trial Balance': render_trial_balance,
    'Audit Engine': render_audit_engine,
    'Data Manager': render_data_manager,
    'Upload Templates': render_templates,
    'User Management': render_user_management
}

renderer = module_map.get(module, render_dashboard)
renderer()