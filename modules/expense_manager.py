cat > modules/expense_manager.py << 'EOF'
"""
Expense Manager Module
"""
import pandas as pd
from datetime import datetime
from typing import Dict
from modules.database import DatabaseManager


class ExpenseManager:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_expenses(self) -> pd.DataFrame:
        return self.db.query_to_df("""
            SELECT expense_number, expense_date,
                   expense_category, description,
                   vendor_name, amount, tax_amount,
                   total_amount, payment_method, status
            FROM expenses ORDER BY expense_date DESC
        """)

    def get_expense_summary(self) -> Dict:
        rows = self.db.execute_query("""
            SELECT
                COUNT(*) as total_count,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(CASE WHEN status='POSTED'
                    THEN total_amount ELSE 0 END), 0) as posted_amount
            FROM expenses
        """)
        return rows[0] if rows else {}

    def get_expenses_by_category(self) -> pd.DataFrame:
        return self.db.query_to_df("""
            SELECT expense_category as Category,
                   COUNT(*) as Count,
                   SUM(total_amount) as Total
            FROM expenses
            GROUP BY expense_category
            ORDER BY Total DESC
        """)
EOF