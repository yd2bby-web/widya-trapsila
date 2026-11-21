# WIDYA TRAPSILA v0.9.2

Pembaruan manajemen administrasi dan pembatasan akses komunikasi.

## Perubahan v0.9.2
- Data Siswa: edit, aktif/nonaktif, dan hapus dengan perlindungan relasi akun serta riwayat konseling.
- Akun Siswa: aktif/nonaktif, reset password sementara, dan hapus akun; riwayat chat yang terhubung mencegah penghapusan permanen.
- Pengurus: mempertahankan edit, aktif/nonaktif, dan hapus.
- Program Kerja: edit dan hapus.
- Pusat Download: edit metadata, ganti file di Cloudflare R2, dan hapus.
- Chat Universal diganti menjadi Chat Pengurus. Hanya administrator dan akun siswa yang cocok dengan data pengurus aktif yang dapat membaca/mengirim pesan; akses diperiksa di server.
- Konselor: edit profil, reset password melalui edit, aktif/nonaktif, dan hapus dengan perlindungan riwayat.
- Penugasan Konselor: daftar, ubah dengan penugasan ulang, dan hapus.
- Chat Konseling tetap privat dua arah; konselor dapat membaca dan membalas siswa yang sedang ditugaskan kepadanya. Riwayat konseling tidak menyediakan tombol hapus.
- Versi service worker diperbarui agar cache PWA diganti.

## Instalasi / deploy
1. Cadangkan proyek dan database Neon sebelum deploy.
2. Salin file proyek dari ZIP ini ke folder proyek lokal. Jangan mengganti `.env` yang sudah ada.
3. Pastikan environment variables Render tetap tersedia: DATABASE_URL, SECRET_KEY, BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_PASSWORD, R2_ENDPOINT_URL, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME.
4. Commit dan push ke branch `main`; Render akan melakukan deploy otomatis.
5. Uji login admin, akun siswa pengurus, akun siswa biasa, akun konselor, upload/ganti/hapus dokumen R2, dan percakapan privat.

## Catatan keamanan
- ZIP sumber tidak menyertakan `.env`, `.git`, atau database lokal.
- Jangan pernah mengunggah `.env` atau membagikan token/password. Jika rahasia pernah ikut terunggah, rotasi nilainya.
- Penghapusan data ditolak jika masih memiliki relasi/riwayat yang harus dipertahankan. Nonaktifkan akun/data sebagai pilihan aman.

## Catatan pengujian
Pemeriksaan sintaks Python dan JavaScript dilakukan pada paket ini. Uji integrasi langsung terhadap Neon, Cloudflare R2, dan deploy Render tetap perlu dilakukan pada lingkungan proyek pemilik.


## v0.9.2
- Dashboard siswa memiliki panel Pengumuman yang dikelola administrator.
- Login menampilkan pilihan Administrator, Siswa, dan Konselor serta memvalidasi role di server.
- Kartu pengurus publik hanya menampilkan foto yang benar-benar diunggah; tidak memakai foto pengganti.


## WIDYA TRAPSILA v0.9.3
- Menambahkan menu Data Anggota PIK-R khusus administrator.
- Data anggota terpisah dari Data Pengurus dan tidak membuat akun login.
- Mendukung tambah, edit, aktif/nonaktif, dan hapus dengan konfirmasi.
- Kolom data: NIS opsional, nama, kelas, jenis kelamin opsional, foto opsional, tanggal bergabung.
- Tabel `members` dibuat otomatis melalui `Base.metadata.create_all` saat aplikasi mulai.
- API anggota dibatasi untuk administrator.
