"""
Data Converter Module
Converts single-entry, scanned, or raw data to double-entry journals.
Auto-sets the second leg of transactions.
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from modules.database import DatabaseManager
import logging

logger = logging.getLogger(__name__)


# ─── Transaction Type Rules ────────────────────────
DOUBLE_ENTRY_RULES = {
    'CASH_SALE': {
        'description': 'Cash Sale',
        'debit_account': '1110',
        'debit_label': 'Cash on Hand',
        'credit_account': '4100',
        'credit_label': 'Sales Revenue'
    },
    'CREDIT_SALE': {
        'description': 'Credit Sale',
        'debit_account': '1210',
        'debit_label': 'Trade Receivables',
        'credit_account': '4100',
        'credit_label': 'Sales Revenue'
    },
    'CASH_PURCHASE': {
        'description': 'Cash Purchase',
        'debit_account': '1300',
        'debit_label': 'Inventory',
        'credit_account': '1120',
        'credit_label': 'Bank Account'
    },
    'CREDIT_PURCHASE': {
        'description': 'Credit Purchase',
        'debit_account': '1300',
        'debit_label': 'Inventory',
        'credit_account': '2110',
        'credit_label': 'Trade Payables'
    },
    'EXPENSE_CASH': {
        'description': 'Cash Expense',
        'debit_account': '6900',
        'debit_label': 'Miscellaneous Expense',
        'credit_account': '1110',
        'credit_label': 'Cash on Hand'
    },
    'EXPENSE_BANK': {
        'description': 'Bank Expense',
        'debit_account': '6900',
        'debit_label': 'Miscellaneous Expense',
        'credit_account': '1120',
        'credit_label': 'Bank Account'
    },
    'PAYMENT_SUPPLIER': {
        'description': 'Payment to Supplier',
        'debit_account': '2110',
        'debit_label': 'Trade Payables',
        'credit_account': '1120',
        'credit_label': 'Bank Account'
    },
    'RECEIPT_CUSTOMER': {
        'description': 'Receipt from Customer',
        'debit_account': '1120',
        'debit_label': 'Bank Account',
        'credit_account': '1210',
        'credit_label': 'Trade Receivables'
    },
    'PAYROLL': {
        'description': 'Payroll Expense',
        'debit_account': '6100',
        'debit_label': 'Salaries & Wages',
        'credit_account': '1120',
        'credit_label': 'Bank Account'
    },
    'DEPRECIATION': {
        'description': 'Depreciation',
        'debit_account': '6400',
        'debit_label': 'Depreciation Expense',
        'credit_account': '1590',
        'credit_label': 'Accumulated Depreciation'
    },
    'PURCHASE_RETURN': {
        'description': 'Purchase Return',
        'debit_account': '2110',
        'debit_label': 'Trade Payables',
        'credit_account': '5200',
        'credit_label': 'Purchase Returns'
    }
}


class DataConverter:
    """
    Converts raw/single-entry/scanned data to double-entry journals.
    Supports batch upload via templates.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    def convert_single_entry(
        self,
        raw_df: pd.DataFrame,
        transaction_type: str,
        date_col: str,
        amount_col: str,
        description_col: str = None,
        reference_col: str = None,
        override_debit_account: str = None,
        override_credit_account: str = None
    ) -> pd.DataFrame:
        """
        Convert a DataFrame of single-entry transactions
        to double-entry format.
        """
        if transaction_type not in DOUBLE_ENTRY_RULES:
            raise ValueError(
                f"Unknown transaction type: {transaction_type}"
            )

        rule = DOUBLE_ENTRY_RULES[transaction_type].copy()

        # Apply overrides
        if override_debit_account:
            rule['debit_account'] = override_debit_account
        if override_credit_account:
            rule['credit_account'] = override_credit_account

        double_entries = []
        for idx, row in raw_df.iterrows():
            amount = float(row[amount_col]) if pd.notna(
                row[amount_col]
            ) else 0

            if amount == 0:
                continue

            date_val = str(row[date_col])
            desc = (
                str(row[description_col])
                if description_col and description_col in row
                else rule['description']
            )
            ref = (
                str(row[reference_col])
                if reference_col and reference_col in row
                else f"CONV-{idx+1:04d}"
            )

            # Build debit leg
            double_entries.append({
                'Date': date_val,
                'Reference': ref,
                'Description': desc,
                'Account_Code': rule['debit_account'],
                'Account_Name': rule['debit_label'],
                'Debit': amount,
                'Credit': 0,
                'Transaction_Type': transaction_type,
                'Leg': 'DEBIT',
                'Source': 'CONVERTED'
            })

            # Build credit leg (auto second-leg)
            double_entries.append({
                'Date': date_val,
                'Reference': ref,
                'Description': desc,
                'Account_Code': rule['credit_account'],
                'Account_Name': rule['credit_label'],
                'Debit': 0,
                'Credit': amount,
                'Transaction_Type': transaction_type,
                'Leg': 'CREDIT',
                'Source': 'CONVERTED'
            })

        return pd.DataFrame(double_entries)

    def post_converted_entries(
        self,
        converted_df: pd.DataFrame,
        posted_by: str
    ) -> int:
        """Post converted double-entry records to journal."""
        if converted_df.empty:
            return 0

        refs = converted_df['Reference'].unique()
        posted_count = 0

        rows = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM journal_entries"
        )
        n = rows[0]['cnt'] if rows else 0

        for ref in refs:
            group = converted_df[converted_df['Reference'] == ref]
            dr_total = group['Debit'].sum()
            cr_total = group['Credit'].sum()

            if abs(dr_total - cr_total) > 0.01:
                logger.warning(
                    f"Imbalanced entry for ref {ref}: "
                    f"DR={dr_total}, CR={cr_total}"
                )
                continue

            n += 1
            je_num = f"CONV-{n:06d}"
            date_val = group['Date'].iloc[0]
            desc = group['Description'].iloc[0]

            je_id = self.db.execute_write("""
                INSERT INTO journal_entries
                (entry_number, entry_date, description,
                 reference, entry_type, source_module,
                 is_posted, created_by, posted_by, posted_at)
                VALUES (?,?,?,?,?,?,1,?,?,?)
            """, (
                je_num, date_val, desc, ref,
                group['Transaction_Type'].iloc[0],
                'DATA_CONVERTER',
                posted_by, posted_by,
                datetime.now().isoformat()
            ))

            for _, line in group.iterrows():
                self.db.execute_write("""
                    INSERT INTO journal_lines
                    (entry_id, account_code, account_name,
                     debit_amount, credit_amount, description)
                    VALUES (?,?,?,?,?,?)
                """, (
                    je_id,
                    line['Account_Code'],
                    line['Account_Name'],
                    line['Debit'],
                    line['Credit'],
                    line['Description']
                ))

            posted_count += 1

        return posted_count

    def detect_transaction_type(
        self,
        df: pd.DataFrame
    ) -> str:
        """Heuristically detect transaction type from columns."""
        cols_lower = [c.lower() for c in df.columns]

        if any('sale' in c or 'revenue' in c for c in cols_lower):
            return 'CASH_SALE'
        if any('purchase' in c or 'supplier' in c for c in cols_lower):
            return 'CREDIT_PURCHASE'
        if any('expense' in c or 'cost' in c for c in cols_lower):
            return 'EXPENSE_BANK'
        if any('payroll' in c or 'salary' in c for c in cols_lower):
            return 'PAYROLL'
        return 'EXPENSE_BANK'

    def get_available_rules(self) -> List[Dict]:
        """Return list of available transaction type rules."""
        return [
            {
                'type': k,
                'description': v['description'],
                'debit': f"{v['debit_account']} {v['debit_label']}",
                'credit': f"{v['credit_account']} {v['credit_label']}"
            }
            for k, v in DOUBLE_ENTRY_RULES.items()
        ]