# 🔍 Python Auditor — Automated Excel Comparison & Audit Tool

## Features
| Feature | Description |
|---|---|
| 📁 Multi-File Upload | Upload 2–10 Excel workbooks simultaneously |
| 🔍 Smart Scanner | Auto-classifies workbook types & detects primary keys |
| ⚖️ Audit Engine | Outer-join comparison with tolerance-based flagging |
| 🚨 Severity Flagging | HIGH / MEDIUM / LOW discrepancy classification |
| 📦 FIFO Costing | Full FIFO inventory layer tracking & COGS calculation |
| 📊 Visual Analytics | Donut, waterfall, heatmap, scatter & bar charts |
| 📥 Report Export | Styled multi-sheet Excel + CSV + JSON reports |

## Quick Start

### 1. Clone & Install
git clone https://github.com/your-username/python-auditor.git
cd python-auditor
pip install -r requirements.txt

### 2. Run Locally
streamlit run app.py

### 3. Deploy to Streamlit Cloud
- Push to GitHub
- Go to share.streamlit.io
- Connect repo → set Main file: app.py → Deploy

## Usage Guide

### Two-File Comparison
1. Upload File 1 (baseline) and File 2 (revised)
2. Select the sheet and primary key column
3. Click **Run Audit**
4. Review KPIs, charts, flagged findings
5. Download Excel/CSV/JSON report

### Multi-File Reconciliation
1. Upload 2–10 Excel files
2. Configure primary key (common across all files)
3. Run audit → view reconciliation matrix

### FIFO Inventory Costing
1. Upload inventory transaction file
2. Map columns: Date, Type, Qty, Unit Cost, Item
3. Run → view COGS, ending inventory layers & charts