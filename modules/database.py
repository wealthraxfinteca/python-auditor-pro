"""
Database Manager - SQLite per assignment
Each assignment gets its own isolated database
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import pandas as pd
import logging

logger = logging.getLogger(__name__)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


class DatabaseManager:
    """Manages SQLite databases - one per assignment."""

    def __init__(self, assignment_id: str):
        self.assignment_id = assignment_id
        self.db_path = os.path.join(
            DATA_DIR, f"assignment_{assignment_id}.db"
        )
        self._init_database()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        return conn

    def _init_database(self):
        """Initialize all database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Entity particulars
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entity (
                    id INTEGER PRIMARY KEY,
                    entity_name TEXT NOT NULL,
                    entity_type TEXT,
                    registration_number TEXT,
                    tax_number TEXT,
                    address TEXT,
                    city TEXT,
                    country TEXT,
                    phone TEXT,
                    email TEXT,
                    website TEXT,
                    fiscal_year_start TEXT,
                    fiscal_year_end TEXT,
                    currency TEXT DEFAULT 'USD',
                    accounting_standard TEXT DEFAULT 'GAAP',
                    industry TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    logo_path TEXT
                )
            """)

            # Chart of Accounts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chart_of_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_code TEXT UNIQUE NOT NULL,
                    account_name TEXT NOT NULL,
                    account_type TEXT NOT NULL,
                    account_category TEXT,
                    parent_code TEXT,
                    is_control_account INTEGER DEFAULT 0,
                    normal_balance TEXT DEFAULT 'DEBIT',
                    description TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Journal Entries (double-entry)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_number TEXT UNIQUE NOT NULL,
                    entry_date TEXT NOT NULL,
                    description TEXT,
                    reference TEXT,
                    entry_type TEXT DEFAULT 'MANUAL',
                    source_module TEXT,
                    is_posted INTEGER DEFAULT 0,
                    is_reversed INTEGER DEFAULT 0,
                    reversal_of INTEGER,
                    created_by TEXT,
                    posted_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    posted_at TEXT,
                    period TEXT,
                    notes TEXT
                )
            """)

            # Journal Entry Lines
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id INTEGER NOT NULL,
                    line_number INTEGER,
                    account_code TEXT NOT NULL,
                    account_name TEXT,
                    debit_amount REAL DEFAULT 0,
                    credit_amount REAL DEFAULT 0,
                    description TEXT,
                    cost_center TEXT,
                    project_code TEXT,
                    FOREIGN KEY (entry_id)
                        REFERENCES journal_entries(id)
                )
            """)

            # Purchases
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase_number TEXT UNIQUE NOT NULL,
                    purchase_date TEXT NOT NULL,
                    supplier_code TEXT,
                    supplier_name TEXT NOT NULL,
                    invoice_number TEXT,
                    invoice_date TEXT,
                    due_date TEXT,
                    item_code TEXT,
                    item_description TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit_cost REAL NOT NULL,
                    total_amount REAL,
                    tax_amount REAL DEFAULT 0,
                    discount_amount REAL DEFAULT 0,
                    net_amount REAL,
                    account_code TEXT,
                    warehouse TEXT DEFAULT 'MAIN',
                    is_posted INTEGER DEFAULT 0,
                    journal_entry_id INTEGER,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """)

            # Purchase Returns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_returns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    return_number TEXT UNIQUE NOT NULL,
                    return_date TEXT NOT NULL,
                    original_purchase_id INTEGER,
                    supplier_name TEXT NOT NULL,
                    item_code TEXT,
                    item_description TEXT,
                    quantity_returned REAL NOT NULL,
                    unit_cost REAL NOT NULL,
                    total_return_amount REAL,
                    reason TEXT,
                    is_posted INTEGER DEFAULT 0,
                    journal_entry_id INTEGER,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (original_purchase_id)
                        REFERENCES purchases(id)
                )
            """)

            # Bin Cards (Inventory movement cards)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bin_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_date TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    item_description TEXT,
                    warehouse TEXT DEFAULT 'MAIN',
                    bin_location TEXT,
                    transaction_type TEXT NOT NULL,
                    reference_number TEXT,
                    source_document TEXT,
                    qty_in REAL DEFAULT 0,
                    qty_out REAL DEFAULT 0,
                    unit_cost REAL DEFAULT 0,
                    balance_qty REAL DEFAULT 0,
                    balance_value REAL DEFAULT 0,
                    fifo_layer_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT
                )
            """)

            # FIFO Inventory Layers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fifo_layers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT NOT NULL,
                    warehouse TEXT DEFAULT 'MAIN',
                    receipt_date TEXT NOT NULL,
                    reference_number TEXT,
                    original_qty REAL NOT NULL,
                    remaining_qty REAL NOT NULL,
                    unit_cost REAL NOT NULL,
                    layer_value REAL,
                    is_exhausted INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Inventory Master
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS inventory_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_code TEXT UNIQUE NOT NULL,
                    item_description TEXT NOT NULL,
                    item_category TEXT,
                    unit_of_measure TEXT DEFAULT 'UNIT',
                    reorder_level REAL DEFAULT 0,
                    reorder_quantity REAL DEFAULT 0,
                    warehouse TEXT DEFAULT 'MAIN',
                    bin_location TEXT,
                    current_qty REAL DEFAULT 0,
                    average_cost REAL DEFAULT 0,
                    fifo_cost REAL DEFAULT 0,
                    total_value REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Purchase Ledger
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS purchase_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_date TEXT NOT NULL,
                    supplier_code TEXT,
                    supplier_name TEXT NOT NULL,
                    transaction_type TEXT NOT NULL,
                    reference_number TEXT,
                    invoice_number TEXT,
                    debit_amount REAL DEFAULT 0,
                    credit_amount REAL DEFAULT 0,
                    running_balance REAL DEFAULT 0,
                    journal_entry_id INTEGER,
                    purchase_id INTEGER,
                    description TEXT,
                    due_date TEXT,
                    payment_status TEXT DEFAULT 'UNPAID',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Expenses
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    expense_number TEXT UNIQUE NOT NULL,
                    expense_date TEXT NOT NULL,
                    expense_category TEXT NOT NULL,
                    description TEXT NOT NULL,
                    vendor_name TEXT,
                    reference TEXT,
                    amount REAL NOT NULL,
                    tax_amount REAL DEFAULT 0,
                    total_amount REAL,
                    account_code TEXT,
                    cost_center TEXT,
                    is_posted INTEGER DEFAULT 0,
                    journal_entry_id INTEGER,
                    payment_method TEXT,
                    status TEXT DEFAULT 'PENDING',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    receipt_path TEXT,
                    notes TEXT
                )
            """)

            # Suppliers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suppliers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    supplier_code TEXT UNIQUE NOT NULL,
                    supplier_name TEXT NOT NULL,
                    contact_person TEXT,
                    email TEXT,
                    phone TEXT,
                    address TEXT,
                    payment_terms INTEGER DEFAULT 30,
                    currency TEXT DEFAULT 'USD',
                    tax_number TEXT,
                    account_code TEXT,
                    credit_limit REAL DEFAULT 0,
                    current_balance REAL DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Audit Log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    user_name TEXT,
                    module TEXT,
                    action TEXT,
                    record_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT
                )
            """)

            conn.commit()
            self._seed_chart_of_accounts(cursor, conn)

    def _seed_chart_of_accounts(
        self, cursor, conn
    ):
        """Seed a standard chart of accounts if empty."""
        cursor.execute(
            "SELECT COUNT(*) FROM chart_of_accounts"
        )
        if cursor.fetchone()[0] > 0:
            return

        accounts = [
            # ASSETS
            ('1000', 'ASSETS', 'Asset', 'Balance Sheet', None, 'DEBIT'),
            ('1100', 'Cash & Cash Equivalents', 'Asset',
             'Current Asset', '1000', 'DEBIT'),
            ('1110', 'Cash on Hand', 'Asset',
             'Current Asset', '1100', 'DEBIT'),
            ('1120', 'Bank Account - Checking', 'Asset',
             'Current Asset', '1100', 'DEBIT'),
            ('1130', 'Petty Cash', 'Asset',
             'Current Asset', '1100', 'DEBIT'),
            ('1200', 'Accounts Receivable', 'Asset',
             'Current Asset', '1000', 'DEBIT'),
            ('1210', 'Trade Receivables', 'Asset',
             'Current Asset', '1200', 'DEBIT'),
            ('1300', 'Inventory', 'Asset',
             'Current Asset', '1000', 'DEBIT'),
            ('1310', 'Raw Materials', 'Asset',
             'Current Asset', '1300', 'DEBIT'),
            ('1320', 'Finished Goods', 'Asset',
             'Current Asset', '1300', 'DEBIT'),
            ('1400', 'Prepaid Expenses', 'Asset',
             'Current Asset', '1000', 'DEBIT'),
            ('1500', 'Property, Plant & Equipment', 'Asset',
             'Non-Current Asset', '1000', 'DEBIT'),
            ('1510', 'Land & Buildings', 'Asset',
             'Non-Current Asset', '1500', 'DEBIT'),
            ('1520', 'Machinery & Equipment', 'Asset',
             'Non-Current Asset', '1500', 'DEBIT'),
            ('1590', 'Accumulated Depreciation', 'Asset',
             'Non-Current Asset', '1500', 'CREDIT'),
            # LIABILITIES
            ('2000', 'LIABILITIES', 'Liability',
             'Balance Sheet', None, 'CREDIT'),
            ('2100', 'Accounts Payable', 'Liability',
             'Current Liability', '2000', 'CREDIT'),
            ('2110', 'Trade Payables', 'Liability',
             'Current Liability', '2100', 'CREDIT'),
            ('2200', 'Accrued Liabilities', 'Liability',
             'Current Liability', '2000', 'CREDIT'),
            ('2300', 'Tax Payable', 'Liability',
             'Current Liability', '2000', 'CREDIT'),
            ('2310', 'VAT/Sales Tax Payable', 'Liability',
             'Current Liability', '2300', 'CREDIT'),
            ('2400', 'Short-Term Loans', 'Liability',
             'Current Liability', '2000', 'CREDIT'),
            ('2500', 'Long-Term Debt', 'Liability',
             'Non-Current Liability', '2000', 'CREDIT'),
            # EQUITY
            ('3000', 'EQUITY', 'Equity',
             'Balance Sheet', None, 'CREDIT'),
            ('3100', 'Share Capital', 'Equity',
             'Equity', '3000', 'CREDIT'),
            ('3200', 'Retained Earnings', 'Equity',
             'Equity', '3000', 'CREDIT'),
            ('3300', 'Current Year Profit/Loss', 'Equity',
             'Equity', '3000', 'CREDIT'),
            # REVENUE
            ('4000', 'REVENUE', 'Revenue',
             'Income Statement', None, 'CREDIT'),
            ('4100', 'Sales Revenue', 'Revenue',
             'Income Statement', '4000', 'CREDIT'),
            ('4200', 'Service Revenue', 'Revenue',
             'Income Statement', '4000', 'CREDIT'),
            ('4300', 'Other Income', 'Revenue',
             'Income Statement', '4000', 'CREDIT'),
            # COST OF SALES
            ('5000', 'COST OF SALES', 'Expense',
             'Income Statement', None, 'DEBIT'),
            ('5100', 'Cost of Goods Sold', 'Expense',
             'Income Statement', '5000', 'DEBIT'),
            ('5200', 'Purchase Returns', 'Expense',
             'Income Statement', '5000', 'CREDIT'),
            # EXPENSES
            ('6000', 'OPERATING EXPENSES', 'Expense',
             'Income Statement', None, 'DEBIT'),
            ('6100', 'Salaries & Wages', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6200', 'Rent Expense', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6300', 'Utilities Expense', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6400', 'Depreciation Expense', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6500', 'Office Supplies', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6600', 'Marketing & Advertising', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6700', 'Professional Fees', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6800', 'Travel & Entertainment', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('6900', 'Miscellaneous Expense', 'Expense',
             'Income Statement', '6000', 'DEBIT'),
            ('7000', 'FINANCE COSTS', 'Expense',
             'Income Statement', None, 'DEBIT'),
            ('7100', 'Interest Expense', 'Expense',
             'Income Statement', '7000', 'DEBIT'),
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO chart_of_accounts
            (account_code, account_name, account_type,
             account_category, parent_code, normal_balance)
            VALUES (?,?,?,?,?,?)
        """, accounts)
        conn.commit()

    def execute_query(
        self,
        sql: str,
        params: tuple = ()
    ) -> List[Dict]:
        """Execute a SELECT query and return list of dicts."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def execute_write(
        self,
        sql: str,
        params: tuple = ()
    ) -> int:
        """Execute INSERT/UPDATE/DELETE and return lastrowid."""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.lastrowid

    def execute_many(
        self,
        sql: str,
        params_list: List[tuple]
    ):
        """Execute batch write operations."""
        with self.get_connection() as conn:
            conn.executemany(sql, params_list)
            conn.commit()

    def query_to_df(
        self,
        sql: str,
        params: tuple = ()
    ) -> pd.DataFrame:
        """Return query results as DataFrame."""
        with self.get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)

    def log_action(
        self,
        user: str,
        module: str,
        action: str,
        record_id: str = '',
        old_vals: Dict = None,
        new_vals: Dict = None
    ):
        """Write to audit log."""
        self.execute_write("""
            INSERT INTO audit_log
            (user_name, module, action, record_id, old_values, new_values)
            VALUES (?,?,?,?,?,?)
        """, (
            user, module, action, record_id,
            json.dumps(old_vals) if old_vals else None,
            json.dumps(new_vals) if new_vals else None
        ))