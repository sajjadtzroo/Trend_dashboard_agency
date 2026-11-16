"""Excel -> star schema importer (polars calamine engine).

Derived columns in the workbook are Excel formulas with no cached values, so
every derived measure is recomputed from the input columns using the documented
arithmetic (verified: 360M @ VAT .1 / Ins .1667 -> Receivable 335,988,000).

Idempotent: each fact carries a stable `source_row` ('Sales!R12'); re-import
deletes rows with the same provenance before re-inserting.
"""
import csv
import warnings
warnings.filterwarnings("ignore")  # calamine dtype-inference noise
import polars as pl
from sqlalchemy import text

from .clean import clean_text, clean_number, clean_percent, canon_company, canon_brand
from .jalali import upsert_date

DATA_SHEETS = ("Sales", "Invoices", "Suppliers")

# Sales Funnel channels: each has `<ch> Revenue IRR` + cost column(s). VOD splits cost
# into Invested (media buy) + External; every other channel has a single `<ch> Cost IRR`.
CHANNELS = ("Digital", "Social", "VOD", "BTL", "ATL", "Studio")


def channel_split(r):
    """One sheet row -> [(channel, revenue, cost, invested_cost)] for channels with money.

    Returns [] unless the parts reconcile with the row's `Total …` columns (older sheet
    layouts left the channel columns blank) — the caller then books one row from the totals.
    """
    n = lambda k: clean_number(r.get(k)) or 0
    parts = []
    for ch in CHANNELS:
        invested = n(f"{ch} Invested Cost IRR")
        cost = n(f"{ch} Cost IRR") + invested + n(f"{ch} External Cost IRR")
        rev = n(f"{ch} Revenue IRR")
        if rev or cost:
            parts.append((ch, rev, cost, invested))
    ok = (parts and abs(sum(p[1] for p in parts) - n("Total Revenue IRR")) < 1
          and abs(sum(p[2] for p in parts) - n("Total Cost IRR")) < 1)
    return parts if ok else []


class Importer:
    def __init__(self, db):
        self.db = db
        self.cache: dict = {}
        self.summary = {"SALE": 0, "RECEIVABLE": 0, "PAYABLE": 0}
        self.orders = 0                 # sheet orders read (an order can be several SALE facts)
        self.skipped_blank = 0          # blank/spacer rows dropped (no key field)
        self.missing_day = 0            # rows with year+month but no day (defaulted to 1)
        self.notes: list[str] = []

    # ---- dim get-or-create (cached, idempotent) ----
    def _key(self, cache_key, sql, params):
        if params.get("__nat__") in self.cache.get(cache_key, {}):
            return self.cache[cache_key][params["__nat__"]]
        p = {k: v for k, v in params.items() if k != "__nat__"}
        key = self.db.execute(text(sql), p).scalar_one()
        self.cache.setdefault(cache_key, {})[params["__nat__"]] = key
        return key

    def user(self, account):
        if not account:
            return None
        return self._key("user", """
            INSERT INTO dim_user(account) VALUES (:a)
            ON CONFLICT (account) DO UPDATE SET account=EXCLUDED.account
            RETURNING user_key""", {"a": account, "__nat__": account})

    def client(self, company, national_code, category):
        if not company:
            return None
        # Dedup on canonical company_name — national_code is sparse (only the Sales
        # sheet carries it) so keying on it would split one client across sheets.
        return self._key("client", """
            INSERT INTO dim_client(company_name, national_code, category) VALUES (:c, :n, :cat)
            ON CONFLICT (company_name) DO UPDATE SET
                national_code=COALESCE(EXCLUDED.national_code, dim_client.national_code),
                category=COALESCE(EXCLUDED.category, dim_client.category)
            RETURNING client_key""",
            {"c": company, "n": national_code, "cat": category, "__nat__": company})

    def brand(self, brand, client_key):
        if not brand or client_key is None:
            return None
        return self._key("brand", """
            INSERT INTO dim_brand(brand_name, client_key) VALUES (:b, :ck)
            ON CONFLICT (brand_name, client_key) DO UPDATE SET brand_name=EXCLUDED.brand_name
            RETURNING brand_key""", {"b": brand, "ck": client_key, "__nat__": (brand, client_key)})

    def project(self, code, name, client_key):
        if not code:
            return None
        return self._key("project", """
            INSERT INTO dim_project(project_code, project_name, client_key) VALUES (:pc, :pn, :ck)
            ON CONFLICT (project_code) DO UPDATE SET project_name=COALESCE(EXCLUDED.project_name, dim_project.project_name)
            RETURNING project_key""", {"pc": code, "pn": name, "ck": client_key, "__nat__": code})

    def campaign(self, order_name, project_key):
        if not order_name:
            return None
        return self._key("campaign", """
            INSERT INTO dim_campaign(order_name, project_key) VALUES (:o, :pk)
            ON CONFLICT (order_name, project_key) DO UPDATE SET order_name=EXCLUDED.order_name
            RETURNING campaign_key""", {"o": order_name, "pk": project_key, "__nat__": (order_name, project_key)})

    def supplier(self, name, main_service):
        if not name:
            return None
        return self._key("supplier", """
            INSERT INTO dim_supplier(supplier_name, main_service) VALUES (:s, :ms)
            ON CONFLICT (supplier_name) DO UPDATE SET main_service=COALESCE(EXCLUDED.main_service, dim_supplier.main_service)
            RETURNING supplier_key""", {"s": name, "ms": main_service, "__nat__": name})

    def invoice(self, number, po):
        if not number and not po:
            return None
        return self._key("invoice", """
            INSERT INTO dim_invoice(invoice_number, po_number) VALUES (:i, :p)
            ON CONFLICT (invoice_number, po_number) DO UPDATE SET invoice_number=EXCLUDED.invoice_number
            RETURNING invoice_key""", {"i": number, "p": po, "__nat__": (number, po)})

    def lookup(self, cache_key, table, key_col, name_col, value):
        """Resolve a seeded lookup (service/media/order_status) get-or-create by name."""
        if not value:
            return None
        return self._key(cache_key, f"""
            INSERT INTO {table}({name_col}) VALUES (:v)
            ON CONFLICT ({name_col}) DO UPDATE SET {name_col}=EXCLUDED.{name_col}
            RETURNING {key_col}""", {"v": value, "__nat__": value})

    # ---- fact insert ----
    def _fact(self, ftype, source_row, **cols):
        self.db.execute(text("DELETE FROM fact_transaction WHERE source_row = :sr"), {"sr": source_row})
        cols = {k: v for k, v in cols.items() if v is not None}
        cols["transaction_type"] = ftype
        cols["source_row"] = source_row
        names = ", ".join(cols)
        binds = ", ".join(f":{k}" for k in cols)
        self.db.execute(text(f"INSERT INTO fact_transaction ({names}) VALUES ({binds})"), cols)
        self.summary[ftype] += 1

    def _read(self, path, sheet):
        return pl.read_excel(path, sheet_name=sheet, engine="calamine").to_dicts()

    def _read_csv(self, path):
        """Sales Funnel CSV: row 0 is a totals banner, row 1 the header (multiline cells),
        rows 2+ the data. Header keys are whitespace-collapsed so 'Total\\nRevenue' -> one key."""
        with open(path, encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.reader(fh))
        header = [" ".join(h.split()) for h in rows[1]]
        return [dict(zip(header, r)) for r in rows[2:]]

    # ---- per-sheet ----
    def import_sales(self, path):
        for i, r in enumerate(self._read(path, "Sales"), start=2):
            company = canon_company(r.get("Company Name"))
            if not company:
                self.skipped_blank += 1
                continue
            sr = f"Sales!R{i}"
            ck = self.client(company, clean_text(r.get("National Code")), clean_text(r.get("Category")))
            pk = self.project(clean_text(r.get("Project ID")), None, ck)
            rev = sum(clean_number(r.get(f"{k} Revenue")) or 0 for k in ("Digital", "VOD", "BTL", "Studio"))
            cost = sum(clean_number(r.get(f"{k} Cost")) or 0 for k in ("Digital", "VOD", "BTL", "Studio"))
            op = rev - cost
            service = clean_text(r.get("Main Service"))
            self._fact("SALE", sr,
                date_key=self._date(r, sr), user_key=self.user(clean_text(r.get("Account"))),
                client_key=ck, brand_key=self.brand(canon_brand(r.get("Brand")), ck),
                project_key=pk, campaign_key=self.campaign(clean_text(r.get("Order Name")), pk),
                service_key=self.lookup("service", "dim_service", "service_key", "service_name", service),
                media_key=self.lookup("media", "dim_media", "media_key", "media_name", service),
                order_status_key=self.lookup("order_status", "dim_order_status", "order_status_key", "label",
                                             clean_text(r.get("Order Status"))),
                revenue=rev, cost=cost, operational_profit=op,
                profit_margin=round(op / rev, 4) if rev else None,
                fulfillment_pct=clean_percent(r.get("Fulfillment %")))

    def import_sales_csv(self, path):
        """Sales Funnel CSV -> SALE facts, one per channel carrying money (see channel_split).
        Blank/spacer rows with no company are skipped."""
        for i, r in enumerate(self._read_csv(path), start=3):   # data starts at file row 3
            company = canon_company(r.get("Company Name"))
            if not company:
                self.skipped_blank += 1
                continue
            sr = f"Sales!R{i}"
            ck = self.client(company, clean_text(r.get("National Code")), clean_text(r.get("Category")))
            pk = self.project(clean_text(r.get("Project ID No.")), None, ck)
            parts = channel_split(r)
            if parts:
                lines = [(f"{sr}#{ch}", ch, rev, cost, inv) for ch, rev, cost, inv in parts]
            else:   # no (reconciling) channel columns: one line from the totals, as before
                lines = [(sr, clean_text(r.get("Main Service")),
                          clean_number(r.get("Total Revenue IRR")) or 0,
                          clean_number(r.get("Total Cost IRR")) or 0,
                          clean_number(r.get("Total Invested Cost IRR")))]
            shared = dict(
                date_key=self._date_csv(r), user_key=self.user(clean_text(r.get("Account"))),
                client_key=ck, brand_key=self.brand(canon_brand(r.get("Brand")), ck),
                project_key=pk, campaign_key=self.campaign(clean_text(r.get("Order Name")), pk),
                order_status_key=self.lookup("order_status", "dim_order_status", "order_status_key", "label",
                                             clean_text(r.get("Order Status"))),
                fulfillment_pct=clean_percent(r.get("Order Fulfillment")))
            for line_sr, service, rev, cost, invested in lines:
                op = rev - cost
                self._fact("SALE", line_sr, **shared,
                    service_key=self.lookup("service", "dim_service", "service_key", "service_name", service),
                    media_key=self.lookup("media", "dim_media", "media_key", "media_name", service),
                    revenue=rev, cost=cost, invested_cost=invested or None, operational_profit=op,
                    profit_margin=round(op / rev, 4) if rev else None)
            self.orders += 1

    def import_invoices(self, path):
        for i, r in enumerate(self._read(path, "Invoices"), start=2):
            company = canon_company(r.get("Company Name"))
            if not company:
                self.skipped_blank += 1
                continue
            sr = f"Invoices!R{i}"
            ck = self.client(company, None, None)
            pk = self.project(clean_text(r.get("Project ID")), clean_text(r.get("Project Name")), ck)
            amount = clean_number(r.get("Invoice Amount")) or 0
            vat_rate = clean_number(r.get("VAT Rate")) or 0
            ins_rate = clean_number(r.get("Insurance Rate")) or 0
            vat = amount * vat_rate
            final = amount + vat
            insurance = amount * ins_rate
            receivable = final - insurance
            paid = clean_number(r.get("Paid Amount")) or 0
            self._fact("RECEIVABLE", sr,
                date_key=self._date(r, sr), user_key=self.user(clean_text(r.get("Account"))),
                client_key=ck, brand_key=self.brand(canon_brand(r.get("Brand")), ck), project_key=pk,
                invoice_key=self.invoice(clean_text(r.get("Invoice Number")), clean_text(r.get("PO Number"))),
                payment_status_key=self._pay(r.get("Payment Status")),
                amount=amount, vat_rate=vat_rate, vat_amount=vat, final_amount=final,
                insurance_rate=ins_rate, insurance_amount=insurance, receivable=receivable,
                amount_paid=paid, balance=receivable - paid)

    def import_suppliers(self, path):
        for i, r in enumerate(self._read(path, "Suppliers"), start=2):
            name = clean_text(r.get("Supplier Name"))
            if not name:
                self.skipped_blank += 1
                continue
            sr = f"Suppliers!R{i}"
            company = canon_company(r.get("Company Name"))
            ck = self.client(company, None, None) if company else None
            service = clean_text(r.get("Main Service"))
            total = clean_number(r.get("Total Amount")) or 0
            paid = clean_number(r.get("Amount Paid")) or 0
            self._fact("PAYABLE", sr,
                date_key=self._date(r, sr), client_key=ck,
                supplier_key=self.supplier(name, service),
                service_key=self.lookup("service", "dim_service", "service_key", "service_name", service),
                invoice_key=self.invoice(clean_text(r.get("Invoice Number")), None),
                payment_status_key=self._pay(r.get("Payment Status")),
                amount=total, amount_paid=paid, balance=total - paid)

    # ---- helpers ----
    def _date(self, r, sr):
        y, m, d = clean_number(r.get("Jalali Year")), clean_number(r.get("Jalali Month")), clean_number(r.get("Jalali Day"))
        if y and m and not d:
            self.missing_day += 1          # aggregated into one note in run()
        return upsert_date(self.db, y, m, d)

    def _date_csv(self, r):
        """CSV carries year + month only (no day). Prefer the invoice month (sparse),
        fall back to the order-brief month; day defaults to 1."""
        y = clean_number(r.get("Year"))
        m = clean_number(r.get("Date of Invoice")) or clean_number(r.get("Date of Order Brief"))
        return upsert_date(self.db, y, m, 1) if (y and m) else None

    def _pay(self, v):
        n = clean_number(v)
        return int(n) if n in (0, 1, 2) else 0  # default Unpaid

    def run(self, path):
        self.import_sales(path)
        self.import_invoices(path)
        self.import_suppliers(path)
        self.db.commit()
        if self.missing_day:
            self.notes.append(f"{self.missing_day} rows had no Jalali day; defaulted to 1")
        return {"inserted": self.summary, "skipped_blank": self.skipped_blank,
                "notes": self.notes[:50], "total": sum(self.summary.values())}

    def run_csv(self, path):
        """Seed path: Sales Funnel CSV only (SALE facts)."""
        self.import_sales_csv(path)
        self.db.commit()
        return {"inserted": self.summary, "orders": self.orders, "skipped_blank": self.skipped_blank,
                "notes": self.notes[:50], "total": sum(self.summary.values())}
