
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, select, text
from app.database import Base
from app.models import Student, User, Officer, Program

load_dotenv()

LOCAL_URL = "sqlite:///./pikr.db"

def normalize_url(url):
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

print("=== MIGRASI WIDYA TRAPSILA KE NEON ===")

neon_url = normalize_url(os.getenv("NEON_DATABASE_URL", "").strip())

if not neon_url:
    raise SystemExit("NEON_DATABASE_URL tidak ditemukan di .env")

source = create_engine(LOCAL_URL)
target = create_engine(neon_url, pool_pre_ping=True)

tables = [
    Student.__table__,
    User.__table__,
    Officer.__table__,
    Program.__table__,
]

try:
    Base.metadata.create_all(target)

    with target.connect() as conn:
        for table in tables:
            count = conn.execute(
                select(text("count(*)")).select_from(table)
            ).scalar_one()

            if count:
                raise RuntimeError(
                    f"Tabel {table.name} sudah berisi {count} data. "
                    "Migrasi dibatalkan."
                )

    with source.connect() as src, target.begin() as dst:
        for table in tables:
            rows = src.execute(select(table)).mappings().all()

            if rows:
                dst.execute(table.insert(), [dict(row) for row in rows])

            print(f"{table.name}: {len(rows)} data dipindahkan")

        for table in tables:
            dst.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table.name}), 1), "
                f"EXISTS (SELECT 1 FROM {table.name}))"
            ))

    print("\nMIGRASI BERHASIL.")

finally:
    source.dispose()
    target.dispose()
