"""app/routers/invoices.py pure/DB helpers: _pay_status and _receivable."""
import pytest
from fastapi import HTTPException
from app.routers.invoices import _pay_status, _receivable
from conftest import requires_services


class TestPayStatus:
    @pytest.mark.parametrize("recv,paid,exp", [
        (1000, 0, 0),        # nothing paid -> Unpaid
        (1000, 400, 2),      # partial
        (1000, 1000, 1),     # paid in full
        (1000, 1000.001, 1), # overpaid rounds to Paid
        (0, 0, 0),           # zero receivable, nothing paid -> Unpaid
    ])
    def test_transitions(self, recv, paid, exp):
        assert _pay_status(recv, paid) == exp


@requires_services
class TestReceivable:
    def test_missing_invoice_raises_404(self, db):
        with pytest.raises(HTTPException) as ei:
            _receivable(db, 99_999_999)
        assert ei.value.status_code == 404

    def test_returns_money_fields(self, db):
        from sqlalchemy import text
        rid = db.execute(text("SELECT transaction_id FROM fact_transaction "
                              "WHERE transaction_type='RECEIVABLE' LIMIT 1")).scalar_one()
        row = _receivable(db, rid)
        assert {"receivable", "amount_paid", "balance"} <= set(row)
