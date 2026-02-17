"""
Migrate all data from MySQL (cs_qbank) to Supabase (Postgres).

Approach: Create clean Postgres DDL manually, then copy data using pandas-style
dict export/import. This avoids MySQL-specific types (TINYINT, collations, etc.).

Usage:
    python3 -m question_banks.v2.migrate_data
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

# ── Connection URLs ──────────────────────────────────────────────────

MYSQL_URL = "mysql+pymysql://admin:Cs-NeeTGuiDe@cs-neetguide.crzbseg7lazz.ap-south-1.rds.amazonaws.com:3306/cs_qbank?charset=utf8mb4"
SUPABASE_URL = "postgresql://postgres:rezri8-kosxuz-mebweG@db.pluaucceqqybafvmdmxv.supabase.co:5432/postgres"

# ── Postgres-compatible DDL for each MySQL table ─────────────────────

DDL = {
    "streams": """
        CREATE TABLE IF NOT EXISTS streams (
            s_no SERIAL PRIMARY KEY,
            stream_name VARCHAR(255) NOT NULL,
            short_url VARCHAR(255) NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "classes": """
        CREATE TABLE IF NOT EXISTS classes (
            s_no SERIAL PRIMARY KEY,
            class_name VARCHAR(255) NOT NULL,
            short_url VARCHAR(255) NOT NULL,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            sequence INTEGER,
            class_in_digit INTEGER NOT NULL DEFAULT 0
        )
    """,
    "cognitive_level": """
        CREATE TABLE IF NOT EXISTS cognitive_level (
            s_no SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "question_types": """
        CREATE TABLE IF NOT EXISTS question_types (
            s_no SERIAL PRIMARY KEY,
            question_type VARCHAR(255) NOT NULL,
            short_url VARCHAR(255),
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "question_diificulty": """
        CREATE TABLE IF NOT EXISTS question_diificulty (
            id INTEGER PRIMARY KEY,
            difficulty_level VARCHAR(20) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "question_level": """
        CREATE TABLE IF NOT EXISTS question_level (
            s_no SERIAL PRIMARY KEY,
            level_name VARCHAR(255) NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "ai_models": """
        CREATE TABLE IF NOT EXISTS ai_models (
            s_no SERIAL PRIMARY KEY,
            model_name VARCHAR(255)
        )
    """,
    "subjects": """
        CREATE TABLE IF NOT EXISTS subjects (
            s_no SERIAL PRIMARY KEY,
            s_name VARCHAR(50) NOT NULL,
            short_url VARCHAR(50) NOT NULL,
            stream INTEGER NOT NULL,
            employee_id INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "chapters": """
        CREATE TABLE IF NOT EXISTS chapters (
            s_no SERIAL PRIMARY KEY,
            s_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            c_name VARCHAR(255) NOT NULL,
            weightage INTEGER NOT NULL DEFAULT 0,
            "order" INTEGER,
            short_url VARCHAR(50) NOT NULL,
            employee_id INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "topics": """
        CREATE TABLE IF NOT EXISTS topics (
            s_no SERIAL PRIMARY KEY,
            s_id INTEGER NOT NULL,
            c_id INTEGER NOT NULL,
            t_name VARCHAR(255) NOT NULL,
            short_url VARCHAR(50) NOT NULL,
            employee_id INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1,
            is_deleted INTEGER NOT NULL DEFAULT 0,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "ai_questions": """
        CREATE TABLE IF NOT EXISTS ai_questions (
            s_no SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 0,
            uuid VARCHAR(100) NOT NULL DEFAULT '',
            stream INTEGER NOT NULL DEFAULT 0,
            question TEXT NOT NULL,
            correct_opt VARCHAR(255) NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            answer_desc TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 0,
            question_type INTEGER NOT NULL DEFAULT 0,
            t_id INTEGER NOT NULL DEFAULT 0,
            s_id INTEGER NOT NULL DEFAULT 0,
            c_id INTEGER NOT NULL DEFAULT 0,
            cognitive_level INTEGER NOT NULL DEFAULT 0,
            keywords TEXT,
            estimated_time DOUBLE PRECISION,
            "QC" TEXT,
            reason TEXT,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model TEXT,
            model_id INTEGER NOT NULL DEFAULT 0
        )
    """,
    "ai_questions_repo": """
        CREATE TABLE IF NOT EXISTS ai_questions_repo (
            s_no SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL DEFAULT 0,
            uuid VARCHAR(100) NOT NULL DEFAULT '',
            stream INTEGER NOT NULL DEFAULT 0,
            question TEXT NOT NULL,
            correct_opt VARCHAR(255) NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            answer_desc TEXT NOT NULL,
            difficulty INTEGER NOT NULL DEFAULT 0,
            question_type INTEGER NOT NULL DEFAULT 0,
            t_id INTEGER NOT NULL DEFAULT 0,
            s_id INTEGER NOT NULL DEFAULT 0,
            c_id INTEGER NOT NULL DEFAULT 0,
            cognitive_level INTEGER NOT NULL DEFAULT 0,
            keywords TEXT,
            estimated_time DOUBLE PRECISION,
            "QC" TEXT,
            reason TEXT,
            added_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            model TEXT,
            model_id INTEGER NOT NULL DEFAULT 0
        )
    """,
}

# Tables where we just copy data (already have Postgres DDL from ORM)
ORM_TABLES = ["qbank_generation_jobs", "qbank_generation_items", "qbank_job_events"]

# Ordered migration list
TABLES_TO_MIGRATE = list(DDL.keys()) + ORM_TABLES


def get_mysql_columns(mysql_engine, table_name: str) -> list[str]:
    """Get column names from MySQL table."""
    with mysql_engine.connect() as conn:
        result = conn.execute(text(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = 'cs_qbank' AND table_name = :tbl "
            f"ORDER BY ordinal_position"
        ), {"tbl": table_name})
        return [row[0] for row in result]


def migrate_table(mysql_engine, pg_engine, table_name: str) -> int:
    """Migrate a single table from MySQL to Postgres."""

    # Check if table already has data on Supabase
    try:
        with pg_engine.connect() as conn:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
            if count and count > 0:
                print(f"  ⏭️  Already has {count} rows — skipping")
                return 0
    except Exception:
        pass  # Table doesn't exist yet, will be created

    # Create table if needed
    if table_name in DDL:
        with pg_engine.begin() as conn:
            conn.execute(text(DDL[table_name]))

    # Get columns from MySQL
    columns = get_mysql_columns(mysql_engine, table_name)
    col_select = ", ".join(f"`{c}`" for c in columns)

    # Read all rows from MySQL
    with mysql_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT {col_select} FROM `{table_name}`")).fetchall()

    if not rows:
        print(f"  📭 Empty in MySQL")
        return 0

    # Convert to list of dicts
    clean_rows = []
    for row in rows:
        clean = {}
        for i, col in enumerate(columns):
            value = row[i]
            if isinstance(value, bytes):
                try:
                    value = value.decode("utf-8")
                except Exception:
                    value = str(value)
            clean[col] = value
        clean_rows.append(clean)

    # Check which columns exist in Postgres table
    with pg_engine.connect() as conn:
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :tbl AND table_schema = 'public'"
        ), {"tbl": table_name})
        pg_columns = {row[0] for row in result}

    # Only insert columns that exist in both
    common_columns = [c for c in columns if c in pg_columns]
    if not common_columns:
        print(f"  ❌ No matching columns between MySQL and Postgres!")
        return 0

    skipped_cols = set(columns) - set(common_columns)
    if skipped_cols:
        print(f"  ⚠️  Skipping columns not in Postgres: {skipped_cols}")

    # Insert in batches
    col_list = ", ".join(f'"{c}"' for c in common_columns)
    param_list = ", ".join(f":{c}" for c in common_columns)
    insert_sql = text(f'INSERT INTO "{table_name}" ({col_list}) VALUES ({param_list})')

    batch_size = 500
    with pg_engine.begin() as conn:
        for i in range(0, len(clean_rows), batch_size):
            batch = [{c: row[c] for c in common_columns} for row in clean_rows[i:i + batch_size]]
            conn.execute(insert_sql, batch)

    return len(clean_rows)


def reset_sequences(pg_engine):
    """Reset Postgres sequences to max(pk) + 1 for all migrated tables."""
    print("\n🔄 Resetting Postgres sequences...")
    with pg_engine.begin() as conn:
        result = conn.execute(text("""
            SELECT t.relname AS table_name,
                   a.attname AS column_name,
                   pg_get_serial_sequence(t.relname, a.attname) AS seq_name
            FROM pg_class t
            JOIN pg_attribute a ON a.attrelid = t.oid
            WHERE pg_get_serial_sequence(t.relname, a.attname) IS NOT NULL
              AND t.relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
        """))
        for row in result:
            tbl, col, seq = row
            max_val = conn.execute(text(f'SELECT COALESCE(MAX("{col}"), 0) FROM "{tbl}"')).scalar()
            conn.execute(text(f"SELECT setval('{seq}', :val)"), {"val": max_val + 1})
            print(f"  {tbl}.{col} → {max_val + 1}")


def main() -> None:
    print("=" * 60)
    print("MySQL → Supabase Data Migration")
    print("=" * 60)
    print()

    mysql_engine = create_engine(MYSQL_URL, pool_pre_ping=True)
    pg_engine = create_engine(SUPABASE_URL, pool_pre_ping=True)

    # Test connections
    print("Testing MySQL...", end=" ", flush=True)
    with mysql_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅")

    print("Testing Supabase...", end=" ", flush=True)
    with pg_engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("✅")
    print()

    total = 0
    results = []

    for tbl in TABLES_TO_MIGRATE:
        print(f"📦 {tbl}...")
        try:
            count = migrate_table(mysql_engine, pg_engine, tbl)
            total += count
            results.append((tbl, count, "✅"))
            if count > 0:
                print(f"  ✅ {count} rows")
        except Exception as e:
            results.append((tbl, 0, "❌"))
            print(f"  ❌ {e}")

    reset_sequences(pg_engine)

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for tbl, count, status in results:
        print(f"  {status} {tbl}: {count} rows")
    print(f"\nTotal: {total} rows migrated")
    print("🎉 Done!")


if __name__ == "__main__":
    main()
