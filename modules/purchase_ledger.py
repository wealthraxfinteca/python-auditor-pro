"""
Purchase Ledger Module
Manages purchases, AP ledger, purchase returns, and journal postings
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from modules.database import DatabaseManager
from modules.bin_card import BinCardManager
import logging

logger = logging.getLogger(__name__)


class PurchaseLedgerManager:
    """
    Full purchase ledger with AP tracking, invoice management,
    automated journal creation, and bin card integration.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db
        self.bin_card = BinCardManager(db)

    def _next_purchase_number(self) -> str:
        rows = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM purchases"
        )
        n = rows[0]['cnt'] + 1 if rows else 1
        return f"PO-{n:06d}"

    def _next_return_number(self) -> str:
        rows = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM purchase_returns"
        )
        n = rows[0]['cnt'] + 1 if rows else 1
        return f"PR-{n:06d}"

    def _next_journal_number(self) -> str:
        rows = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM journal_entries"
        )
        n = rows[0]['cnt'] + 1 if rows else 1
        return f"JE-{n:06d}"

    # ─── Create Purchase ───────────────────────────
    def create_purchase(self, purchase_data: Dict) -> int:
        """Create a purchase record (unposted)."""
        total = (
            purchase_data['quantity'] * purchase_data['unit_cost']
        )
        tax = purchase_data.get('tax_amount', 0)
        discount = purchase_data.get('discount_amount', 0)
        net = total + tax - discount

        po_num = self._next_purchase_number()
        purchase_id = self.db.execute_write("""
            INSERT INTO purchases
            (purchase_number, purchase_date, supplier_code,
             supplier_name, invoice_number, invoice_date,
             due_date, item_code, item_description,
             quantity, unit_cost, total_amount, tax_amount,
             discount_amount, net_amount, account_code,
             warehouse, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            po_num,
            purchase_data['purchase_date'],
            purchase_data.get('supplier_code', ''),
            purchase_data['supplier_name'],
            purchase_data.get('invoice_number', ''),
            purchase_data.get('invoice_date', ''),
            purchase_data.get('due_date', ''),
            purchase_data.get('item_code', ''),
            purchase_data['item_description'],
            purchase_data['quantity'],
            purchase_data['unit_cost'],
            total, tax, discount, net,
            purchase_data.get('account_code', '1300'),
            purchase_data.get('warehouse', 'MAIN'),
            purchase_data.get('notes', '')
        ))
        return purchase_id

    # ─── Post Purchase (creates JE + Bin Card) ─────
    def post_purchase(
        self,
        purchase_id: int,
        posted_by: str
    ) -> Dict:
        """
        Post a purchase: creates double-entry journal,
        updates bin card, and updates purchase ledger.
        """
        purch = self.db.execute_query(
            "SELECT * FROM purchases WHERE id=?",
            (purchase_id,)
        )
        if not purch:
            raise ValueError(f"Purchase {purchase_id} not found")

        p = purch[0]
        if p['is_posted']:
            raise ValueError(f"Purchase {p['purchase_number']} already posted")

        # 1. Create Journal Entry
        je_num = self._next_journal_number()
        je_id = self.db.execute_write("""
            INSERT INTO journal_entries
            (entry_number, entry_date, description,
             reference, entry_type, source_module,
             is_posted, created_by, posted_by,
             posted_at, period)
            VALUES (?,?,?,?,?,?,1,?,?,?,?)
        """, (
            je_num,
            p['purchase_date'],
            f"Purchase: {p['item_description']} from {p['supplier_name']}",
            p['purchase_number'],
            'PURCHASE',
            'PURCHASE_LEDGER',
            posted_by,
            posted_by,
            datetime.now().isoformat(),
            p['purchase_date'][:7]
        ))

        # 2. Journal Lines: DR Inventory / CR Accounts Payable
        lines = [
            # Debit: Inventory (asset increases)
            (je_id, 1, p['account_code'] or '1300',
             'Inventory / Purchases',
             p['net_amount'], 0,
             f"Purchase: {p['item_description']}"),
            # Credit: Accounts Payable (liability increases)
            (je_id, 2, '2110',
             'Trade Payables',
             0, p['net_amount'],
             f"AP: {p['supplier_name']} - {p['invoice_number']}")
        ]

        # Tax line if applicable
        if p.get('tax_amount', 0) > 0:
            lines[0] = (
                je_id, 1, '1300', 'Inventory',
                p['total_amount'], 0, f"Purchase: {p['item_description']}"
            )
            lines.append((
                je_id, 3, '2310', 'VAT/Tax Payable',
                0, p['tax_amount'],
                f"Tax on purchase {p['purchase_number']}"
            ))

        self.db.execute_many("""
            INSERT INTO journal_lines
            (entry_id, line_number, account_code, account_name,
             debit_amount, credit_amount, description)
            VALUES (?,?,?,?,?,?,?)
        """, lines)

        # 3. Post to Bin Card (if inventory item)
        if p.get('item_code'):
            self.bin_card.post_receipt(
                item_code=p['item_code'],
                item_description=p['item_description'],
                quantity=p['quantity'],
                unit_cost=p['unit_cost'],
                transaction_date=p['purchase_date'],
                reference=p['purchase_number'],
                warehouse=p.get('warehouse', 'MAIN')
            )

        # 4. Update Purchase Ledger (AP ledger)
        self._post_to_purchase_ledger(p, je_id, 'INVOICE')

        # 5. Mark purchase as posted
        self.db.execute_write("""
            UPDATE purchases
            SET is_posted=1, status='POSTED', journal_entry_id=?
            WHERE id=?
        """, (je_id, purchase_id))

        # 6. Update supplier balance
        self._update_supplier_balance(
            p['supplier_name'], p['net_amount']
        )

        self.db.log_action(
            posted_by, 'PURCHASE_LEDGER',
            'POST_PURCHASE',
            str(purchase_id),
            new_vals={'journal_entry': je_num}
        )

        return {
            'purchase_number': p['purchase_number'],
            'journal_entry': je_num,
            'net_amount': p['net_amount']
        }

    # ─── Purchase Returns ──────────────────────────
    def create_purchase_return(
        self,
        return_data: Dict,
        posted_by: str
    ) -> Dict:
        """Create and post a purchase return."""
        ret_num = self._next_return_number()
        total = (
            return_data['quantity_returned']
            * return_data['unit_cost']
        )

        ret_id = self.db.execute_write("""
            INSERT INTO purchase_returns
            (return_number, return_date, original_purchase_id,
             supplier_name, item_code, item_description,
             quantity_returned, unit_cost, total_return_amount,
             reason, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            ret_num,
            return_data['return_date'],
            return_data.get('original_purchase_id'),
            return_data['supplier_name'],
            return_data.get('item_code', ''),
            return_data.get('item_description', ''),
            return_data['quantity_returned'],
            return_data['unit_cost'],
            total,
            return_data.get('reason', ''),
            'PENDING'
        ))

        # Auto-post return
        je_num = self._next_journal_number()
        je_id = self.db.execute_write("""
            INSERT INTO journal_entries
            (entry_number, entry_date, description,
             reference, entry_type, source_module,
             is_posted, created_by, posted_by, posted_at)
            VALUES (?,?,?,?,?,?,1,?,?,?)
        """, (
            je_num,
            return_data['return_date'],
            f"Purchase Return: {return_data.get('item_description','')} "
            f"to {return_data['supplier_name']}",
            ret_num,
            'PURCHASE_RETURN',
            'PURCHASE_LEDGER',
            posted_by,
            posted_by,
            datetime.now().isoformat()
        ))

        # DR: AP, CR: Inventory (reverse of purchase)
        self.db.execute_many("""
            INSERT INTO journal_lines
            (entry_id, line_number, account_code, account_name,
             debit_amount, credit_amount, description)
            VALUES (?,?,?,?,?,?,?)
        """, [
            (je_id, 1, '2110', 'Trade Payables',
             total, 0, f"Return to {return_data['supplier_name']}"),
            (je_id, 2, '5200', 'Purchase Returns',
             0, total, f"Return: {ret_num}")
        ])

        # Reverse bin card
        if return_data.get('item_code'):
            self.bin_card.post_return(
                item_code=return_data['item_code'],
                quantity=return_data['quantity_returned'],
                unit_cost=return_data['unit_cost'],
                transaction_date=return_data['return_date'],
                reference=ret_num
            )

        # Update AP ledger (debit = reduces payable)
        self._post_to_purchase_ledger(
            {
                'purchase_date': return_data['return_date'],
                'supplier_name': return_data['supplier_name'],
                'purchase_number': ret_num,
                'invoice_number': ret_num,
                'net_amount': total
            },
            je_id,
            'RETURN'
        )

        self.db.execute_write("""
            UPDATE purchase_returns
            SET is_posted=1, status='POSTED', journal_entry_id=?
            WHERE id=?
        """, (je_id, ret_id))

        # Reduce supplier balance
        self._update_supplier_balance(
            return_data['supplier_name'], -total
        )

        return {
            'return_number': ret_num,
            'journal_entry': je_num,
            'total_return_amount': total
        }

    def _post_to_purchase_ledger(
        self,
        purchase: Dict,
        je_id: int,
        trans_type: str
    ):
        """Post entry to AP purchase ledger."""
        # Get current supplier balance
        bal = self.db.execute_query("""
            SELECT running_balance FROM purchase_ledger
            WHERE supplier_name=?
            ORDER BY id DESC LIMIT 1
        """, (purchase['supplier_name'],))

        current_bal = bal[0]['running_balance'] if bal else 0

        if trans_type == 'INVOICE':
            debit = 0
            credit = purchase['net_amount']
            new_bal = current_bal + credit
        else:  # RETURN or PAYMENT
            debit = purchase['net_amount']
            credit = 0
            new_bal = current_bal - debit

        self.db.execute_write("""
            INSERT INTO purchase_ledger
            (transaction_date, supplier_name,
             transaction_type, reference_number,
             invoice_number, debit_amount, credit_amount,
             running_balance, journal_entry_id, description)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            purchase.get('purchase_date',
                         datetime.now().strftime('%Y-%m-%d')),
            purchase['supplier_name'],
            trans_type,
            purchase.get('purchase_number', ''),
            purchase.get('invoice_number', ''),
            debit, credit, new_bal,
            je_id,
            f"{trans_type}: {purchase.get('item_description', '')}"
        ))

    def _update_supplier_balance(
        self,
        supplier_name: str,
        amount: float
    ):
        """Update supplier current balance."""
        self.db.execute_write("""
            UPDATE suppliers
            SET current_balance = current_balance + ?
            WHERE supplier_name=?
        """, (amount, supplier_name))

    # ─── Queries ───────────────────────────────────
    def get_purchase_ledger(
        self,
        supplier_name: str = None
    ) -> pd.DataFrame:
        """Get purchase ledger / AP ledger."""
        if supplier_name:
            return self.db.query_to_df("""
                SELECT
                    transaction_date as Date,
                    supplier_name as Supplier,
                    transaction_type as Type,
                    reference_number as Reference,
                    invoice_number as Invoice,
                    debit_amount as Debit,
                    credit_amount as Credit,
                    running_balance as Balance,
                    description as Description,
                    payment_status as Status
                FROM purchase_ledger
                WHERE supplier_name=?
                ORDER BY id ASC
            """, (supplier_name,))
        return self.db.query_to_df("""
            SELECT
                transaction_date as Date,
                supplier_name as Supplier,
                transaction_type as Type,
                reference_number as Reference,
                invoice_number as Invoice,
                debit_amount as Debit,
                credit_amount as Credit,
                running_balance as Balance,
                payment_status as Status
            FROM purchase_ledger
            ORDER BY id ASC
        """)

    def get_ap_aging(self) -> pd.DataFrame:
        """Calculate AP aging buckets."""
        return self.db.query_to_df("""
            SELECT
                pl.supplier_name as Supplier,
                SUM(CASE WHEN pl.running_balance > 0
                         THEN pl.running_balance ELSE 0 END) as Total_Balance,
                SUM(CASE WHEN
                    julianday('now') - julianday(pl.transaction_date) <= 30
                    AND pl.running_balance > 0
                    THEN pl.credit_amount ELSE 0 END) as "0-30 Days",
                SUM(CASE WHEN
                    julianday('now') - julianday(pl.transaction_date) BETWEEN 31 AND 60
                    AND pl.running_balance > 0
                    THEN pl.credit_amount ELSE 0 END) as "31-60 Days",
                SUM(CASE WHEN
                    julianday('now') - julianday(pl.transaction_date) BETWEEN 61 AND 90
                    AND pl.running_balance > 0
                    THEN pl.credit_amount ELSE 0 END) as "61-90 Days",
                SUM(CASE WHEN
                    julianday('now') - julianday(pl.transaction_date) > 90
                    AND pl.running_balance > 0
                    THEN pl.credit_amount ELSE 0 END) as "90+ Days"
            FROM purchase_ledger pl
            GROUP BY pl.supplier_name
            HAVING Total_Balance > 0
        """)