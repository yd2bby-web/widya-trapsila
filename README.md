# WIDYA TRAPSILA v0.8.0 — Chat Konseling Privat

## Fitur
- Admin membuat akun konselor dengan username dan password awal (minimal 10 karakter).
- Admin menugaskan satu konselor utama untuk setiap siswa. Siswa yang sama dapat dipindahkan ke konselor lain.
- Konselor melihat hanya daftar siswa yang ditugaskan kepadanya.
- Siswa melihat konselor yang ditugaskan dan dapat mengirim pesan privat.
- Pesan tersimpan di database Neon dan diperbarui otomatis setiap 5 detik pada panel siswa/konselor.
- Chat konseling terpisah dari Chat Universal.
- Endpoint pesan memeriksa hak akses pada server untuk setiap permintaan; admin tidak memiliki endpoint untuk membaca isi percakapan.
- Perubahan database bersifat additive: menambah `students.counselor_user_id` dan tabel `counseling_messages`. Data siswa, akun, chat universal, dan dokumen yang ada tidak dihapus.

## Instalasi
1. Ekstrak ZIP ke folder proyek lama.
2. Salin/replace file proyek. Jangan timpa `.env` dan jangan hapus `.git` lokal.
3. Pastikan `requirements.txt` tetap digunakan seperti versi sebelumnya.
4. Jalankan:

```powershell
git add app/main.py app/models.py static/index.html README.md
git commit -m "WIDYA TRAPSILA v0.8.0 - Private Counseling Chat"
git push origin main
```

Render akan deploy otomatis. Migrasi kolom dan pembuatan tabel baru berjalan saat aplikasi startup. Tidak ada Environment variable baru.

## Cara menggunakan
1. Login sebagai admin → menu **Konselor**.
2. Buat akun konselor. Berikan username dan password awal secara pribadi kepada konselor.
3. Pilih siswa dan konselor pada bagian **Penugasan Konselor**, lalu simpan.
4. Konselor login memakai akun yang dibuat admin, pilih siswa binaan, lalu mulai percakapan.
5. Siswa login seperti biasa; panel **Konseling Privat** muncul setelah konselor ditugaskan.
6. Konselor dan siswa dapat mengganti password melalui panel masing-masing.

## Catatan privasi
- Admin mengelola akun dan penugasan, tetapi aplikasi tidak menyediakan tampilan admin untuk membaca pesan konseling.
- Akses percakapan dibatasi di backend berdasarkan identitas siswa dan konselor yang sedang ditugaskan.
- Satu siswa hanya memiliki satu konselor utama pada satu waktu.
- Percakapan disimpan sebagai data aplikasi biasa di database. Ini bukan enkripsi end-to-end; operator infrastruktur/database yang memiliki akses tingkat sistem secara teknis tetap dapat mengakses data. Terapkan kebijakan sekolah, persetujuan, dan prosedur perlindungan siswa sebelum digunakan untuk pengungkapan sensitif atau keadaan darurat.
