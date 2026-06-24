cat > modules/data_manager.py << 'EOF'
"""
Data Manager Module
"""
import pandas as pd
from typing import Dict, List
from modules.database import DatabaseManager


class DataManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_all_journals(self) -> pd.DataFrame:
        return self.db.query_to_df("""
            SELECT je.id, je.entry_number, je.entry_date,
                   je.description, je.entry_type,
                   je.source_module, je.is_posted,
                   je.is_reversed,
                   COUNT(jl.id) as line_count,
                   SUM(jl.debit_amount) as total_debits,
                   SUM(jl.credit_amount) as total_credits
            FROM journal_entries je
            LEFT JOIN journal_lines jl ON je.id = jl.entry_id
            GROUP BY je.id
            ORDER BY je.id DESC
        """)

    def get_journal_lines(self, entry_id: int) -> pd.DataFrame:
        return self.db.query_to_df("""
            SELECT line_number, account_code, account_name,
                   debit_amount, credit_amount, description
            FROM journal_lines
            WHERE entry_id = ?
            ORDER BY line_number
        """, (entry_id,))

    def get_audit_trail(self, limit: int = 200) -> pd.DataFrame:
        return self.db.query_to_df(f"""
            SELECT action_date, user_name, module,
                   action, record_id
            FROM audit_log
            ORDER BY id DESC
            LIMIT {limit}
        """)

    def update_unposted_purchase(
        self,
        purchase_id: int,
        updates: Dict,
        user: str
    ) -> bool:
        old = self.db.execute_query(
            "SELECT * FROM purchases WHERE id=? AND is_posted=0",
            (purchase_id,)
        )
        if not old:
            return False

        self.db.execute_write("""
            UPDATE purchases
            SET quantity=?, unit_cost=?,
                net_amount=?, total_amount=?,
                supplier_name=?, item_description=?
            WHERE id=? AND is_posted=0
        """, (
            updates.get('quantity'),
            updates.get('unit_cost'),
            updates.get('net_amount'),
            updates.get('net_amount'),
            updates.get('supplier_name'),
            updates.get('item_description'),
            purchase_id
        ))

        self.db.log_action(
            user, 'DATA_MANAGER',
            'EDIT_PURCHASE', str(purchase_id),
            old_vals=old[0], new_vals=updates
        )
        return True

    def void_journal_entry(
        self,
        entry_id: int,
        reason: str,
        user: str
    ) -> str:
        from datetime import datetime
        original_lines = self.db.execute_query(
            "SELECT * FROM journal_lines WHERE entry_id=?",
            (entry_id,)
        )
        rows = self.db.execute_query(
            "SELECT COUNT(*) cnt FROM journal_entries"
        )
        void_num = f"VOID-{rows[0]['cnt']+1:06d}"

        void_je = self.db.execute_write("""
            INSERT INTO journal_entries
            (entry_number, entry_date, description,
             entry_type, is_posted, reversal_of,
             created_by, posted_by, posted_at)
            VALUES (?,date('now'),?,?,1,?,?,?,?)
        """, (
            void_num,
            f"VOID: {reason}",
            'VOID', entry_id,
            user, user,
            datetime.now().isoformat()
        ))

        for ln in original_lines:
            self.db.execute_write("""
                INSERT INTO journal_lines
                (entry_id, account_code, account_name,
                 debit_amount, credit_amount, description)
                VALUES (?,?,?,?,?,?)
            """, (
                void_je,
                ln['account_code'],
                ln['account_name'],
                ln['credit_amount'],
                ln['debit_amount'],
                f"VOID: {reason}"
            ))

        self.db.execute_write(
            "UPDATE journal_entries SET is_reversed=1 WHERE id=?",
            (entry_id,)
        )

        self.db.log_action(
            user, 'DATA_MANAGER',
            'VOID_JOURNAL', str(entry_id),
            new_vals={'void_number': void_num, 'reason': reason}
        )
        return void_num
EOF