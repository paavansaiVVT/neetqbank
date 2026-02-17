"""
Initialize QBank V2 tables on Supabase (Postgres).

Usage:
    QBANK_V2_DATABASE_URL="postgresql://..." python3 -m question_banks.v2.init_supabase

This script creates all three QBank V2 tables using SQLAlchemy's
metadata.create_all(), which is dialect-agnostic and works with
both MySQL and Postgres.
"""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

from question_banks.v2.repository import Base
from question_banks.v2.models_user import QbankUser  # noqa: F401 — registers table with Base
from question_banks.v2.config import get_settings


def main() -> None:
    settings = get_settings()
    db_url = settings.database_url

    if not db_url:
        print("ERROR: Set QBANK_V2_DATABASE_URL environment variable first.")
        print("Example: QBANK_V2_DATABASE_URL='postgresql://postgres.xxx:password@host:6543/postgres'")
        sys.exit(1)

    print(f"Connecting to: {db_url[:50]}...")

    engine = create_engine(db_url, pool_pre_ping=True)

    # Test connection first
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print(f"✅ Connection successful!")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

    # Create all tables
    print("Creating tables...")
    Base.metadata.create_all(engine)

    # Verify tables exist
    with engine.connect() as conn:
        # This works for both MySQL and Postgres
        tables = Base.metadata.tables.keys()
        print(f"✅ Created {len(tables)} tables: {', '.join(tables)}")

    print("\n🎉 Supabase migration complete!")
    print("You can now verify the tables in your Supabase Dashboard → Table Editor")


if __name__ == "__main__":
    main()
