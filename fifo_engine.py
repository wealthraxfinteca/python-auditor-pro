"""
FIFO (First-In, First-Out) Costing Engine
Processes inventory transactions and calculates FIFO costs
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class FIFOLayer:
    """Represents a single FIFO inventory layer."""
    date: datetime
    quantity: float
    unit_cost: float
    remaining_qty: float = field(init=False)
    layer_id: int = field(default=0)

    def __post_init__(self):
        self.remaining_qty = self.quantity

    @property
    def total_cost(self) -> float:
        return self.remaining_qty * self.unit_cost

    @property
    def is_exhausted(self) -> bool:
        return self.remaining_qty <= 0


class FIFOEngine:
    """
    Processes inventory records using FIFO costing methodology.
    Tracks layers, calculates COGS, and computes ending inventory values.
    """

    def __init__(self):
        self.layers: List[FIFOLayer] = []
        self.transactions_log: List[Dict] = []
        self.cogs_log: List[Dict] = []
        self.layer_counter = 0

    def process_transactions(
        self,
        df: pd.DataFrame,
        date_col: str,
        type_col: str,
        qty_col: str,
        cost_col: str,
        item_col: Optional[str] = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Main processing method for FIFO costing.
        Accepts a DataFrame of transactions and returns FIFO results.
        """
        results = {}

        # Sort by date to ensure proper FIFO ordering
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col).reset_index(drop=True)

        if item_col and item_col in df.columns:
            # Process each item separately
            for item_id, item_df in df.groupby(item_col):
                item_result = self._process_item_transactions(
                    item_df,
                    date_col,
                    type_col,
                    qty_col,
                    cost_col,
                    item_id=str(item_id)
                )
                results[str(item_id)] = item_result
        else:
            # Process as single item pool
            item_result = self._process_item_transactions(
                df,
                date_col,
                type_col,
                qty_col,
                cost_col,
                item_id='ALL'
            )
            results['ALL'] = item_result

        return results

    def _process_item_transactions(
        self,
        df: pd.DataFrame,
        date_col: str,
        type_col: str,
        qty_col: str,
        cost_col: str,
        item_id: str = 'ALL'
    ) -> Dict:
        """Process FIFO for a single item."""
        layers: List[FIFOLayer] = []
        cogs_records = []
        running_inventory = []
        total_cogs = 0.0
        total_receipts = 0.0
        total_issues = 0.0

        # Normalize transaction types
        receipt_types = ['receipt', 'purchase', 'in', 'buy', 'received', 'po']
        issue_types = ['issue', 'sale', 'out', 'sell', 'sold', 'usage', 'dispatch']

        for _, row in df.iterrows():
            trans_type = str(row[type_col]).lower().strip()
            qty = float(row[qty_col]) if pd.notna(row[qty_col]) else 0
            cost = float(row[cost_col]) if pd.notna(row[cost_col]) else 0
            trans_date = row[date_col]

            is_receipt = any(t in trans_type for t in receipt_types)
            is_issue = any(t in trans_type for t in issue_types)

            if is_receipt:
                # Add new FIFO layer
                self.layer_counter += 1
                new_layer = FIFOLayer(
                    date=trans_date,
                    quantity=qty,
                    unit_cost=cost,
                    layer_id=self.layer_counter
                )
                layers.append(new_layer)
                total_receipts += qty * cost

                running_inventory.append({
                    'Date': trans_date,
                    'Item': item_id,
                    'Transaction': 'RECEIPT',
                    'Quantity': qty,
                    'Unit_Cost': cost,
                    'Transaction_Value': qty * cost,
                    'COGS': 0,
                    'Inventory_Layers': len(
                        [l for l in layers if not l.is_exhausted]
                    ),
                    'Inventory_Value': sum(
                        l.total_cost for l in layers
                    )
                })

            elif is_issue:
                # Consume from oldest FIFO layers
                cogs, issue_detail = self._consume_fifo_layers(
                    layers,
                    qty,
                    trans_date,
                    item_id
                )
                total_cogs += cogs
                total_issues += qty
                cogs_records.extend(issue_detail)

                running_inventory.append({
                    'Date': trans_date,
                    'Item': item_id,
                    'Transaction': 'ISSUE',
                    'Quantity': -qty,
                    'Unit_Cost': cogs / qty if qty > 0 else 0,
                    'Transaction_Value': -cogs,
                    'COGS': cogs,
                    'Inventory_Layers': len(
                        [l for l in layers if not l.is_exhausted]
                    ),
                    'Inventory_Value': sum(
                        l.total_cost for l in layers
                    )
                })

        # Build ending inventory from remaining layers
        ending_inventory = self._build_ending_inventory(layers, item_id)

        return {
            'item_id': item_id,
            'total_cogs': total_cogs,
            'total_receipts': total_receipts,
            'ending_inventory_value': sum(
                l.total_cost for l in layers
            ),
            'ending_inventory_qty': sum(
                l.remaining_qty for l in layers
            ),
            'running_inventory': pd.DataFrame(running_inventory),
            'cogs_detail': pd.DataFrame(cogs_records),
            'ending_layers': ending_inventory,
            'layer_count': len(layers)
        }

    def _consume_fifo_layers(
        self,
        layers: List[FIFOLayer],
        quantity_needed: float,
        trans_date: datetime,
        item_id: str
    ) -> Tuple[float, List[Dict]]:
        """
        Consume inventory from oldest FIFO layers.
        Returns total COGS and detailed consumption records.
        """
        total_cogs = 0.0
        issue_detail = []
        remaining_to_issue = quantity_needed

        for layer in layers:
            if layer.is_exhausted or remaining_to_issue <= 0:
                continue

            qty_from_layer = min(layer.remaining_qty, remaining_to_issue)
            cogs_from_layer = qty_from_layer * layer.unit_cost

            layer.remaining_qty -= qty_from_layer
            total_cogs += cogs_from_layer
            remaining_to_issue -= qty_from_layer

            issue_detail.append({
                'Date': trans_date,
                'Item': item_id,
                'Layer_ID': layer.layer_id,
                'Layer_Date': layer.date,
                'Layer_Unit_Cost': layer.unit_cost,
                'Qty_Consumed': qty_from_layer,
                'COGS_Amount': cogs_from_layer
            })

        if remaining_to_issue > 0:
            logger.warning(
                f"Insufficient inventory for item {item_id}. "
                f"Short by {remaining_to_issue} units."
            )

        return total_cogs, issue_detail

    def _build_ending_inventory(
        self,
        layers: List[FIFOLayer],
        item_id: str
    ) -> pd.DataFrame:
        """Build a DataFrame of remaining inventory layers."""
        active_layers = [l for l in layers if not l.is_exhausted]

        if not active_layers:
            return pd.DataFrame()

        return pd.DataFrame([
            {
                'Item': item_id,
                'Layer_ID': l.layer_id,
                'Receipt_Date': l.date,
                'Original_Qty': l.quantity,
                'Remaining_Qty': l.remaining_qty,
                'Unit_Cost': l.unit_cost,
                'Layer_Value': l.total_cost,
                'Consumed_Qty': l.quantity - l.remaining_qty
            }
            for l in active_layers
        ])

    def generate_fifo_summary(
        self,
        results: Dict[str, Dict]
    ) -> pd.DataFrame:
        """Generate a summary DataFrame across all items."""
        summary_rows = []

        for item_id, result in results.items():
            summary_rows.append({
                'Item_ID': item_id,
                'Total_COGS': result['total_cogs'],
                'Total_Receipts_Value': result['total_receipts'],
                'Ending_Inventory_Qty': result['ending_inventory_qty'],
                'Ending_Inventory_Value': result['ending_inventory_value'],
                'Inventory_Layers_Remaining': result['layer_count'],
                'Gross_Profit_Impact': (
                    result['total_receipts'] - result['total_cogs']
                )
            })

        return pd.DataFrame(summary_rows)