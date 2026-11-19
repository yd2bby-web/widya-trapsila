# PIK-R Digital Center — SMP Negeri 1 Wonogiri

Starter project tahap 1: FastAPI, SQLAlchemy, login JWT, role dasar, database SQLite lokal / PostgreSQL cloud, dan import data siswa XLSX.

## Menjalankan di Windows (PowerShell)

1. Install Python 3.12.
2. Buka folder proyek di VS Code atau terminal.
3. Buat virtual environment:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

4. Salin `.env.example` menjadi `.env`, lalu ganti `SECRET_KEY` dan password admin.
5. Jalankan:

   ```powershell
   uvicorn app.main:app --reload
   ```

6. Buka `http://127.0.0.1:8000` dan dokumentasi API di `http://127.0.0.1:8000/docs`.

## Akun admin awal

Diambil dari `BOOTSTRAP_ADMIN_USERNAME` dan `BOOTSTRAP_ADMIN_PASSWORD` dalam `.env`. Ganti password contoh sebelum menjalankan aplikasi dan jangan unggah file `.env` ke GitHub.

## Template Excel

File `student_template.xlsx` sudah disertakan. Header wajib: `NIS | Nama Siswa | Kelas`. Kolom keempat `NISN` bersifat opsional.

Import: `POST /api/admin/students/import` dengan Bearer token admin dan file `.xlsx`.

## Catatan penting sebelum dipakai siswa

Ini fondasi pengembangan, belum siap produksi. Sebelum data siswa asli dimasukkan, perlu ditambahkan migrasi database, reset password, verifikasi akun, pembatasan percobaan login, audit log, backup otomatis, persetujuan sekolah/orang tua sesuai kebijakan, kebijakan privasi, dan pengamanan konseling. Jangan gunakan data siswa asli pada tahap uji coba.
