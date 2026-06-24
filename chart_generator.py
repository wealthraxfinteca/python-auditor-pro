"""
Chart Generator
Creates audit visualization charts using Plotly
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Optional


class ChartGenerator:
    """Generates interactive Plotly charts for audit insights."""

    # Color palette
    COLORS = {
        'primary': '#1f4e79',
        'secondary': '#2e75b6',
        'accent': '#00b0f0',
        'success': '#00b050',
        'warning': '#ffc000',
        'danger': '#ff0000',
        'light': '#dce6f1',
        'HIGH': '#d9534f',
        'MEDIUM': '#f0ad4e',
        'LOW': '#5bc0de'
    }

    def create_audit_overview_chart(
        self,
        recon_stats: Dict,
        comparison_label: str
    ) -> go.Figure:
        """
        Donut chart showing record reconciliation breakdown.
        """
        matched = recon_stats.get('matched_clean', 0)
        changed = recon_stats.get('records_with_changes', 0)
        added = recon_stats.get('records_added', 0)
        removed = recon_stats.get('records_removed', 0)

        labels = ['Clean Matches', 'Changed Records', 'Added', 'Removed']
        values = [matched, changed, added, removed]
        colors = [
            self.COLORS['success'],
            self.COLORS['warning'],
            self.COLORS['accent'],
            self.COLORS['danger']
        ]

        # Filter out zeros
        filtered = [
            (l, v, c) for l, v, c in zip(labels, values, colors)
            if v > 0
        ]
        if not filtered:
            filtered = [('No Differences', 1, self.COLORS['success'])]

        labels, values, colors = zip(*filtered)

        fig = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=colors, line=dict(color='white', width=2)),
            textinfo='label+percent+value',
            hovertemplate='<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>'
        ))

        fig.add_annotation(
            text=f"<b>{sum(values)}</b><br>Total<br>Records",
            x=0.5, y=0.5,
            font_size=14,
            showarrow=False
        )

        fig.update_layout(
            title=dict(
                text=f"📊 Reconciliation Overview: {comparison_label}",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            showlegend=True,
            height=420,
            margin=dict(t=80, b=20, l=20, r=20),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    def create_variance_waterfall_chart(
        self,
        diff_df: pd.DataFrame,
        top_n: int = 10
    ) -> go.Figure:
        """
        Waterfall chart showing top variance contributors by column.
        """
        if diff_df.empty or 'Variance' not in diff_df.columns:
            return self._empty_chart("No Variance Data Available")

        numeric_diffs = diff_df[diff_df['Is_Numeric'] == True].copy()
        if numeric_diffs.empty:
            return self._empty_chart("No Numeric Variances Found")

        col_variance = (
            numeric_diffs.groupby('Column')['Variance']
            .sum()
            .reset_index()
            .sort_values('Variance', ascending=False)
            .head(top_n)
        )

        colors = [
            self.COLORS['success'] if v >= 0 else self.COLORS['danger']
            for v in col_variance['Variance']
        ]

        fig = go.Figure(go.Bar(
            x=col_variance['Column'],
            y=col_variance['Variance'],
            marker_color=colors,
            text=[f"{v:,.2f}" for v in col_variance['Variance']],
            textposition='outside',
            hovertemplate=(
                '<b>%{x}</b><br>'
                'Net Variance: %{y:,.2f}<extra></extra>'
            )
        ))

        fig.update_layout(
            title=dict(
                text="📉 Net Variance by Column (Top Contributors)",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            xaxis_title="Column",
            yaxis_title="Net Variance",
            height=400,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickangle=-35)
        )

        fig.add_hline(
            y=0,
            line_dash='dash',
            line_color='grey',
            opacity=0.5
        )

        return fig

    def create_severity_distribution_chart(
        self,
        flagged_df: pd.DataFrame
    ) -> go.Figure:
        """
        Horizontal bar chart showing severity distribution of findings.
        """
        if flagged_df.empty or 'Severity' not in flagged_df.columns:
            return self._empty_chart("No Flagged Findings")

        severity_counts = (
            flagged_df['Severity']
            .value_counts()
            .reindex(['HIGH', 'MEDIUM', 'LOW'], fill_value=0)
        )

        fig = go.Figure(go.Bar(
            y=severity_counts.index,
            x=severity_counts.values,
            orientation='h',
            marker_color=[
                self.COLORS.get(s, '#999')
                for s in severity_counts.index
            ],
            text=severity_counts.values,
            textposition='inside',
            textfont=dict(color='white', size=14, family='Arial Black'),
            hovertemplate='<b>%{y}</b>: %{x} findings<extra></extra>'
        ))

        fig.update_layout(
            title=dict(
                text="🚨 Discrepancy Severity Distribution",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            xaxis_title="Number of Findings",
            yaxis_title="Severity Level",
            height=320,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    def create_column_heatmap(
        self,
        diff_df: pd.DataFrame,
        primary_key: str = 'Primary_Key'
    ) -> go.Figure:
        """
        Heatmap of which key x column combinations have discrepancies.
        """
        if diff_df.empty:
            return self._empty_chart("No Differences to Display")

        # Pivot for heatmap: keys vs columns
        diff_df = diff_df.copy()
        diff_df['Has_Diff'] = 1

        top_keys = (
            diff_df.groupby('Primary_Key')['Has_Diff']
            .sum()
            .nlargest(20)
            .index
        )
        filtered = diff_df[diff_df['Primary_Key'].isin(top_keys)]

        pivot = (
            filtered.pivot_table(
                index='Primary_Key',
                columns='Column',
                values='Has_Diff',
                aggfunc='count',
                fill_value=0
            )
        )

        severity_pivot = None
        if 'Severity' in diff_df.columns:
            sev_map = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            diff_df['Sev_Score'] = diff_df.get(
                'Severity', 'LOW'
            ).map(sev_map).fillna(1)

            severity_pivot = (
                diff_df[diff_df['Primary_Key'].isin(top_keys)]
                .pivot_table(
                    index='Primary_Key',
                    columns='Column',
                    values='Sev_Score',
                    aggfunc='max',
                    fill_value=0
                )
            )

        display_pivot = severity_pivot if severity_pivot is not None else pivot

        fig = go.Figure(go.Heatmap(
            z=display_pivot.values,
            x=display_pivot.columns.tolist(),
            y=display_pivot.index.tolist(),
            colorscale=[
                [0, '#f8f9fa'],
                [0.33, self.COLORS['LOW']],
                [0.66, self.COLORS['MEDIUM']],
                [1, self.COLORS['HIGH']]
            ],
            colorbar=dict(
                title='Severity',
                tickvals=[0, 1, 2, 3],
                ticktext=['None', 'LOW', 'MED', 'HIGH']
            ),
            hovertemplate=(
                'Record: <b>%{y}</b><br>'
                'Column: <b>%{x}</b><br>'
                'Severity: %{z}<extra></extra>'
            )
        ))

        fig.update_layout(
            title=dict(
                text="🔍 Discrepancy Heatmap (Records × Columns)",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            height=500,
            xaxis=dict(tickangle=-35),
            paper_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    def create_variance_trend_chart(
        self,
        diff_df: pd.DataFrame
    ) -> go.Figure:
        """
        Scatter plot of variance percentage per record.
        """
        if diff_df.empty or 'Variance_Pct' not in diff_df.columns:
            return self._empty_chart("No Variance Trend Data")

        numeric_df = diff_df[
            diff_df['Is_Numeric'] == True
        ].dropna(subset=['Variance_Pct'])

        if numeric_df.empty:
            return self._empty_chart("No Numeric Variance Data")

        severity_colors = {
            'HIGH': self.COLORS['HIGH'],
            'MEDIUM': self.COLORS['MEDIUM'],
            'LOW': self.COLORS['LOW']
        }

        fig = go.Figure()

        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            subset = numeric_df[
                numeric_df.get('Severity', pd.Series(['LOW'] * len(numeric_df))) == severity
            ] if 'Severity' in numeric_df.columns else numeric_df

            if not subset.empty:
                fig.add_trace(go.Scatter(
                    x=subset['Primary_Key'],
                    y=subset['Variance_Pct'],
                    mode='markers',
                    name=severity,
                    marker=dict(
                        color=severity_colors.get(severity, '#999'),
                        size=9,
                        opacity=0.8,
                        line=dict(color='white', width=1)
                    ),
                    hovertemplate=(
                        'Key: <b>%{x}</b><br>'
                        'Variance: <b>%{y:.2f}%</b><extra></extra>'
                    )
                ))

        fig.add_hline(
            y=0, line_dash='dash',
            line_color='grey', opacity=0.5
        )
        fig.add_hrect(
            y0=-self.get_tolerance_pct(),
            y1=self.get_tolerance_pct(),
            fillcolor='green', opacity=0.07,
            annotation_text="Tolerance Band"
        )

        fig.update_layout(
            title=dict(
                text="📈 Variance % per Record",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            xaxis_title="Record (Primary Key)",
            yaxis_title="Variance %",
            height=420,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickangle=-45)
        )

        return fig

    def create_fifo_chart(
        self,
        running_inventory_df: pd.DataFrame
    ) -> go.Figure:
        """
        Line chart showing running inventory value and COGS over time.
        """
        if running_inventory_df.empty:
            return self._empty_chart("No FIFO Data Available")

        df = running_inventory_df.copy()
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=(
                'Running Inventory Value',
                'Cumulative COGS'
            ),
            vertical_spacing=0.12
        )

        # Inventory value line
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=df['Inventory_Value'],
                name='Inventory Value',
                line=dict(color=self.COLORS['secondary'], width=2.5),
                fill='tozeroy',
                fillcolor='rgba(46,117,182,0.15)',
                hovertemplate='Date: %{x}<br>Value: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=1
        )

        # Cumulative COGS
        df['Cumulative_COGS'] = df['COGS'].cumsum()
        fig.add_trace(
            go.Bar(
                x=df['Date'],
                y=df['COGS'],
                name='COGS per Transaction',
                marker_color=self.COLORS['danger'],
                opacity=0.7,
                hovertemplate='Date: %{x}<br>COGS: $%{y:,.2f}<extra></extra>'
            ),
            row=2, col=1
        )

        fig.update_layout(
            title=dict(
                text="📦 FIFO Inventory & COGS Analysis",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            height=560,
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )

        return fig

    def create_multi_file_comparison_chart(
        self,
        recon_matrix: pd.DataFrame
    ) -> go.Figure:
        """
        Grouped bar chart for multi-file reconciliation matrix.
        """
        if recon_matrix.empty:
            return self._empty_chart("No Multi-File Data")

        metrics = [
            'Value_Differences', 'Records_Added',
            'Records_Removed', 'Clean_Matches'
        ]
        colors = [
            self.COLORS['warning'], self.COLORS['success'],
            self.COLORS['danger'], self.COLORS['accent']
        ]

        fig = go.Figure()

        for metric, color in zip(metrics, colors):
            if metric in recon_matrix.columns:
                fig.add_trace(go.Bar(
                    name=metric.replace('_', ' '),
                    x=recon_matrix['Comparison'],
                    y=recon_matrix[metric],
                    marker_color=color,
                    hovertemplate=(
                        '<b>%{x}</b><br>'
                        f'{metric}: %{{y}}<extra></extra>'
                    )
                ))

        fig.update_layout(
            title=dict(
                text="🗂️ Multi-File Audit Comparison Matrix",
                font=dict(size=16, color=self.COLORS['primary'])
            ),
            barmode='group',
            xaxis_title="File Comparison",
            yaxis_title="Count",
            height=420,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickangle=-25)
        )

        return fig

    def _empty_chart(self, message: str) -> go.Figure:
        """Return a placeholder chart with a message."""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            x=0.5, y=0.5,
            xref='paper', yref='paper',
            showarrow=False,
            font=dict(size=18, color='grey')
        )
        fig.update_layout(
            height=300,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig

    def get_tolerance_pct(self) -> float:
        return 1.0