"""Atomic, persistent per-agent cloud budget accounting.

All amounts are integer micro-USD to avoid floating-point accounting errors.
Reservations are conservative estimates; reconcile after verified provider usage.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path


class BudgetExceeded(Exception):
    pass


class BudgetLedger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS agents (name TEXT PRIMARY KEY, limit_usd_micro INTEGER NOT NULL CHECK(limit_usd_micro >= 0), used INTEGER NOT NULL DEFAULT 0, reserved INTEGER NOT NULL DEFAULT 0)")
            db.execute("CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, agent TEXT NOT NULL, amount INTEGER NOT NULL, state TEXT NOT NULL CHECK(state IN ('reserved','settled','cancelled')))")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def set_limit(self, agent: str, limit_micro: int):
        if not agent or limit_micro < 0:
            raise ValueError("Invalid agent or limit")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT used,reserved FROM agents WHERE name=?", (agent,)).fetchone()
            if row and sum(row) > limit_micro:
                db.rollback()
                raise BudgetExceeded("New limit below committed spending")
            db.execute("INSERT INTO agents(name,limit_usd_micro) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET limit_usd_micro=excluded.limit_usd_micro", (agent, limit_micro))
            db.commit()

    def reserve(self, agent: str, request_id: str, amount_micro: int):
        if not request_id or amount_micro < 0:
            raise ValueError("Invalid reservation")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM reservations WHERE id=?", (request_id,)).fetchone():
                db.rollback()
                raise ValueError("Duplicate reservation ID")
            updated = db.execute("UPDATE agents SET reserved=reserved+? WHERE name=? AND used+reserved+?<=limit_usd_micro", (amount_micro, agent, amount_micro))
            if updated.rowcount != 1:
                db.rollback()
                raise BudgetExceeded("Agent budget exhausted or not configured")
            db.execute("INSERT INTO reservations(id,agent,amount,state) VALUES (?,?,?,'reserved')", (request_id, agent, amount_micro))
            db.commit()

    def settle(self, request_id: str, actual_micro: int):
        if actual_micro < 0:
            raise ValueError("Negative actual cost")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT agent,amount,state FROM reservations WHERE id=?", (request_id,)).fetchone()
            if not row or row[2] != "reserved":
                db.rollback()
                raise ValueError("Unknown or already closed reservation")
            agent, reserved, _ = row
            if actual_micro > reserved:
                db.rollback()
                raise BudgetExceeded("Actual charge exceeds reservation; manual reconciliation required")
            db.execute("UPDATE agents SET reserved=reserved-?,used=used+? WHERE name=?", (reserved, actual_micro, agent))
            db.execute("UPDATE reservations SET state='settled' WHERE id=?", (request_id,))
            db.commit()

    def cancel(self, request_id: str):
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT agent,amount,state FROM reservations WHERE id=?", (request_id,)).fetchone()
            if not row or row[2] != "reserved":
                db.rollback()
                raise ValueError("Unknown or already closed reservation")
            db.execute("UPDATE agents SET reserved=reserved-? WHERE name=?", (row[1], row[0]))
            db.execute("UPDATE reservations SET state='cancelled' WHERE id=?", (request_id,))
            db.commit()

    def status(self, agent: str) -> dict:
        with self._connect() as db:
            row = db.execute("SELECT limit_usd_micro,used,reserved FROM agents WHERE name=?", (agent,)).fetchone()
        if not row:
            raise KeyError(agent)
        return dict(limit_micro=row[0], used_micro=row[1], reserved_micro=row[2], available_micro=row[0]-row[1]-row[2])
