# QS Subject Journal Finder

Web app statis untuk mencari jurnal Scopus berdasarkan **QS Subject Area** (pemetaan via kode ASJC).

**Live:** https://bhq2506.github.io/qsjournal/

Setiap jurnal menampilkan **Nama Jurnal, Publisher, Quartile (SJR 2025)** dan **QS Subject Area**, dan judulnya bisa diklik menuju halaman Scopus (`https://www.scopus.com/sourceid/<id>`).

- 27.000 jurnal aktif · 56 QS subject · 5 broad faculty area
- Cari berdasarkan judul, publisher, atau ISSN/eISSN (tekan `/` untuk fokus ke kotak pencarian)
- Filter per QS subject, quartile (Q1–Q4, Not ranked), dan open access
- Tag QS subject pada tiap jurnal bisa diklik untuk pindah ke subject tersebut
- Link langsung ke subject: `.../#computer-science`, `.../#business-and-management-studies`, dst.

Tanpa build step, tanpa dependency — cukup `index.html` + `data/journals.json`.

## Deploy ke GitHub Pages

```bash
git init
git add .
git commit -m "QS Subject Journal Finder"
git branch -M main
git remote add origin https://github.com/bhq2506/qsjournal.git
git push -u origin main
```

Lalu di GitHub: **Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: `main` / `(root)` → Save**.
Situs akan tersedia di https://bhq2506.github.io/qsjournal/.

## Menjalankan secara lokal

`fetch()` tidak jalan jika `index.html` dibuka langsung sebagai file, jadi pakai web server kecil:

```bash
python -m http.server 8000
# buka http://localhost:8000
```

## Memperbarui data

Jika file Excel diperbarui (daftar Scopus atau SJR baru):

```bash
pip install openpyxl
python scripts/build_data.py path/ke/QS_Subject_ASJCode_Journal_.xlsx
git commit -am "Update data" && git push
```

Script membaca sheet `SJR 2025`, `Menu`, dan setiap sheet subject (baris 1–3 = judul, broad area, kode ASJC; header di baris 6; data mulai baris 7).

## Catatan metodologi

- Jurnal masuk ke suatu QS subject jika minimal satu kode ASJC-nya cocok dengan kode ASJC yang dipetakan QS ke subject tersebut. Satu jurnal bisa muncul di beberapa subject.
- Quartile adalah **SJR 2025 best quartile** lintas semua kategori Scopus jurnal tersebut, **bukan** quartile di kategori yang sesuai dengan QS subject. Jurnal yang tertulis Q1 bisa saja Q2/Q3 di kategori yang relevan.
- Jurnal tanpa data SJR ditandai *Not ranked*.
