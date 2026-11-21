import os
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

# Muat konfigurasi dari .env proyek
load_dotenv(override=True)

neon_url = os.getenv("NEON_DATABASE_URL", "").strip()
new_password = os.getenv("NEW_ADMIN_PASSWORD", "")

if not neon_url:
    raise SystemExit("ERROR: NEON_DATABASE_URL tidak ditemukan di .env")

if len(new_password) < 12:
    raise SystemExit("ERROR: NEW_ADMIN_PASSWORD minimal 12 karakter.")

# Normalisasi URL untuk psycopg 3
if neon_url.startswith("postgres://"):
    neon_url = neon_url.replace("postgres://", "postgresql+psycopg://", 1)
elif neon_url.startswith("postgresql://"):
    neon_url = neon_url.replace("postgresql://", "postgresql+psycopg://", 1)

# Tampilkan identitas database tanpa membocorkan username/password/URL lengkap
parsed = make_url(neon_url)
print("TARGET DATABASE:")
print("Host    :", parsed.host)
print("Port    :", parsed.port or 5432)
print("Database:", parsed.database)

# Wajib set sebelum app.database di-import
os.environ["DATABASE_URL"] = neon_url

from sqlalchemy import select
from app.database import SessionLocal
from app.models import User
from app.security import hash_password, verify_password


def main():
    db = SessionLocal()
    try:
        admin = db.scalar(select(User).where(User.username == "admin"))
        if admin is None:
            raise SystemExit("ERROR: Akun admin tidak ditemukan pada database target.")

        admin.password_hash = hash_password(new_password)
        db.commit()
        db.refresh(admin)

        # Verifikasi dilakukan SETELAH commit dan refresh
        verified = verify_password(new_password, admin.password_hash)
        print("Username direset:", admin.username)
        print("Akun aktif       :", admin.is_active)
        print("Verifikasi pasca-commit:", verified)

        if not verified:
            raise SystemExit("GAGAL: Hash password setelah commit tidak cocok.")

        print("RESET BERHASIL. Gunakan NEW_ADMIN_PASSWORD untuk login.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
