"""Live schema introspection for the Data Schema page.

Everything comes from pg_catalog (tables, columns, types, PK/FK) plus the
``COMMENT ON`` text via obj_description / col_description, so the UI can never
drift from the database.
"""

from __future__ import annotations

from typing import Any

from psycopg import sql
from psycopg.rows import dict_row

from .tools.executor import json_safe

SCHEMAS = ("finance", "trading", "tools")
MAX_SAMPLE = 50


class UnknownSchemaObject(LookupError):
    pass


class SchemaService:
    def __init__(self, db_provider):
        self._db_provider = db_provider

    async def _fetch(self, query, params=None) -> list[dict[str, Any]]:
        db = self._db_provider()
        await db.ensure_open()
        async with db.app_pool.connection(timeout=10.0) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                return list(await cur.fetchall())

    async def list_schemas(self) -> dict[str, Any]:
        rows = await self._fetch(
            "SELECT nspname AS name, obj_description(oid, 'pg_namespace') AS comment "
            "FROM pg_namespace WHERE nspname = ANY(%s)",
            (list(SCHEMAS),),
        )
        by_name = {r["name"]: r for r in rows}
        return {"schemas": [{"name": s, "comment": (by_name.get(s) or {}).get("comment")}
                            for s in SCHEMAS if s in by_name]}

    async def table_names(self, schema: str) -> list[str]:
        rows = await self._fetch(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r','p','v','m') ORDER BY c.relname",
            (schema,),
        )
        return [r["relname"] for r in rows]

    async def describe(self, schema: str) -> dict[str, Any]:
        if schema not in SCHEMAS:
            raise UnknownSchemaObject(schema)
        schema_rows = await self._fetch(
            "SELECT obj_description(oid, 'pg_namespace') AS comment FROM pg_namespace WHERE nspname = %s",
            (schema,),
        )
        if not schema_rows:
            raise UnknownSchemaObject(schema)
        tables = await self._fetch(
            "SELECT c.oid, c.relname AS name, obj_description(c.oid, 'pg_class') AS comment, "
            "c.reltuples::bigint AS estimate, c.relkind "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r','p','v','m') ORDER BY c.relname",
            (schema,),
        )
        columns = await self._fetch(
            "SELECT a.attrelid AS oid, a.attnum, a.attname AS name, "
            "format_type(a.atttypid, a.atttypmod) AS type, NOT a.attnotnull AS nullable, "
            "col_description(a.attrelid, a.attnum) AS comment "
            "FROM pg_attribute a JOIN pg_class c ON c.oid = a.attrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = %s AND c.relkind IN ('r','p','v','m') AND a.attnum > 0 AND NOT a.attisdropped "
            "ORDER BY a.attrelid, a.attnum",
            (schema,),
        )
        constraints = await self._fetch(
            "SELECT con.conrelid AS oid, con.contype, con.conkey, con.confkey, "
            "fc.relname AS ftable, fn.nspname AS fschema, con.confrelid AS foid "
            "FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "LEFT JOIN pg_class fc ON fc.oid = con.confrelid "
            "LEFT JOIN pg_namespace fn ON fn.oid = fc.relnamespace "
            "WHERE n.nspname = %s AND con.contype IN ('p','f')",
            (schema,),
        )
        # attnum -> name for referenced tables (may live in another schema)
        foreign_oids = sorted({c["foid"] for c in constraints if c["contype"] == "f" and c["foid"]})
        attnames: dict[tuple[int, int], str] = {(c["oid"], c["attnum"]): c["name"] for c in columns}
        if foreign_oids:
            for r in await self._fetch(
                "SELECT attrelid AS oid, attnum, attname FROM pg_attribute WHERE attrelid = ANY(%s) AND attnum > 0",
                (foreign_oids,),
            ):
                attnames[(r["oid"], r["attnum"])] = r["attname"]

        pk: set[tuple[int, int]] = set()
        fk: dict[tuple[int, int], dict[str, Any]] = {}
        for con in constraints:
            if con["contype"] == "p":
                pk.update((con["oid"], k) for k in con["conkey"] or [])
            else:
                for local, remote in zip(con["conkey"] or [], con["confkey"] or []):
                    fk[(con["oid"], local)] = {
                        "schema": con["fschema"],
                        "table": con["ftable"],
                        "column": attnames.get((con["foid"], remote)),
                    }

        out_tables = []
        for t in tables:
            row_count = await self._row_count(schema, t["name"])
            cols = [
                {
                    "name": c["name"],
                    "type": c["type"],
                    "nullable": c["nullable"],
                    "pk": (c["oid"], c["attnum"]) in pk,
                    "fk": fk.get((c["oid"], c["attnum"])),
                    "comment": c["comment"],
                }
                for c in columns
                if c["oid"] == t["oid"]
            ]
            out_tables.append({"name": t["name"], "comment": t["comment"], "row_count": row_count, "columns": cols})
        return {"name": schema, "comment": schema_rows[0]["comment"], "tables": out_tables}

    async def _row_count(self, schema: str, table: str) -> int | None:
        # Tables are small (tens of thousands of rows), so an exact count is cheap
        # and avoids reltuples = -1 on never-analysed tables.
        try:
            rows = await self._fetch(
                sql.SQL("SELECT count(*) AS n FROM {}.{}").format(sql.Identifier(schema), sql.Identifier(table))
            )
            return int(rows[0]["n"])
        except Exception:  # noqa: BLE001
            return None

    async def sample(self, schema: str, table: str, limit: int = 5) -> dict[str, Any]:
        if schema not in SCHEMAS:
            raise UnknownSchemaObject(schema)
        if table not in await self.table_names(schema):
            raise UnknownSchemaObject(f"{schema}.{table}")
        limit = max(1, min(int(limit), MAX_SAMPLE))
        db = self._db_provider()
        await db.ensure_open()
        async with db.app_pool.connection(timeout=10.0) as conn:
            cur = await conn.execute(
                sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(sql.Identifier(schema), sql.Identifier(table)),
                (limit,),
            )
            columns = [d.name for d in (cur.description or [])]
            rows = [[json_safe(v) for v in r] for r in await cur.fetchall()]
        return {"columns": columns, "rows": rows}
