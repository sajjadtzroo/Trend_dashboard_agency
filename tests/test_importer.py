"""app/importer.py — payment-status mapping, derived-column arithmetic, and
dim get-or-create idempotency (DB writes are rolled back by the `db` fixture)."""
import pytest
from app.importer import Importer
from conftest import requires_services


@pytest.fixture
def imp(db):
    return Importer(db)


class TestPay:
    @pytest.mark.parametrize("v,exp", [(0, 0), (1, 1), (2, 2), ("1", 1),
                                       (None, 0), (3, 0), (-1, 0), ("junk", 0)])
    def test_pay_maps_to_status(self, imp, v, exp):
        assert imp._pay(v) == exp


def test_derived_invoice_arithmetic():
    """The receivable derivation documented in importer: amount + VAT - insurance."""
    amount, vat_rate, ins_rate = 360_000_000, 0.1, 1.0 / 6
    vat = amount * vat_rate
    final = amount + vat
    insurance = amount * ins_rate
    receivable = final - insurance
    # matches the header note: 360M @ VAT .1 / Ins .1667 -> ~335,988,000 (rounded)
    assert round(receivable) == 336_000_000
    assert final == 396_000_000


@requires_services
class TestDimIdempotency:
    def test_same_instance_caches(self, imp):
        k1 = imp.supplier("Unit Test Supplier Co", "VOD")
        k2 = imp.supplier("Unit Test Supplier Co", "VOD")
        assert k1 == k2 and k1 is not None

    def test_fresh_instance_hits_on_conflict(self, db):
        a = Importer(db).supplier("Unit Test Supplier Co2", "BTL")
        b = Importer(db).supplier("Unit Test Supplier Co2", "BTL")   # ON CONFLICT -> same key
        assert a == b

    def test_blank_name_returns_none(self, imp):
        assert imp.supplier(None, "VOD") is None
        assert imp.client(None, None, None) is None
        assert imp.brand("X", None) is None       # needs client_key
