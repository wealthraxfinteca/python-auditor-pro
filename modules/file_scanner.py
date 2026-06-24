"""
Multi-Source File Directory Scanner
Automatically discovers, classifies, and ingests Excel workbooks
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FileScanner:
    """
    Scans directories or uploaded files, classifies workbooks,
    and extracts structured data for audit processing.
    """

    SUPPORTED_EXTENSIONS = {'.xlsx', '.xls', '.xlsm', '.xlsb'}

    def __init__(self):
        self.scan_report = []
        self.discovered_files = {}
        self.errors = []

    def scan_uploaded_files(
        self,
        uploaded_files: list
    ) -> Dict[str, Dict]:
        """
        Process Streamlit uploaded file objects.
        Returns a structured dictionary of file metadata and DataFrames.
        """
        results = {}

        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            file_ext = Path(file_name).suffix.lower()

            if file_ext not in self.SUPPORTED_EXTENSIONS:
                self.errors.append(
                    f"Unsupported format: {file_name}"
                )
                continue

            try:
                file_info = self._process_excel_file(
                    uploaded_file,
                    file_name
                )
                results[file_name] = file_info
                logger.info(f"Successfully scanned: {file_name}")

            except Exception as e:
                error_msg = f"Error processing {file_name}: {str(e)}"
                self.errors.append(error_msg)
                logger.error(error_msg)

        self.discovered_files = results
        return results

    def scan_directory(self, directory_path: str) -> Dict[str, Dict]:
        """
        Scan a directory for Excel files and process each one.
        """
        results = {}
        directory = Path(directory_path)

        if not directory.exists():
            raise FileNotFoundError(
                f"Directory not found: {directory_path}"
            )

        excel_files = []
        for ext in self.SUPPORTED_EXTENSIONS:
            excel_files.extend(directory.rglob(f"*{ext}"))

        logger.info(
            f"Found {len(excel_files)} Excel files in {directory_path}"
        )

        for file_path in excel_files:
            try:
                with open(file_path, 'rb') as f:
                    file_info = self._process_excel_file(
                        f,
                        file_path.name
                    )
                    results[file_path.name] = file_info

            except Exception as e:
                error_msg = f"Error: {file_path.name}: {str(e)}"
                self.errors.append(error_msg)

        self.discovered_files = results
        return results

    def _process_excel_file(
        self,
        file_obj,
        file_name: str
    ) -> Dict:
        """
        Extract metadata and all sheets from an Excel workbook.
        """
        xl = pd.ExcelFile(file_obj)
        sheets = xl.sheet_names

        workbook_type = self._classify_workbook(sheets)

        sheet_data = {}
        sheet_metadata = {}

        for sheet in sheets:
            try:
                df = xl.parse(sheet)
                df = self._clean_dataframe(df)

                sheet_metadata[sheet] = {
                    'rows': len(df),
                    'columns': len(df.columns),
                    'column_names': list(df.columns),
                    'dtypes': df.dtypes.astype(str).to_dict(),
                    'null_counts': df.isnull().sum().to_dict(),
                    'numeric_cols': list(
                        df.select_dtypes(
                            include=[np.number]
                        ).columns
                    ),
                    'has_dates': self._detect_date_columns(df),
                    'potential_keys': self._detect_primary_keys(df)
                }
                sheet_data[sheet] = df

            except Exception as e:
                logger.warning(
                    f"Could not parse sheet '{sheet}': {str(e)}"
                )

        return {
            'file_name': file_name,
            'workbook_type': workbook_type,
            'sheet_count': len(sheets),
            'sheet_names': sheets,
            'sheet_data': sheet_data,
            'sheet_metadata': sheet_metadata,
            'scan_timestamp': datetime.now().isoformat(),
            'total_records': sum(
                meta['rows']
                for meta in sheet_metadata.values()
            )
        }

    def _classify_workbook(self, sheets: List[str]) -> str:
        """
        Classify workbook type based on sheet structure.
        """
        sheet_names_lower = [s.lower() for s in sheets]

        fifo_keywords = [
            'inventory', 'stock', 'cost', 'fifo',
            'purchase', 'receipt', 'issue'
        ]
        financial_keywords = [
            'balance', 'income', 'cash', 'trial',
            'ledger', 'journal', 'account'
        ]
        audit_keywords = [
            'audit', 'reconcil', 'variance',
            'discrepan', 'comparison'
        ]

        if any(
            kw in name
            for name in sheet_names_lower
            for kw in fifo_keywords
        ):
            return 'INVENTORY_WORKBOOK'
        elif any(
            kw in name
            for name in sheet_names_lower
            for kw in financial_keywords
        ):
            return 'FINANCIAL_WORKBOOK'
        elif any(
            kw in name
            for name in sheet_names_lower
            for kw in audit_keywords
        ):
            return 'AUDIT_WORKBOOK'
        elif len(sheets) == 1:
            return 'SINGLE_SHEET_WORKBOOK'
        else:
            return 'MULTI_TAB_WORKBOOK'

    def _clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and standardize a DataFrame from Excel ingestion.
        """
        # Drop fully empty rows and columns
        df = df.dropna(how='all')
        df = df.dropna(axis=1, how='all')

        # Strip whitespace from string columns
        str_cols = df.select_dtypes(include=['object']).columns
        for col in str_cols:
            df[col] = df[col].astype(str).str.strip()
            df[col] = df[col].replace('nan', np.nan)

        # Standardize column names
        df.columns = [
            str(col).strip().replace('\n', ' ').replace('\r', '')
            for col in df.columns
        ]

        df = df.reset_index(drop=True)
        return df

    def _detect_date_columns(self, df: pd.DataFrame) -> List[str]:
        """Identify columns that contain date-like values."""
        date_cols = []
        for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                date_cols.append(col)
            elif df[col].dtype == object:
                try:
                    sample = df[col].dropna().head(5)
                    pd.to_datetime(sample)
                    date_cols.append(col)
                except Exception:
                    pass
        return date_cols

    def _detect_primary_keys(self, df: pd.DataFrame) -> List[str]:
        """
        Heuristically detect columns that could serve as primary keys.
        """
        potential_keys = []
        key_keywords = [
            'id', 'key', 'code', 'number', 'num',
            'ref', 'sku', 'item', 'employee', 'account'
        ]

        for col in df.columns:
            col_lower = col.lower()

            is_keyword_match = any(kw in col_lower for kw in key_keywords)
            is_unique = df[col].nunique() == len(df[col].dropna())
            has_low_nulls = df[col].isnull().sum() / len(df) < 0.05

            if (is_keyword_match or is_unique) and has_low_nulls:
                potential_keys.append(col)

        return potential_keys[:5]  # Return top 5 candidates

    def get_scan_summary(self) -> Dict:
        """Return a summary of the scanning operation."""
        return {
            'total_files_scanned': len(self.discovered_files),
            'total_errors': len(self.errors),
            'errors': self.errors,
            'files': {
                name: {
                    'type': info['workbook_type'],
                    'sheets': info['sheet_count'],
                    'records': info['total_records']
                }
                for name, info in self.discovered_files.items()
            }
        }