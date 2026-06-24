"""
Assignment Manager
Creates and manages audit assignments with entity particulars
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import Dict, List, Optional
import streamlit as st
from modules.database import DatabaseManager

ASSIGN_DB = "data/assignments.db"
os.makedirs("data", exist_ok=True)


class AssignmentManager:
    """Manages audit assignments - each with own database."""

    def __init__(self):
        self._init_assignments_db()

    def _init_assignments_db(self):
        with sqlite3.connect(ASSIGN_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS assignments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    assignment_id TEXT UNIQUE NOT NULL,
                    assignment_name TEXT NOT NULL,
                    assignment_type TEXT,
                    entity_name TEXT NOT NULL,
                    entity_type TEXT,
                    fiscal_year TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    status TEXT DEFAULT 'ACTIVE',
                    created_by TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    description TEXT,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.commit()

    def create_assignment(
        self,
        assignment_name: str,
        entity_name: str,
        entity_data: Dict,
        created_by: str
    ) -> str:
        """Create a new assignment and initialize its database."""
        import uuid
        assignment_id = str(uuid.uuid4())[:8].upper()

        with sqlite3.connect(ASSIGN_DB) as conn:
            conn.execute("""
                INSERT INTO assignments
                (assignment_id, assignment_name, assignment_type,
                 entity_name, entity_type, fiscal_year,
                 start_date, end_date, created_by, description)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                assignment_id,
                assignment_name,
                entity_data.get('assignment_type', 'AUDIT'),
                entity_name,
                entity_data.get('entity_type', 'Company'),
                entity_data.get('fiscal_year', ''),
                entity_data.get('start_date', ''),
                entity_data.get('end_date', ''),
                created_by,
                entity_data.get('description', '')
            ))
            conn.commit()

        # Initialize assignment database & save entity
        db = DatabaseManager(assignment_id)
        db.execute_write("""
            INSERT OR REPLACE INTO entity
            (id, entity_name, entity_type, registration_number,
             tax_number, address, city, country, phone, email,
             website, fiscal_year_start, fiscal_year_end,
             currency, accounting_standard, industry)
            VALUES
            (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            entity_name,
            entity_data.get('entity_type', ''),
            entity_data.get('registration_number', ''),
            entity_data.get('tax_number', ''),
            entity_data.get('address', ''),
            entity_data.get('city', ''),
            entity_data.get('country', ''),
            entity_data.get('phone', ''),
            entity_data.get('email', ''),
            entity_data.get('website', ''),
            entity_data.get('fiscal_year_start', ''),
            entity_data.get('fiscal_year_end', ''),
            entity_data.get('currency', 'USD'),
            entity_data.get('accounting_standard', 'GAAP'),
            entity_data.get('industry', '')
        ))

        return assignment_id

    def get_all_assignments(self) -> List[Dict]:
        with sqlite3.connect(ASSIGN_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM assignments ORDER BY created_at DESC
            """).fetchall()
            return [dict(r) for r in rows]

    def get_assignment(self, assignment_id: str) -> Optional[Dict]:
        with sqlite3.connect(ASSIGN_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM assignments WHERE assignment_id=?
            """, (assignment_id,)).fetchone()
            return dict(row) if row else None

    def update_assignment_status(
        self,
        assignment_id: str,
        status: str
    ):
        with sqlite3.connect(ASSIGN_DB) as conn:
            conn.execute("""
                UPDATE assignments SET status=? WHERE assignment_id=?
            """, (status, assignment_id))
            conn.commit()


def render_assignment_selector(user: Dict) -> Optional[str]:
    """Sidebar assignment selector."""
    mgr = AssignmentManager()
    assignments = mgr.get_all_assignments()

    if not assignments:
        return None

    options = {
        f"{a['assignment_id']} | {a['entity_name']} "
        f"({a['fiscal_year']})": a['assignment_id']
        for a in assignments
        if a['status'] == 'ACTIVE'
    }

    selected = st.sidebar.selectbox(
        "📂 Active Assignment",
        options=list(options.keys()),
        key='assignment_selector'
    )

    return options.get(selected)