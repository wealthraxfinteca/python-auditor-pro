"""
Core Audit Engine
Performs multi-file comparison, variance analysis, and discrepancy flagging
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AuditEngine:
    """
    Core audit engine that compares DataFrames, calculates variances,
    flags discrepancies, and generates structured audit findings.
    """

    def __init__(self, tolerance: float = 0.01):
        """
        Args:
            tolerance: Acceptable numeric variance threshold (default 1%)
        """
        self.tolerance = tolerance
        self.audit_timestamp = datetime.now()
        self.findings = {}

    def compare_two_files(
        self,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        primary_key: str,
        file1_label: str = "File_1",
        file2_label: str = "File_2"
    ) -> Dict:
        """
        Perform a full audit comparison between two DataFrames.
        Returns a comprehensive findings dictionary.
        """
        # Validate primary key exists in both DataFrames
        if primary_key not in df1.columns:
            raise ValueError(
                f"Primary key '{primary_key}' not found in {file1_label}"
            )
        if primary_key not in df2.columns:
            raise ValueError(
                f"Primary key '{primary_key}' not found in {file2_label}"
            )

        # Standardize key column
        df1 = df1.copy()
        df2 = df2.copy()
        df1[primary_key] = df1[primary_key].astype(str).str.strip()
        df2[primary_key] = df2[primary_key].astype(str).str.strip()

        # Outer join to capture all records
        merged = df1.merge(
            df2,
            on=primary_key,
            how='outer',
            suffixes=(f'_{file1_label}', f'_{file2_label}'),
            indicator=True
        )

        # Categorize records
        added = merged[merged['_merge'] == 'right_only'].copy()
        removed = merged[merged['_merge'] == 'left_only'].copy()
        common = merged[merged['_merge'] == 'both'].copy()

        # Analyze differences in common records
        value_differences = self._extract_value_differences(
            common, df1, df2, primary_key,
            file1_label, file2_label
        )

        # Calculate variance metrics
        variance_metrics = self._calculate_variance_metrics(
            value_differences, df1, df2
        )

        # Flag severity levels
        flagged_findings = self._flag_discrepancies(
            value_differences, variance_metrics
        )

        # Reconciliation stats
        recon_stats = self._reconciliation_stats(
            df1, df2, common, added, removed,
            value_differences, file1_label, file2_label
        )

        findings = {
            'comparison_label': f"{file1_label} vs {file2_label}",
            'audit_timestamp': self.audit_timestamp.isoformat(),
            'primary_key': primary_key,
            'recon_stats': recon_stats,
            'value_differences': value_differences,
            'variance_metrics': variance_metrics,
            'flagged_findings': flagged_findings,
            'added_records': added,
            'removed_records': removed,
            'common_records': common,
            'merged_df': merged
        }

        self.findings[f"{file1_label}_vs_{file2_label}"] = findings
        return findings

    def compare_multiple_files(
        self,
        file_data: Dict[str, pd.DataFrame],
        primary_key: str
    ) -> Dict:
        """
        Compare multiple files against a baseline (first file).
        Performs pairwise comparisons and builds a reconciliation matrix.
        """
        file_names = list(file_data.keys())
        all_comparisons = {}

        if len(file_names) < 2:
            raise ValueError("At least 2 files required for comparison.")

        baseline_name = file_names[0]
        baseline_df = file_data[baseline_name]

        for other_name in file_names[1:]:
            other_df = file_data[other_name]
            comparison = self.compare_two_files(
                baseline_df,
                other_df,
                primary_key,
                baseline_name,
                other_name
            )
            all_comparisons[f"{baseline_name}_vs_{other_name}"] = comparison

        # Build reconciliation matrix across all comparisons
        recon_matrix = self._build_reconciliation_matrix(
            all_comparisons, primary_key
        )

        return {
            'comparisons': all_comparisons,
            'reconciliation_matrix': recon_matrix,
            'file_count': len(file_names),
            'baseline_file': baseline_name,
            'audit_timestamp': self.audit_timestamp.isoformat()
        }

    def _extract_value_differences(
        self,
        common: pd.DataFrame,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        primary_key: str,
        label1: str,
        label2: str
    ) -> pd.DataFrame:
        """Extract cell-level differences from common records."""
        differences = []

        # Find comparable columns (exist in both, excluding key)
        comparable_cols = [
            col for col in df1.columns
            if col != primary_key and col in df2.columns
        ]

        for _, row in common.iterrows():
            for col in comparable_cols:
                col_old = f"{col}_{label1}"
                col_new = f"{col}_{label2}"

                if col_old not in row.index or col_new not in row.index:
                    continue

                val_old = row[col_old]
                val_new = row[col_new]

                # Skip if both are NaN
                if pd.isna(val_old) and pd.isna(val_new):
                    continue

                # Check for discrepancy
                is_different = self._values_differ(val_old, val_new)

                if is_different:
                    # Calculate variance for numeric fields
                    variance = None
                    variance_pct = None
                    is_numeric = False

                    try:
                        num_old = float(val_old)
                        num_new = float(val_new)
                        variance = num_new - num_old
                        variance_pct = (
                            (variance / num_old * 100)
                            if num_old != 0 else None
                        )
                        is_numeric = True
                    except (ValueError, TypeError):
                        pass

                    differences.append({
                        'Primary_Key': row[primary_key],
                        'Column': col,
                        f'Value_{label1}': val_old,
                        f'Value_{label2}': val_new,
                        'Variance': variance,
                        'Variance_Pct': variance_pct,
                        'Is_Numeric': is_numeric,
                        'Data_Type': 'Numeric' if is_numeric else 'Text',
                        'Null_Change': (
                            'Became_Null' if pd.isna(val_new)
                            else 'Was_Null' if pd.isna(val_old)
                            else 'Value_Changed'
                        )
                    })

        return pd.DataFrame(differences)

    def _values_differ(self, val1: Any, val2: Any) -> bool:
        """Determine if two values are meaningfully different."""
        # Both null -> no difference
        if pd.isna(val1) and pd.isna(val2):
            return False

        # One is null -> difference
        if pd.isna(val1) or pd.isna(val2):
            return True

        # Numeric comparison with tolerance
        try:
            num1 = float(val1)
            num2 = float(val2)
            if num1 == 0 and num2 == 0:
                return False
            relative_diff = abs(num1 - num2) / max(abs(num1), abs(num2), 1e-10)
            return relative_diff > self.tolerance
        except (ValueError, TypeError):
            pass

        # String comparison
        return str(val1).strip() != str(val2).strip()

    def _calculate_variance_metrics(
        self,
        diff_df: pd.DataFrame,
        df1: pd.DataFrame,
        df2: pd.DataFrame
    ) -> Dict:
        """Calculate aggregate variance metrics for the audit report."""
        if diff_df.empty:
            return {
                'total_differences': 0,
                'numeric_differences': 0,
                'text_differences': 0,
                'total_variance': 0,
                'max_variance': 0,
                'min_variance': 0,
                'avg_variance_pct': 0,
                'columns_with_diffs': [],
                'top_variance_columns': []
            }

        numeric_diffs = diff_df[diff_df['Is_Numeric'] == True]
        text_diffs = diff_df[diff_df['Is_Numeric'] == False]

        # Column-level variance aggregation
        col_variance = {}
        if not numeric_diffs.empty:
            col_variance = (
                numeric_diffs.groupby('Column')['Variance']
                .agg(['sum', 'count', 'mean'])
                .to_dict('index')
            )

        top_cols = sorted(
            col_variance.items(),
            key=lambda x: abs(x[1].get('sum', 0)),
            reverse=True
        )[:5]

        return {
            'total_differences': len(diff_df),
            'numeric_differences': len(numeric_diffs),
            'text_differences': len(text_diffs),
            'total_variance': (
                numeric_diffs['Variance'].sum()
                if not numeric_diffs.empty else 0
            ),
            'max_variance': (
                numeric_diffs['Variance'].max()
                if not numeric_diffs.empty else 0
            ),
            'min_variance': (
                numeric_diffs['Variance'].min()
                if not numeric_diffs.empty else 0
            ),
            'avg_variance_pct': (
                numeric_diffs['Variance_Pct'].mean()
                if not numeric_diffs.empty else 0
            ),
            'columns_with_diffs': diff_df['Column'].unique().tolist(),
            'top_variance_columns': [
                {
                    'column': col,
                    'total_variance': stats['sum'],
                    'occurrences': int(stats['count'])
                }
                for col, stats in top_cols
            ]
        }

    def _flag_discrepancies(
        self,
        diff_df: pd.DataFrame,
        metrics: Dict
    ) -> pd.DataFrame:
        """
        Apply severity flags to each discrepancy.
        HIGH: >10% variance or null changes
        MEDIUM: 1-10% variance
        LOW: <1% variance or text changes
        """
        if diff_df.empty:
            return pd.DataFrame()

        flagged = diff_df.copy()

        def assign_severity(row):
            if row['Null_Change'] in ('Became_Null', 'Was_Null'):
                return 'HIGH'
            if not row['Is_Numeric']:
                return 'MEDIUM'
            if row['Variance_Pct'] is None:
                return 'MEDIUM'
            pct = abs(row['Variance_Pct'])
            if pct > 10:
                return 'HIGH'
            elif pct > 1:
                return 'MEDIUM'
            else:
                return 'LOW'

        flagged['Severity'] = flagged.apply(assign_severity, axis=1)

        severity_map = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        flagged['Severity_Score'] = flagged['Severity'].map(severity_map)
        flagged = flagged.sort_values(
            'Severity_Score', ascending=False
        ).drop(columns='Severity_Score')

        return flagged

    def _reconciliation_stats(
        self,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        common: pd.DataFrame,
        added: pd.DataFrame,
        removed: pd.DataFrame,
        diff_df: pd.DataFrame,
        label1: str,
        label2: str
    ) -> Dict:
        """Build reconciliation statistics dictionary."""
        total_in_df1 = len(df1)
        total_in_df2 = len(df2)
        common_count = len(common)
        matched_clean = common_count - (
            len(diff_df['Primary_Key'].unique()) if not diff_df.empty else 0
        )

        match_rate = (
            (matched_clean / max(total_in_df1, total_in_df2)) * 100
            if max(total_in_df1, total_in_df2) > 0 else 0
        )

        return {
            f'total_records_{label1}': total_in_df1,
            f'total_records_{label2}': total_in_df2,
            'common_records': common_count,
            'matched_clean': matched_clean,
            'records_added': len(added),
            'records_removed': len(removed),
            'records_with_changes': (
                len(diff_df['Primary_Key'].unique())
                if not diff_df.empty else 0
            ),
            'match_rate_pct': round(match_rate, 2),
            'audit_pass': match_rate >= 95.0
        }

    def _build_reconciliation_matrix(
        self,
        comparisons: Dict,
        primary_key: str
    ) -> pd.DataFrame:
        """Build a matrix showing differences across all comparisons."""
        matrix_rows = []

        for comp_label, comp_data in comparisons.items():
            stats = comp_data['recon_stats']
            metrics = comp_data['variance_metrics']

            matrix_rows.append({
                'Comparison': comp_label,
                'Common_Records': stats.get('common_records', 0),
                'Clean_Matches': stats.get('matched_clean', 0),
                'Value_Differences': metrics.get('total_differences', 0),
                'Records_Added': stats.get('records_added', 0),
                'Records_Removed': stats.get('records_removed', 0),
                'Total_Numeric_Variance': metrics.get('total_variance', 0),
                'Match_Rate_%': stats.get('match_rate_pct', 0),
                'Audit_Status': (
                    'PASS' if stats.get('audit_pass', False) else 'FAIL'
                )
            })

        return pd.DataFrame(matrix_rows)