"""Every HTTP endpoint, end-to-end against the running Postgres + Redis.

Read endpoints assert 200 + shape. Mutating endpoints (payments, manage
patch/delete) do net-zero round-trips that restore the seeded DB in `finally`.
"""
import pytest
from sqlalchemy import text
from conftest import requires_services

pytestmark = requires_services

DASHBOARD = ["/meta", "/kpis", "/funnel", "/revenue-by-service", "/revenue-trend",
             "/top-clients", "/top-campaigns", "/brands", "/receivables", "/payables",
             "/receivables-aging", "/payables-aging", "/fulfillment-trend"]
STATEMENTS = ["/statements/income", "/statements/balance", "/statements/cashflow",
              "/statements/segments", "/statements/notes"]
RESOURCES = ["campaigns", "projects", "users", "media"]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


@pytest.mark.parametrize("path", DASHBOARD)
def test_dashboard_endpoints_200(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, (list, dict))


def test_kpis_shape(client):
    b = client.get("/kpis").json()
    for k in ("revenue", "cost", "op_profit", "ar_outstanding", "ap_outstanding"):
        assert k in b


def test_kpis_numeric_not_string(client):
    b = client.get("/kpis").json()
    assert isinstance(b["revenue"], (int, float))   # cache round-trip keeps numbers


def test_dashboard_filter_applied(client):
    # a client filter must not error and must stay within the unfiltered total
    full = client.get("/kpis").json()["revenue"]
    one = client.get("/kpis", params={"client": "Unilever"}).json()["revenue"]
    assert one <= full + 1


@pytest.mark.parametrize("path", STATEMENTS)
def test_statement_endpoints_200(client, path):
    r = client.get(path)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, dict) and body   # non-empty statement payload


@pytest.mark.parametrize("by", ["campaign", "brand", "client", "service"])
def test_segments_by_dimension(client, by):
    b = client.get("/statements/segments", params={"by": by}).json()
    assert b["by"] == by and isinstance(b["rows"], list)


@pytest.mark.parametrize("resource", RESOURCES)
def test_manage_list_200(client, resource):
    r = client.get(f"/manage/{resource}")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_manage_unknown_resource_404(client):
    assert client.get("/manage/widgets").status_code == 404


@pytest.mark.parametrize("resource", RESOURCES)
def test_manage_detail_200(client, resource):
    lst = client.get(f"/manage/{resource}").json()
    if not lst:
        pytest.skip(f"no {resource} seeded")
    rid = lst[0]["id"]
    b = client.get(f"/manage/{resource}/{rid}").json()
    assert "item" in b and "transactions" in b


def test_manage_detail_unknown_404(client):
    assert client.get("/manage/campaigns/99999999").status_code == 404


def test_manage_patch_empty_body_400(client):
    lst = client.get("/manage/campaigns").json()
    rid = lst[0]["id"]
    assert client.patch(f"/manage/campaigns/{rid}", json={}).status_code == 400


# ---- invoices ----
def test_invoices_list_200(client):
    r = client.get("/invoices")
    assert r.status_code == 200 and isinstance(r.json(), list)


def test_invoices_list_has_expected_columns(client):
    rows_ = client.get("/invoices").json()
    if rows_:
        assert {"id", "invoice_number", "client", "balance", "status"} <= set(rows_[0])


def test_invoice_detail_200(client):
    lst = client.get("/invoices").json()
    iid = lst[0]["id"]
    b = client.get(f"/invoices/{iid}").json()
    assert b["id"] == iid and "vat_rate" in b and "receivable" in b


def test_invoice_detail_404(client):
    assert client.get("/invoices/99999999").status_code == 404


def test_invoice_payments_ledger_200(client):
    iid = client.get("/invoices").json()[0]["id"]
    b = client.get(f"/invoices/{iid}/payments").json()
    assert "rows" in b and b["rows"][0]["label"] == "Opening (imported)"


def test_invoice_payments_unknown_404(client):
    assert client.get("/invoices/99999999/payments").status_code == 404


def test_invoice_related_200(client):
    iid = client.get("/invoices").json()[0]["id"]
    r = client.get(f"/invoices/{iid}/related")
    assert r.status_code == 200 and isinstance(r.json(), list)


# ---- imports ----
def test_import_bad_extension_400(client):
    files = {"file": ("data.txt", b"nope", "text/plain")}
    assert client.post("/import/xlsx", files=files).status_code == 400


def test_import_status_unknown_404(client):
    assert client.get("/import/status/nope").status_code == 404


# ---- mutation round-trips (restore state) ----
def _outstanding_invoice(client):
    for row in client.get("/invoices").json():
        if (row.get("balance") or 0) > 100:
            return row["id"], float(row["balance"])
    pytest.skip("no invoice with outstanding balance")


class TestPaymentWriteRoundTrip:
    def test_post_then_delete_restores_balance(self, client):
        iid, balance = _outstanding_invoice(client)
        note = "pytest-roundtrip"
        # bad amounts first (no mutation)
        assert client.post(f"/invoices/{iid}/payments", json={"amount": 0}).status_code == 400
        assert client.post(f"/invoices/{iid}/payments",
                           json={"amount": balance + 1_000_000}).status_code == 400

        r = client.post(f"/invoices/{iid}/payments", json={"amount": 100, "note": note})
        assert r.status_code == 200
        assert r.json()["balance"] == pytest.approx(balance - 100, abs=1)
        try:
            ledger = client.get(f"/invoices/{iid}/payments").json()["rows"]
            pid = next(p["payment_id"] for p in ledger if p.get("note") == note)
        finally:
            # always undo, even if the assertion above changes
            ledger = client.get(f"/invoices/{iid}/payments").json()["rows"]
            for p in ledger:
                if p.get("note") == note and p.get("payment_id"):
                    client.delete(f"/invoices/{iid}/payments/{p['payment_id']}")
        restored = client.get(f"/invoices/{iid}").json()["balance"]
        assert restored == pytest.approx(balance, abs=1)

    def test_delete_unknown_payment_404(self, client):
        iid, _ = _outstanding_invoice(client)
        assert client.delete(f"/invoices/{iid}/payments/99999999").status_code == 404


class TestManagePatchRoundTrip:
    def test_rename_and_restore(self, client, db):
        lst = client.get("/manage/campaigns").json()
        rid, original = lst[0]["id"], lst[0]["name"]
        try:
            r = client.patch(f"/manage/campaigns/{rid}", json={"name": "PYTEST TEMP NAME"})
            assert r.status_code == 200 and r.json()["updated"] == rid
            got = db.execute(text("SELECT order_name FROM dim_campaign WHERE campaign_key=:id"),
                             {"id": rid}).scalar_one()
            assert got == "PYTEST TEMP NAME"
        finally:
            client.patch(f"/manage/campaigns/{rid}", json={"name": original})

    def test_patch_unknown_404(self, client):
        assert client.patch("/manage/campaigns/99999999", json={"name": "x"}).status_code == 404


def test_manage_delete_unknown_is_noop_hard(client):
    # nonexistent id: not referenced -> hard path, 0 rows, still 200
    r = client.delete("/manage/media/99999999")
    assert r.status_code == 200 and r.json()["mode"] == "hard" and r.json()["references"] == 0
