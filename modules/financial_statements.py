"""
Financial Statements Module
Generates GAAP/IFRS compliant financial statements
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple
from modules.database import DatabaseManager
import logging

logger = logging.getLogger(__name__)


class FinancialStatementsEngine:
    """
    Generates complete GAAP/IFRS financial statements from
    posted journal entries and general ledger.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    # ─── General Ledger ────────────────────────────
    def get_general_ledger(
        self,
        from_date: str = None,
        to_date: str = None,
        account_code: str = None
    ) -> pd.DataFrame:
        """Extract general ledger from posted journal entries."""
        conditions = ["je.is_posted = 1"]
        params = []

        if from_date:
            conditions.append("je.entry_date >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("je.entry_date <= ?")
            params.append(to_date)
        if account_code:
            conditions.append("jl.account_code = ?")
            params.append(account_code)

        where = " AND ".join(conditions)

        return self.db.query_to_df(f"""
            SELECT
                je.entry_date as Date,
                je.entry_number as "Entry No",
                jl.account_code as "Account Code",
                jl.account_name as "Account Name",
                je.description as Description,
                je.reference as Reference,
                jl.debit_amount as Debit,
                jl.credit_amount as Credit,
                je.entry_type as Type,
                je.source_module as Source
            FROM journal_entries je
            JOIN journal_lines jl ON je.id = jl.entry_id
            WHERE {where}
            ORDER BY je.entry_date ASC, je.id ASC
        """, tuple(params))

    # ─── Trial Balance ─────────────────────────────
    def get_trial_balance(
        self,
        from_date: str = None,
        to_date: str = None
    ) -> pd.DataFrame:
        """Generate trial balance from posted journals."""
        conditions = ["je.is_posted = 1"]
        params = []
        if from_date:
            conditions.append("je.entry_date >= ?")
            params.append(from_date)
        if to_date:
            conditions.append("je.entry_date <= ?")
            params.append(to_date)

        where = " AND ".join(conditions)

        tb = self.db.query_to_df(f"""
            SELECT
                coa.account_code as "Account Code",
                coa.account_name as "Account Name",
                coa.account_type as "Account Type",
                coa.account_category as "Category",
                coa.normal_balance as "Normal Balance",
                COALESCE(SUM(jl.debit_amount), 0) as "Total Debits",
                COALESCE(SUM(jl.credit_amount), 0) as "Total Credits",
                COALESCE(SUM(jl.debit_amount), 0) -
                COALESCE(SUM(jl.credit_amount), 0) as "Net Balance",
                CASE
                    WHEN coa.normal_balance = 'DEBIT'
                    THEN COALESCE(SUM(jl.debit_amount), 0) -
                         COALESCE(SUM(jl.credit_amount), 0)
                    ELSE COALESCE(SUM(jl.credit_amount), 0) -
                         COALESCE(SUM(jl.debit_amount), 0)
                END as "Closing Balance"
            FROM chart_of_accounts coa
            LEFT JOIN journal_lines jl
                ON coa.account_code = jl.account_code
            LEFT JOIN journal_entries je
                ON jl.entry_id = je.id AND {where}
            WHERE coa.is_active = 1
              AND coa.parent_code IS NOT NULL
            GROUP BY coa.account_code, coa.account_name,
                     coa.account_type, coa.account_category,
                     coa.normal_balance
            ORDER BY coa.account_code
        """, tuple(params * 2))

        # Check balance
        total_dr = tb["Total Debits"].sum()
        total_cr = tb["Total Credits"].sum()
        tb.attrs['total_debits'] = total_dr
        tb.attrs['total_credits'] = total_cr
        tb.attrs['balanced'] = abs(total_dr - total_cr) < 0.01

        return tb

    # ─── Income Statement ──────────────────────────
    def get_income_statement(
        self,
        from_date: str,
        to_date: str
    ) -> Dict:
        """Generate P&L / Income Statement."""
        tb = self.get_trial_balance(from_date, to_date)

        revenue_df = tb[
            tb['Account Type'].isin(['Revenue'])
        ].copy()
        cogs_df = tb[
            tb['Account Code'].str.startswith('5')
        ].copy()
        expense_df = tb[
            tb['Account Code'].str.startswith('6') |
            tb['Account Code'].str.startswith('7')
        ].copy()

        total_revenue = revenue_df['Closing Balance'].sum()
        total_cogs = cogs_df['Closing Balance'].sum()
        gross_profit = total_revenue - total_cogs
        gross_margin = (
            (gross_profit / total_revenue * 100)
            if total_revenue != 0 else 0
        )

        total_expenses = expense_df['Closing Balance'].sum()
        operating_profit = gross_profit - total_expenses
        net_income = operating_profit  # (simplified)

        return {
            'revenue': revenue_df,
            'cogs': cogs_df,
            'expenses': expense_df,
            'totals': {
                'total_revenue': total_revenue,
                'total_cogs': total_cogs,
                'gross_profit': gross_profit,
                'gross_margin_pct': gross_margin,
                'total_expenses': total_expenses,
                'operating_profit': operating_profit,
                'net_income': net_income,
                'period': f"{from_date} to {to_date}"
            }
        }

    # ─── Balance Sheet ─────────────────────────────
    def get_balance_sheet(self, as_of_date: str) -> Dict:
        """Generate Balance Sheet as at a given date."""
        tb = self.get_trial_balance(to_date=as_of_date)

        assets_df = tb[
            tb['Account Type'] == 'Asset'
        ].copy()
        liabilities_df = tb[
            tb['Account Type'] == 'Liability'
        ].copy()
        equity_df = tb[
            tb['Account Type'] == 'Equity'
        ].copy()

        total_assets = assets_df['Closing Balance'].sum()
        total_liabilities = liabilities_df['Closing Balance'].sum()
        total_equity = equity_df['Closing Balance'].sum()

        current_assets = assets_df[
            assets_df['Category'] == 'Current Asset'
        ]['Closing Balance'].sum()
        non_current_assets = assets_df[
            assets_df['Category'] == 'Non-Current Asset'
        ]['Closing Balance'].sum()
        current_liabilities = liabilities_df[
            liabilities_df['Category'] == 'Current Liability'
        ]['Closing Balance'].sum()
        non_current_liabilities = liabilities_df[
            liabilities_df['Category'] == 'Non-Current Liability'
        ]['Closing Balance'].sum()

        return {
            'assets': assets_df,
            'liabilities': liabilities_df,
            'equity': equity_df,
            'totals': {
                'total_assets': total_assets,
                'total_liabilities': total_liabilities,
                'total_equity': total_equity,
                'total_liab_equity': total_liabilities + total_equity,
                'current_assets': current_assets,
                'non_current_assets': non_current_assets,
                'current_liabilities': current_liabilities,
                'non_current_liabilities': non_current_liabilities,
                'working_capital': current_assets - current_liabilities,
                'current_ratio': (
                    current_assets / current_liabilities
                    if current_liabilities != 0 else 0
                ),
                'as_of_date': as_of_date,
                'balanced': abs(
                    total_assets - (total_liabilities + total_equity)
                ) < 0.01
            }
        }

    # ─── Cash Flow (Indirect Method) ───────────────
    def get_cash_flow_statement(
        self,
        from_date: str,
        to_date: str
    ) -> Dict:
        """Generate Cash Flow Statement (Indirect Method)."""
        is_data = self.get_income_statement(from_date, to_date)
        net_income = is_data['totals']['net_income']

        # Cash from operations (simplified)
        ap_change = self.db.execute_query("""
            SELECT COALESCE(SUM(credit_amount - debit_amount), 0) as ap
            FROM purchase_ledger
            WHERE transaction_date BETWEEN ? AND ?
        """, (from_date, to_date))

        inv_change = self.db.execute_query("""
            SELECT COALESCE(SUM(qty_in - qty_out) * unit_cost, 0) as inv
            FROM bin_cards
            WHERE transaction_date BETWEEN ? AND ?
        """, (from_date, to_date))

        ap_val = ap_change[0]['ap'] if ap_change else 0
        inv_val = -(inv_change[0]['inv'] if inv_change else 0)

        operating_cash = net_income + ap_val + inv_val

        return {
            'operating': {
                'net_income': net_income,
                'ap_changes': ap_val,
                'inventory_changes': inv_val,
                'net_operating': operating_cash
            },
            'investing': {
                'capex': 0,
                'net_investing': 0
            },
            'financing': {
                'loan_proceeds': 0,
                'dividends': 0,
                'net_financing': 0
            },
            'net_change': operating_cash,
            'period': f"{from_date} to {to_date}"
        }