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


## Update v0.4.0 — Akun Siswa

- Administrator dapat membuat akun untuk seluruh siswa aktif yang belum memiliki akun.
- Username siswa menggunakan NIS.
- Password awal dibuat acak per siswa dan hanya ditampilkan satu kali untuk diunduh sebagai CSV.
- Siswa dapat login dari halaman yang sama dan melihat identitasnya.
- Password awal wajib diganti dengan password pribadi minimal 10 karakter.
- Penambahan kolom `users.password_change_required` dilakukan otomatis secara aditif saat aplikasi dijalankan.

Catatan operasional:
1. Import data siswa terlebih dahulu.
2. Masuk sebagai administrator, buka menu **Akun Siswa**, lalu pilih **Buat Akun Siswa**.
3. Unduh CSV kredensial dan bagikan hanya kepada siswa yang bersangkutan.
4. Jangan kirim file CSV kredensial melalui grup umum.


## Pusat Download (v0.6.0)

Pusat Download memakai bucket Cloudflare R2 private. Metadata dokumen berada di Neon; file biner disimpan di R2. Admin mengunggah melalui menu Pusat Download, sedangkan siswa harus login untuk melihat dan mengunduh. Link unduhan bertanda tangan berlaku 10 menit. Batas file 25 MB.

Tambahkan environment variables berikut pada Render (jangan masukkan secret ke GitHub):
- `R2_ENDPOINT_URL` = `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME`

Buat bucket R2 private dan token API dengan izin Object Read & Write hanya untuk bucket tersebut.


## v0.6.1 — Perbaikan akses Pusat Download siswa

- Menambahkan tombol pintas Pusat Download pada header Area Siswa.
- Menandai panel Pusat Download secara eksplisit agar tampil pada dashboard siswa.
- Daftar dokumen dimuat saat dashboard siswa dibuka; filter kategori tetap tersedia.
- Akses unduh tetap menggunakan endpoint terautentikasi.
