import pytest
from percival.budget import BudgetExceeded, BudgetLedger


def test_reservation_settlement_and_persistence(tmp_path):
    path = tmp_path / "ledger.db"
    ledger = BudgetLedger(path)
    ledger.set_limit("research", 1000)
    ledger.reserve("research", "req-1", 800)
    with pytest.raises(BudgetExceeded):
        ledger.reserve("research", "req-2", 300)
    ledger.settle("req-1", 650)
    assert BudgetLedger(path).status("research") == dict(limit_micro=1000, used_micro=650, reserved_micro=0, available_micro=350)


def test_reservation_is_idempotency_guard(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.db")
    ledger.set_limit("agent", 100)
    ledger.reserve("agent", "id", 40)
    with pytest.raises(ValueError):
        ledger.reserve("agent", "id", 40)
    ledger.cancel("id")
    assert ledger.status("agent")["available_micro"] == 100
    with pytest.raises(ValueError):
        ledger.cancel("id")


def test_cannot_lower_limit_below_committed(tmp_path):
    ledger = BudgetLedger(tmp_path / "ledger.db")
    ledger.set_limit("agent", 100)
    ledger.reserve("agent", "id", 80)
    with pytest.raises(BudgetExceeded):
        ledger.set_limit("agent", 50)
    with pytest.raises(BudgetExceeded):
        ledger.settle("id", 90)
