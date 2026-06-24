"""
User Authentication Module
Manages users, roles, sessions per assignment
"""

import sqlite3
import hashlib
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Optional
import streamlit as st

AUTH_DB = "data/auth.db"
os.makedirs("data", exist_ok=True)


class AuthManager:
    """Handles user authentication and session management."""

    ROLES = {
        'ADMIN': [
            'all'
        ],
        'AUDITOR': [
            'view', 'upload', 'audit', 'reports'
        ],
        'ACCOUNTANT': [
            'view', 'journal', 'purchases',
            'expenses', 'reports'
        ],
        'VIEWER': [
            'view', 'reports'
        ]
    }

    def __init__(self):
        self._init_auth_db()

    def _init_auth_db(self):
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT,
                    email TEXT,
                    role TEXT DEFAULT 'VIEWER',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_login TEXT,
                    assigned_entities TEXT DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT,
                    session_token TEXT UNIQUE,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            # Create default admin
            admin_hash = self._hash_password("admin123")
            conn.execute("""
                INSERT OR IGNORE INTO users
                (username, password_hash, full_name, role)
                VALUES ('admin', ?, 'System Administrator', 'ADMIN')
            """, (admin_hash,))
            conn.commit()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(
            (password + "pyauditor_salt_2024").encode()
        ).hexdigest()

    def login(
        self,
        username: str,
        password: str
    ) -> Optional[Dict]:
        """Authenticate user and return user info."""
        password_hash = self._hash_password(password)
        with sqlite3.connect(AUTH_DB) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM users
                WHERE username=? AND password_hash=?
                AND is_active=1
            """, (username, password_hash)).fetchone()

            if row:
                user = dict(row)
                user['assigned_entities'] = json.loads(
                    user.get('assigned_entities', '[]')
                )
                conn.execute("""
                    UPDATE users SET last_login=?
                    WHERE username=?
                """, (datetime.now().isoformat(), username))
                conn.commit()
                return user
        return None

    def create_user(
        self,
        username: str,
        password: str,
        full_name: str,
        email: str,
        role: str
    ) -> bool:
        """Create a new user account."""
        try:
            with sqlite3.connect(AUTH_DB) as conn:
                conn.execute("""
                    INSERT INTO users
                    (username, password_hash, full_name, email, role)
                    VALUES (?,?,?,?,?)
                """, (
                    username,
                    self._hash_password(password),
                    full_name,
                    email,
                    role
                ))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_users(self) -> list:
        with sqlite3.connect(AUTH_DB) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id,username,full_name,email,role,"
                "is_active,last_login FROM users"
            ).fetchall()
            return [dict(r) for r in rows]

    def update_password(
        self,
        username: str,
        new_password: str
    ) -> bool:
        with sqlite3.connect(AUTH_DB) as conn:
            conn.execute("""
                UPDATE users SET password_hash=?
                WHERE username=?
            """, (self._hash_password(new_password), username))
            conn.commit()
        return True

    def has_permission(
        self,
        user_role: str,
        permission: str
    ) -> bool:
        perms = self.ROLES.get(user_role, [])
        return 'all' in perms or permission in perms


def render_login_page():
    """Render the login page UI."""
    st.markdown("""
    <div style="
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: linear-gradient(135deg, #1f4e79, #2e75b6);
        padding: 2rem;
    ">
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div style="
            background:white;
            border-radius:16px;
            padding:2.5rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align:center;
        ">
            <h1 style="color:#1f4e79; margin:0; font-size:2rem;">
                🔍 Python Auditor Pro
            </h1>
            <p style="color:#6c757d; margin:0.5rem 0 2rem;">
                Enterprise Financial Audit System
            </p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("### 🔐 Sign In")
            username = st.text_input(
                "Username",
                placeholder="Enter username"
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter password"
            )
            submitted = st.form_submit_button(
                "Sign In",
                use_container_width=True,
                type="primary"
            )

            if submitted:
                auth = AuthManager()
                user = auth.login(username, password)
                if user:
                    st.session_state['user'] = user
                    st.session_state['authenticated'] = True
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")

        st.caption(
            "Default: admin / admin123 — Change on first login"
        )