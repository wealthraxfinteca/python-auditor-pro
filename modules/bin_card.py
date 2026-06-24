"""
Bin Card & Inventory Management Module
Manages inventory movements, FIFO layers, bin card records
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from modules.database import DatabaseManager
import logging

logger = logging.getLogger(__name__)


class BinCardManager:
    """
    Manages bin cards, inventory movements, and FIFO costing.
    Every purchase receipt creates a FIFO layer and bin card entry.
    """

    def __init__(self, db: DatabaseManager):
        self.db = db

    # ─── Item Registration ─────────────────────────
    def register_item(self, item_data: Dict) -> int:
        """Register a new inventory item."""
        return self.db.execute_write("""
            INSERT OR REPLACE INTO inventory_master
            (item_code, item_description, item_category,
             unit_of_measure, reorder_level, reorder_quantity,
             warehouse, bin_location)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            item_data['item_code'],
            item_data['item_description'],
            item_data.get('item_category', 'General'),
            item_data.get('unit_of_measure', 'UNIT'),
            item_data.get('reorder_level', 0),
            item_data.get('reorder_quantity', 0),
            item_data.get('warehouse', 'MAIN'),
            item_data.get('bin_location', '')
        ))

    # ─── Receipts (from Purchases) ─────────────────
    def post_receipt(
        self,
        item_code: str,
        item_description: str,
        quantity: float,
        unit_cost: float,
        transaction_date: str,
        reference: str,
        warehouse: str = 'MAIN',
        notes: str = ''
    ) -> Dict:
        """
        Post a goods receipt to bin card and create FIFO layer.
        Called automatically when a purchase is posted.
        """
        # 1. Create FIFO layer
        layer_id = self.db.execute_write("""
            INSERT INTO fifo_layers
            (item_code, warehouse, receipt_date, reference_number,
             original_qty, remaining_qty, unit_cost, layer_value)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            item_code, warehouse, transaction_date,
            reference, quantity, quantity,
            unit_cost, quantity * unit_cost
        ))

        # 2. Get current balance
        current = self._get_current_balance(item_code, warehouse)
        new_qty = current['qty'] + quantity
        new_value = current['value'] + (quantity * unit_cost)

        # 3. Post bin card entry
        self.db.execute_write("""
            INSERT INTO bin_cards
            (transaction_date, item_code, item_description,
             warehouse, transaction_type, reference_number,
             source_document, qty_in, qty_out, unit_cost,
             balance_qty, balance_value, fifo_layer_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            transaction_date, item_code, item_description,
            warehouse, 'RECEIPT', reference,
            'PURCHASE', quantity, 0,
            unit_cost, new_qty, new_value,
            layer_id, notes
        ))

        # 4. Update inventory master
        self._update_inventory_master(item_code, warehouse)

        return {
            'layer_id': layer_id,
            'new_balance_qty': new_qty,
            'new_balance_value': new_value
        }

    # ─── Issues (FIFO consumption) ─────────────────
    def post_issue(
        self,
        item_code: str,
        item_description: str,
        quantity: float,
        transaction_date: str,
        reference: str,
        warehouse: str = 'MAIN',
        notes: str = ''
    ) -> Dict:
        """
        Post an inventory issue using FIFO consumption.
        Returns COGS calculated per FIFO.
        """
        # Check available stock
        current = self._get_current_balance(item_code, warehouse)
        if current['qty'] < quantity:
            raise ValueError(
                f"Insufficient stock for {item_code}. "
                f"Available: {current['qty']}, Requested: {quantity}"
            )

        # Consume FIFO layers
        cogs, consumed = self._consume_fifo(
            item_code, warehouse, quantity
        )

        avg_cost = cogs / quantity if quantity > 0 else 0
        new_qty = current['qty'] - quantity
        new_value = current['value'] - cogs

        # Post bin card entry
        self.db.execute_write("""
            INSERT INTO bin_cards
            (transaction_date, item_code, item_description,
             warehouse, transaction_type, reference_number,
             source_document, qty_in, qty_out, unit_cost,
             balance_qty, balance_value, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            transaction_date, item_code, item_description,
            warehouse, 'ISSUE', reference,
            'SALES_ORDER', 0, quantity,
            avg_cost, new_qty, new_value, notes
        ))

        self._update_inventory_master(item_code, warehouse)

        return {
            'cogs': cogs,
            'avg_fifo_cost': avg_cost,
            'new_balance_qty': new_qty,
            'consumed_layers': consumed
        }

    # ─── Purchase Returns ──────────────────────────
    def post_return(
        self,
        item_code: str,
        quantity: float,
        unit_cost: float,
        transaction_date: str,
        reference: str,
        warehouse: str = 'MAIN'
    ) -> Dict:
        """Post a purchase return - reverses FIFO layer."""
        # Find the most recent layer with this cost to reverse
        layers = self.db.execute_query("""
            SELECT * FROM fifo_layers
            WHERE item_code=? AND warehouse=?
            AND ABS(unit_cost - ?) < 0.001
            AND is_exhausted=0
            ORDER BY receipt_date DESC
            LIMIT 1
        """, (item_code, warehouse, unit_cost))

        if layers:
            layer = layers[0]
            reduce_qty = min(quantity, layer['remaining_qty'])
            self.db.execute_write("""
                UPDATE fifo_layers
                SET remaining_qty = remaining_qty - ?,
                    layer_value = (remaining_qty - ?) * unit_cost,
                    is_exhausted = CASE
                        WHEN (remaining_qty - ?) <= 0 THEN 1
                        ELSE 0 END
                WHERE id=?
            """, (reduce_qty, reduce_qty, reduce_qty, layer['id']))

        current = self._get_current_balance(item_code, warehouse)
        new_qty = current['qty'] - quantity
        new_value = current['value'] - (quantity * unit_cost)

        self.db.execute_write("""
            INSERT INTO bin_cards
            (transaction_date, item_code, item_description,
             warehouse, transaction_type, reference_number,
             source_document, qty_in, qty_out, unit_cost,
             balance_qty, balance_value)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            transaction_date, item_code, '',
            warehouse, 'RETURN', reference,
            'PURCHASE_RETURN', 0, quantity,
            unit_cost, new_qty, new_value
        ))

        self._update_inventory_master(item_code, warehouse)
        return {'new_balance_qty': new_qty}

    # ─── FIFO Engine ───────────────────────────────
    def _consume_fifo(
        self,
        item_code: str,
        warehouse: str,
        quantity_needed: float
    ) -> Tuple[float, List[Dict]]:
        """Consume FIFO layers and return total COGS."""
        layers = self.db.execute_query("""
            SELECT * FROM fifo_layers
            WHERE item_code=? AND warehouse=? AND is_exhausted=0
            ORDER BY receipt_date ASC, id ASC
        """, (item_code, warehouse))

        total_cogs = 0.0
        consumed = []
        remaining = quantity_needed

        for layer in layers:
            if remaining <= 0:
                break

            consume_qty = min(layer['remaining_qty'], remaining)
            cogs_from_layer = consume_qty * layer['unit_cost']
            total_cogs += cogs_from_layer
            remaining -= consume_qty

            new_remaining = layer['remaining_qty'] - consume_qty
            self.db.execute_write("""
                UPDATE fifo_layers
                SET remaining_qty=?,
                    layer_value=? * unit_cost,
                    is_exhausted=?
                WHERE id=?
            """, (
                new_remaining,
                new_remaining,
                1 if new_remaining <= 0 else 0,
                layer['id']
            ))

            consumed.append({
                'layer_id': layer['id'],
                'receipt_date': layer['receipt_date'],
                'unit_cost': layer['unit_cost'],
                'qty_consumed': consume_qty,
                'cogs': cogs_from_layer
            })

        return total_cogs, consumed

    def _get_current_balance(
        self,
        item_code: str,
        warehouse: str
    ) -> Dict:
        """Get current inventory balance from bin cards."""
        result = self.db.execute_query("""
            SELECT balance_qty, balance_value
            FROM bin_cards
            WHERE item_code=? AND warehouse=?
            ORDER BY id DESC LIMIT 1
        """, (item_code, warehouse))

        if result:
            return {
                'qty': result[0]['balance_qty'],
                'value': result[0]['balance_value']
            }
        return {'qty': 0.0, 'value': 0.0}

    def _update_inventory_master(
        self,
        item_code: str,
        warehouse: str
    ):
        """Recalculate and update inventory master totals."""
        layers = self.db.execute_query("""
            SELECT SUM(remaining_qty) as total_qty,
                   SUM(layer_value) as total_value,
                   CASE WHEN SUM(remaining_qty) > 0
                        THEN SUM(layer_value)/SUM(remaining_qty)
                        ELSE 0 END as fifo_cost
            FROM fifo_layers
            WHERE item_code=? AND warehouse=? AND is_exhausted=0
        """, (item_code, warehouse))

        if layers and layers[0]['total_qty'] is not None:
            l = layers[0]
            self.db.execute_write("""
                UPDATE inventory_master
                SET current_qty=?, total_value=?, fifo_cost=?
                WHERE item_code=? AND warehouse=?
            """, (
                l['total_qty'] or 0,
                l['total_value'] or 0,
                l['fifo_cost'] or 0,
                item_code, warehouse
            ))

    # ─── Queries ───────────────────────────────────
    def get_bin_card(
        self,
        item_code: str,
        warehouse: str = 'MAIN'
    ) -> pd.DataFrame:
        """Get full bin card history for an item."""
        return self.db.query_to_df("""
            SELECT
                transaction_date as Date,
                transaction_type as Type,
                reference_number as Reference,
                source_document as Source,
                qty_in as "Qty IN",
                qty_out as "Qty OUT",
                unit_cost as "Unit Cost",
                balance_qty as "Balance Qty",
                balance_value as "Balance Value",
                notes as Notes
            FROM bin_cards
            WHERE item_code=? AND warehouse=?
            ORDER BY id ASC
        """, (item_code, warehouse))

    def get_inventory_summary(self) -> pd.DataFrame:
        """Get current inventory valuation summary."""
        return self.db.query_to_df("""
            SELECT
                im.item_code as "Item Code",
                im.item_description as "Description",
                im.item_category as "Category",
                im.unit_of_measure as UOM,
                im.current_qty as "Current Qty",
                im.fifo_cost as "FIFO Cost",
                im.total_value as "Total Value",
                im.reorder_level as "Reorder Level",
                CASE WHEN im.current_qty <= im.reorder_level
                     THEN 'REORDER' ELSE 'OK' END as Status,
                im.warehouse as Warehouse,
                im.bin_location as "Bin Location"
            FROM inventory_master im
            WHERE im.is_active=1
            ORDER BY im.item_code
        """)

    def get_fifo_layers(self, item_code: str) -> pd.DataFrame:
        """Get active FIFO layers for an item."""
        return self.db.query_to_df("""
            SELECT
                id as "Layer ID",
                receipt_date as "Receipt Date",
                reference_number as Reference,
                original_qty as "Original Qty",
                remaining_qty as "Remaining Qty",
                unit_cost as "Unit Cost",
                layer_value as "Layer Value",
                CASE WHEN is_exhausted=1 THEN 'Exhausted'
                     ELSE 'Active' END as Status
            FROM fifo_layers
            WHERE item_code=?
            ORDER BY receipt_date ASC
        """, (item_code,))

    def get_low_stock_items(self) -> pd.DataFrame:
        """Get items below reorder level."""
        return self.db.query_to_df("""
            SELECT item_code, item_description,
                   current_qty, reorder_level, reorder_quantity
            FROM inventory_master
            WHERE current_qty <= reorder_level AND is_active=1
        """)