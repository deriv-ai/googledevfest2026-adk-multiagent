"""Consistency checks for the committed synthetic CSVs in db/seed/.

Headers must match the columns in db/init (COPY uses explicit
column lists), foreign keys must resolve, sizes must stay in the expected ranges,
and the finance <-> trading and finance <-> marketing reconciliations must hold.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import pytest

SEED = Path(__file__).resolve().parent.parent / "db" / "seed"

COLUMNS = {
    "finance_entities.csv": ["entity_id", "name", "country", "currency"],
    "finance_accounts.csv": ["account_code", "account_name", "account_type", "category"],
    "finance_fx_rates.csv": ["rate_date", "currency", "usd_rate"],
    "finance_gl_entries.csv": ["entry_id", "entry_date", "entity_id", "account_code", "amount_local",
                               "currency", "amount_usd", "description"],
    "finance_budgets.csv": ["month", "entity_id", "account_code", "budget_usd"],
    "trading_clients.csv": ["client_id", "full_name", "country", "segment", "signup_date", "risk_level"],
    "trading_instruments.csv": ["symbol", "name", "asset_class"],
    "trading_trades.csv": ["trade_id", "client_id", "symbol", "side", "quantity", "open_price", "close_price",
                           "open_time", "close_time", "notional_usd", "pnl_usd", "commission_usd", "status"],
    "trading_daily_prices.csv": ["symbol", "price_date", "open", "high", "low", "close", "volume"],
    "marketing_campaigns.csv": ["campaign_id", "name", "entity_id", "channel", "start_date", "end_date"],
    "marketing_campaign_spend.csv": ["spend_id", "campaign_id", "spend_date", "spend_usd", "impressions", "clicks"],
    "marketing_signups.csv": ["client_id", "campaign_id", "signup_date"],
}

ROW_RANGES = {
    "finance_entities.csv": (4, 4),
    "finance_accounts.csv": (15, 60),
    "finance_fx_rates.csv": (1_500, 5_000),
    "finance_gl_entries.csv": (10_000, 25_000),
    "finance_budgets.csv": (500, 3_000),
    "trading_clients.csv": (500, 800),
    "trading_instruments.csv": (10, 30),
    "trading_trades.csv": (15_000, 30_000),
    "trading_daily_prices.csv": (3_000, 12_000),
    "marketing_campaigns.csv": (80, 200),
    "marketing_campaign_spend.csv": (200, 500),
    "marketing_signups.csv": (100, 400),
}

COUNTRY_TO_ENTITY = {"GB": "NM-UK", **{c: "NM-SG" for c in ("SG", "MY", "TH", "ID", "VN", "PH")},
                     **{c: "NM-AE" for c in ("AE", "SA", "QA", "KW", "BH", "OM")}}


@lru_cache(maxsize=None)
def load(name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (SEED / name).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def rows(name: str) -> list[dict[str, str]]:
    return load(name)[1]


@pytest.mark.parametrize("name", sorted(COLUMNS))
def test_header_matches_contract(name):
    header, _ = load(name)
    assert header == COLUMNS[name]


@pytest.mark.parametrize("name", sorted(ROW_RANGES))
def test_row_counts_in_range(name):
    lo, hi = ROW_RANGES[name]
    assert lo <= len(rows(name)) <= hi


def test_total_size_is_a_few_mb():
    total = sum((SEED / n).stat().st_size for n in COLUMNS)
    assert 1_000_000 < total < 10_000_000


@pytest.mark.parametrize("name,keys", [
    ("finance_entities.csv", ("entity_id",)),
    ("finance_accounts.csv", ("account_code",)),
    ("finance_fx_rates.csv", ("rate_date", "currency")),
    ("finance_gl_entries.csv", ("entry_id",)),
    ("finance_budgets.csv", ("month", "entity_id", "account_code")),
    ("trading_clients.csv", ("client_id",)),
    ("trading_instruments.csv", ("symbol",)),
    ("trading_trades.csv", ("trade_id",)),
    ("trading_daily_prices.csv", ("symbol", "price_date")),
    ("marketing_campaigns.csv", ("campaign_id",)),
    ("marketing_campaign_spend.csv", ("spend_id",)),
    ("marketing_signups.csv", ("client_id",)),
])
def test_primary_keys_unique(name, keys):
    seen = [tuple(r[k] for k in keys) for r in rows(name)]
    assert len(seen) == len(set(seen))


def test_reference_data():
    ents = {r["entity_id"]: r["currency"] for r in rows("finance_entities.csv")}
    assert ents == {"NM-UK": "GBP", "NM-SG": "SGD", "NM-AE": "AED", "NM-INTL": "USD"}
    accts = rows("finance_accounts.csv")
    assert {a["account_type"] for a in accts} <= {"revenue", "expense", "asset", "liability", "equity"}
    cats = {a["category"] for a in accts}
    assert {"Trading commission", "Spread revenue", "Subscription fees", "Interest income"} <= cats
    assert {"Staff costs", "Marketing", "Technology", "Office & admin", "Payment processing",
            "Professional fees"} <= cats
    insts = rows("trading_instruments.csv")
    assert {i["asset_class"] for i in insts} == {"forex", "crypto", "commodities", "indices"}
    assert {"EURUSD", "BTCUSD", "XAUUSD", "US100"} <= {i["symbol"] for i in insts}


def test_enums():
    for c in rows("trading_clients.csv"):
        assert c["segment"] in ("retail", "pro", "vip")
        assert c["risk_level"] in ("low", "medium", "high")
        assert len(c["country"]) == 2
    for t in rows("trading_trades.csv"):
        assert t["side"] in ("buy", "sell")
        assert t["status"] in ("open", "closed")
        closed = t["status"] == "closed"
        assert bool(t["close_time"]) == closed
        assert bool(t["commission_usd"]) == closed
        assert bool(t["pnl_usd"]) == closed
        assert Decimal(t["quantity"]) > 0 and Decimal(t["notional_usd"]) > 0


def test_foreign_keys():
    ents = {r["entity_id"] for r in rows("finance_entities.csv")}
    accts = {r["account_code"]: r["account_type"] for r in rows("finance_accounts.csv")}
    ccys = {r["currency"] for r in rows("finance_fx_rates.csv")}
    for g in rows("finance_gl_entries.csv"):
        assert g["entity_id"] in ents and g["account_code"] in accts and g["currency"] in ccys
        assert accts[g["account_code"]] in ("revenue", "expense")
        assert Decimal(g["amount_usd"]) > 0 and Decimal(g["amount_local"]) > 0
    for b in rows("finance_budgets.csv"):
        assert b["entity_id"] in ents and b["account_code"] in accts
        assert b["month"].endswith("-01")
    clients = {c["client_id"]: c for c in rows("trading_clients.csv")}
    symbols = {i["symbol"] for i in rows("trading_instruments.csv")}
    for t in rows("trading_trades.csv"):
        assert t["client_id"] in clients and t["symbol"] in symbols
        assert t["open_time"][:10] >= clients[t["client_id"]]["signup_date"]
    for p in rows("trading_daily_prices.csv"):
        assert p["symbol"] in symbols
        lo, hi = Decimal(p["low"]), Decimal(p["high"])
        assert lo <= Decimal(p["open"]) <= hi and lo <= Decimal(p["close"]) <= hi


def test_gl_currency_matches_entity_and_fx():
    ent_ccy = {r["entity_id"]: r["currency"] for r in rows("finance_entities.csv")}
    fx = {(r["rate_date"], r["currency"]): Decimal(r["usd_rate"]) for r in rows("finance_fx_rates.csv")}
    for g in rows("finance_gl_entries.csv"):
        assert g["currency"] == ent_ccy[g["entity_id"]]
        expected = Decimal(g["amount_local"]) * fx[(g["entry_date"], g["currency"])]
        assert abs(expected - Decimal(g["amount_usd"])) <= Decimal("0.01")


def test_about_eighteen_months():
    months = {g["entry_date"][:7] for g in rows("finance_gl_entries.csv")}
    assert 17 <= len(months) <= 19
    assert months == {b["month"][:7] for b in rows("finance_budgets.csv")}


def test_commission_reconciles_with_gl():
    """GL 'Trading commission' per month+entity == SUM(trades.commission_usd) (client country -> entity)."""
    cat = {a["account_code"]: a["category"] for a in rows("finance_accounts.csv")}
    gl = defaultdict(Decimal)
    for g in rows("finance_gl_entries.csv"):
        if cat[g["account_code"]] == "Trading commission":
            gl[(g["entry_date"][:7], g["entity_id"])] += Decimal(g["amount_usd"])
    country = {c["client_id"]: c["country"] for c in rows("trading_clients.csv")}
    tr = defaultdict(Decimal)
    for t in rows("trading_trades.csv"):
        if t["status"] == "closed":
            ent = COUNTRY_TO_ENTITY.get(country[t["client_id"]], "NM-INTL")
            tr[(t["close_time"][:7], ent)] += Decimal(t["commission_usd"])
    assert set(gl) == set(tr)
    worst = max(abs(gl[k] - tr[k]) for k in gl)
    assert worst < Decimal("1.00"), worst


def _monthly(category_filter, entity=None):
    acct = {a["account_code"]: a for a in rows("finance_accounts.csv")}
    out = defaultdict(lambda: [Decimal(0), Decimal(0)])  # month -> [actual, budget]
    for g in rows("finance_gl_entries.csv"):
        a = acct[g["account_code"]]
        if category_filter(a) and (entity is None or g["entity_id"] == entity):
            out[g["entry_date"][:7]][0] += Decimal(g["amount_usd"])
    for b in rows("finance_budgets.csv"):
        a = acct[b["account_code"]]
        if category_filter(a) and (entity is None or b["entity_id"] == entity):
            out[b["month"][:7]][1] += Decimal(b["budget_usd"])
    return out


def _all_months():
    return sorted({g["entry_date"][:7] for g in rows("finance_gl_entries.csv")})


def _complete_months():
    months = _all_months()
    last_trade_day = max(t["open_time"][:10] for t in rows("trading_trades.csv"))
    last = dt.date.fromisoformat(last_trade_day)
    if (last + dt.timedelta(days=1)).month == last.month:  # last month is partial
        months = months[:-1]
    return months


def test_storyline_revenue_miss_is_the_worst_month():
    rev = _monthly(lambda a: a["account_type"] == "revenue")
    months = _complete_months()
    ratios = {m: rev[m][0] / rev[m][1] for m in months}
    worst = min(ratios, key=ratios.get)
    assert ratios[worst] < Decimal("0.70"), ratios[worst]
    assert worst == _all_months()[-4], worst  # end month - 3 (Aug 2026 in the committed data)


def test_storyline_crypto_spike():
    insts = {i["symbol"]: i["asset_class"] for i in rows("trading_instruments.csv")}
    crypto = defaultdict(int)
    for t in rows("trading_trades.csv"):
        if t["status"] == "closed" and insts[t["symbol"]] == "crypto":
            crypto[t["close_time"][:7]] += 1
    months = _complete_months()
    spike = _all_months()[-2]  # end month - 1 (Oct 2026 in the committed data)
    others = [crypto[m] for m in months if m != spike]
    assert crypto[spike] > 2 * max(others)
    rev = _monthly(lambda a: a["category"] == "Trading commission")
    assert rev[spike][0] > Decimal("1.3") * rev[spike][1]


def test_storyline_marketing_overrun_in_one_entity():
    recent = _all_months()[-5:-1]  # overrun runs from end month - 5; skip the partial end month
    over = {}
    for ent in ("NM-UK", "NM-SG", "NM-AE", "NM-INTL"):
        mk = _monthly(lambda a: a["category"] == "Marketing", ent)
        over[ent] = min(mk[m][0] / mk[m][1] for m in recent)
    assert over["NM-SG"] > Decimal("1.25"), over
    assert all(v < Decimal("1.15") for e, v in over.items() if e != "NM-SG"), over


def test_marketing_foreign_keys():
    ents = {r["entity_id"] for r in rows("finance_entities.csv")}
    campaigns = {c["campaign_id"]: c for c in rows("marketing_campaigns.csv")}
    channels = {"search ads", "social ads", "video ads", "app-store ads", "affiliate network"}
    for c in campaigns.values():
        assert c["entity_id"] in ents and c["channel"] in channels and c["name"].endswith(c["channel"])
        assert c["start_date"] <= c["end_date"]
    for s in rows("marketing_campaign_spend.csv"):
        c = campaigns[s["campaign_id"]]
        assert c["start_date"] <= s["spend_date"] <= c["end_date"]
        assert Decimal(s["spend_usd"]) > 0 and 0 < int(s["clicks"]) < int(s["impressions"])
    clients = {c["client_id"]: c for c in rows("trading_clients.csv")}
    for g in rows("marketing_signups.csv"):
        client = clients[g["client_id"]]
        assert g["signup_date"] == client["signup_date"]
        assert campaigns[g["campaign_id"]]["entity_id"] == COUNTRY_TO_ENTITY.get(client["country"], "NM-INTL")


def test_campaign_spend_reconciles_with_gl():
    gl = {g["entry_id"]: g for g in rows("finance_gl_entries.csv") if g["account_code"] == "5200"}
    spend = {s["spend_id"]: s for s in rows("marketing_campaign_spend.csv")}
    assert spend.keys() == gl.keys()
    campaigns = {c["campaign_id"]: c for c in rows("marketing_campaigns.csv")}
    for spend_id, s in spend.items():
        assert s["spend_usd"] == gl[spend_id]["amount_usd"] and s["spend_date"] == gl[spend_id]["entry_date"]
        assert campaigns[s["campaign_id"]]["entity_id"] == gl[spend_id]["entity_id"]


def test_storyline_nimbus_go_cost_per_signup_rises():
    """Nimbus Go vs NM-SG's campaigns in the same number of months just before it."""
    campaigns = {c["campaign_id"]: c for c in rows("marketing_campaigns.csv") if c["entity_id"] == "NM-SG"}
    go = {cid for cid, c in campaigns.items() if c["name"].startswith("Nimbus Go")}
    spend, signups = defaultdict(Decimal), defaultdict(int)
    for s in rows("marketing_campaign_spend.csv"):
        if s["campaign_id"] in campaigns:
            spend[(s["campaign_id"] in go, s["spend_date"][:7])] += Decimal(s["spend_usd"])
    for g in rows("marketing_signups.csv"):
        if g["campaign_id"] in campaigns:
            signups[(g["campaign_id"] in go, g["signup_date"][:7])] += 1

    go_months = sorted(m for is_go, m in spend if is_go)[:-1]  # skip the partial end month
    before = sorted(m for is_go, m in spend if not is_go)[-len(go_months):]
    assert before[-1] < go_months[0]

    def totals(is_go, months):
        return sum(spend[(is_go, m)] for m in months), sum(signups[(is_go, m)] for m in months)

    go_spend, go_signups = totals(True, go_months)
    old_spend, old_signups = totals(False, before)
    assert go_spend > Decimal("1.5") * old_spend
    assert go_spend / go_signups > Decimal("1.3") * old_spend / old_signups
