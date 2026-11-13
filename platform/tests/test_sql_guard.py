import pytest

from devfest_agents.tools.sql_guard import (
    SqlGuardError,
    check_sql,
    compile_sql,
    find_placeholders,
    mask_sql,
    normalize_sql,
)


def test_placeholders_ignore_casts_literals_and_comments():
    sql = (
        "SELECT to_char(t.close_time, 'HH24:MI') AS hhmm, :x::date AS d -- :not_me\n"
        "FROM trading.trades t /* :nor_me */ WHERE t.symbol = ':literal' AND t.qty > :min_qty "
        "AND t.close_time::date BETWEEN :start_date AND :end_date AND :x IS NOT NULL"
    )
    assert find_placeholders(sql) == ["x", "min_qty", "start_date", "end_date"]


def test_mask_keeps_length():
    sql = "SELECT 'a;b' AS x, \"weird;col\" FROM finance.t -- c;\n"
    assert len(mask_sql(sql)) == len(sql)
    assert ";" not in mask_sql(sql).rstrip()


@pytest.mark.parametrize("sql", [
    "SELECT * FROM trading.trades",
    "WITH m AS (SELECT symbol FROM trading.trades) SELECT * FROM m",
    "SELECT extract(month FROM t.close_time) AS m FROM trading.trades t",
    "SELECT t.symbol FROM trading.trades t JOIN trading.instruments i USING (symbol);",
    "SELECT close, open FROM trading.daily_prices WHERE symbol = 'DROP TABLE x'",
    "SELECT * FROM generate_series(1, 3) g CROSS JOIN trading.instruments",
])
def test_valid_trading_sql(sql):
    assert check_sql(sql, "trading") == []


@pytest.mark.parametrize("sql,needle", [
    ("DROP TABLE trading.trades", "SELECT or WITH"),
    ("SELECT 1; DROP TABLE trading.trades", "single statement"),
    ("SELECT * FROM trading.trades; SELECT 1", "single statement"),
    ("SELECT * FROM finance.gl_entries", "may only read the 'trading' schema"),
    ("SELECT * FROM tools.tools", "may only read the 'trading' schema"),
    ("SELECT * FROM pg_catalog.pg_tables", "System catalogs"),
    ("SELECT * FROM information_schema.tables", "System catalogs"),
    ("SELECT pg_sleep(10)", "System catalogs"),
    ("WITH x AS (DELETE FROM trading.trades RETURNING *) SELECT * FROM x", "DELETE"),
    ("SELECT * INTO trading.copy FROM trading.trades", "INTO"),
    ("SELECT set_config('role', 'app', false)", "set_config"),
    ("SELECT * FROM trades", "schema-qualified"),
    ("", "empty"),
])
def test_rejections(sql, needle):
    errors = check_sql(sql, "trading")
    assert errors, sql
    assert any(needle.lower() in e.lower() for e in errors), errors


def test_finance_cannot_read_trading():
    errors = check_sql("SELECT * FROM trading.trades", "finance")
    assert any("'finance' schema" in e for e in errors)


def test_compile_casts_and_percent_escape():
    sql = "SELECT * FROM trading.clients c WHERE c.full_name LIKE 'A%' AND c.signup_date >= :start_date " \
          "AND (:segment IS NULL OR c.segment = :segment) LIMIT :limit;"
    out = compile_sql(sql, {"start_date": "date", "segment": "string", "limit": "integer"})
    assert "'A%%'" in out
    assert "%(start_date)s::date" in out
    assert "%(segment)s::text IS NULL" in out
    assert out.endswith("LIMIT %(limit)s::bigint")
    assert ";" not in out


def test_compile_keeps_existing_casts():
    out = compile_sql("SELECT :end_month::date + interval '1 month'", {"end_month": "date"})
    assert out == "SELECT %(end_month)s::date::date + interval '1 month'"


def test_compile_leaves_literals_alone():
    out = compile_sql("SELECT to_char(now(), 'HH24:MI'), :n", {"n": "number"})
    assert "'HH24:MI'" in out and "%(n)s::numeric" in out


def test_compile_unknown_placeholder():
    with pytest.raises(SqlGuardError):
        compile_sql("SELECT :nope", {})


def test_normalize_strips_trailing_semicolon():
    assert normalize_sql("  SELECT 1 ;  ") == "SELECT 1"
