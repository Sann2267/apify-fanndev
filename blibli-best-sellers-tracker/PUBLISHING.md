# Publikasi & Harga — Blibli Best Sellers Tracker

Langkah yang harus dilakukan di Apify Console. Kode sudah siap; yang tersisa
hanya konfigurasi akun dan Store.

Actor: https://console.apify.com/actors/YXN1ex9bJyQGHJapp

## 1. Verifikasi identitas (KYC)

Wajib sebelum actor berbayar bisa aktif. Console → **Settings → Billing** →
lengkapi verifikasi identitas dan data payout.

Tanpa ini, harga tidak bisa disimpan.

## 2. Publikasikan ke Apify Store

Console → actor → tab **Publication**.

- **Categories**: `ECOMMERCE` (kompetitor sejenis memakai kombinasi
  `ECOMMERCE` + `AUTOMATION`, atau `ECOMMERCE` + `DEVELOPER_TOOLS`)
- **Title** dan **Description** sudah terisi dari `.actor/actor.json`
- README sudah siap-publikasi

Tekan **Publish to Store**.

## 3. Pasang harga pay-per-event

Console → actor → tab **Monetization** → pilih **Pay per event**.

Buat **tepat dua** event berikut:

| Nama event | Judul | Harga |
| --- | --- | --- |
| `apify-actor-start` | Actor Start | **$0,05** |
| `category-tracked` | Category tracked | **$1,00** |

### Tiga hal yang mudah salah

**Nama event harus persis `category-tracked`.** Kode memanggil
`Actor.charge({ eventName: 'category-tracked' })` di
[src/main.js](src/main.js). Nama yang berbeda membuat penagihan gagal diam-diam
— actor tetap bekerja, tapi Anda tidak dibayar.

**Jangan aktifkan `apify-default-dataset-item`.** Event itu menagih tiap baris
dataset secara otomatis. Actor ini sudah menagih per kategori; mengaktifkan
keduanya berarti pengguna dibebani dua kali untuk pekerjaan yang sama.

**`apify-actor-start` ditagih platform secara otomatis.** Jangan menambahkan
kode untuk menagihnya — percobaan menagihnya sendiri akan gagal.

## 4. Kenapa per kategori, bukan per hasil

Diukur dari run nyata: 11 baris hasil dengan biaya $0,66 — sekitar **$0,06 per
baris**. Tarif per-hasil yang lazim di Apify Store berkisar $0,001–$0,005, jadi
menagih per baris akan membuat actor ini rugi sekitar dua puluh kali lipat.

Biaya sesungguhnya ditentukan jumlah kategori (300 permintaan halaman produk per
kategori), bukan jumlah baris. Harga mengikuti biaya.

Kategori tanpa daftar "Paling Laris" tidak ditagih, dan anggaran maksimum run
pengguna dihormati sejak awal — actor memindai sebanyak yang sanggup ditagih,
bukan memindai dulu lalu gagal menagih.

## 5. Setelah terbit

Uji dengan akun lain (atau minta teman) untuk memastikan tagihan muncul benar
pada run pertama. Periksa tab **Runs** → sebuah run → **Charges**.

Kalau `category-tracked` tidak muncul di sana, hampir pasti nama event di
Console tidak sama persis dengan yang di kode.
