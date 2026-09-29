# ECHO LOOP

Arena shooter dengan mekanik time-loop, dibuat pakai Python + pygame.

Waktu berulang setiap **8 detik**. Setiap loop yang selesai berubah jadi **Echo**, yaitu hantu dirimu sendiri yang mengulang persis semua gerakan dan tembakanmu di loop itu, lalu ikut bertarung di sampingmu. Semakin lama bertahan, semakin banyak pasukan "masa lalu" yang kamu punya. Tapi mereka juga bisa hilang.

## Cara Menjalankan

Butuh Python 3.8+ dan pygame.

```bash
pip install pygame
```

```bash
python echo_loop.py
```

## Kontrol

| Tombol | Aksi |
| --- | --- |
| `W A S D` / Panah | Bergerak |
| Mouse | Membidik |
| Klik kiri (tahan) | Menembak |
| `Space` / `Shift` / Klik kanan | Dash (kebal selama dash) |
| `P` / `Esc` | Pause |
| `Q` (saat pause) | Kembali ke menu |
| `R` / `Enter` (saat game over) | Main lagi |

## Mekanik Utama

### Echo
- Setiap 8 detik, rekaman loop-mu disimpan jadi satu Echo.
- Echo mengulang gerakan dan tembakanmu **frame per frame**. Peluru Echo juga melukai musuh.
- Maksimal **5 Echo** aktif. Kalau lebih, Echo paling lama hilang.
- Titik-titik biru di depan Echo menunjukkan jalur yang akan dilewatinya, jadi kamu bisa merencanakan kombinasi dengan dirimu yang dulu.
- **Tips:** anggap setiap loop sebagai "pemrograman" turret. Loop yang dipakai menembak satu jalur akan menjaga jalur itu terus.

### Echo Pecah vs Echo Dimakan
- **Pecah (shattered):** Echo yang tertabrak musuh biasa atau kena peluru musuh akan pecah untuk sisa loop itu, lalu **kembali di loop berikutnya**. Musuh yang menabraknya juga terkena 2 damage.
- **Dimakan (devoured):** Echo yang disentuh **Leech ungu** akan **hilang selamanya**, dan Leech jadi lebih besar serta lebih kuat.

### Skor & Combo
- Membunuh musuh berturut-turut menaikkan multiplier sampai **x8** (naik tiap 5 kill).
- Combo reset kalau tidak membunuh selama sekitar 1,6 detik, atau saat kamu terkena damage.
- Bonus skor setiap kali berhasil melewati satu loop.
- Highscore disimpan otomatis di `echo_loop_highscore.txt`.

### Nyawa
- Mulai dengan 3 hati, maksimal 5.
- Musuh kadang menjatuhkan hati (+1 HP). Kalau HP sudah penuh, jadi +150 skor.
- Setelah terkena damage, kamu kebal sebentar (karakter berkedip).

## Musuh

| Musuh | Bentuk | Perilaku |
| --- | --- | --- |
| **Chaser** | Lingkaran merah | Mengejar badan terdekat, baik kamu maupun Echo. Echo bisa jadi umpan. |
| **Splitter** | Lingkaran hijau | Lambat dan tebal, pecah jadi 2 mini saat mati. Muncul setelah ~18 detik. |
| **Shooter** | Belah ketupat kuning | Menjaga jarak dan menembakmu. Berkedip putih sebelum menembak. Muncul setelah ~32 detik. |
| **Leech** | Segitiga ungu | Memburu Echo dan memakannya permanen. Muncul mulai loop 3. **Prioritas utama.** |
| **Brute** | Segi delapan oranye | Tank dengan 14 HP, pecah jadi 4 mini. Muncul setelah ~60 detik. |

Tanda **X berkedip** muncul sebelum musuh spawn, jadi selalu ada waktu untuk bereaksi. Setiap awal loop ada gelombang musuh tambahan yang makin besar seiring loop bertambah.

## Kustomisasi

Semua angka balance ada di bagian `config` di awal [echo_loop.py](echo_loop.py):

| Konstanta | Default | Fungsi |
| --- | --- | --- |
| `LOOP_SECONDS` | `8` | Durasi satu loop |
| `MAX_ECHOES` | `5` | Jumlah Echo maksimal |
| `START_HP` / `MAX_HP` | `3` / `5` | Nyawa awal / maksimal |
| `PLAYER_SPEED` | `3.6` | Kecepatan gerak |
| `FIRE_COOLDOWN` | `8` | Jeda antar tembakan (frame) |
| `DASH_COOLDOWN` | `55` | Jeda dash (frame) |
| `MAX_ENEMIES` | `60` | Batas musuh di layar |
| `ENEMY_TYPES` | - | HP, kecepatan, warna, dan skor tiap musuh |

## Struktur File

```
echo_loop.py                 # seluruh game
echo_loop_highscore.txt      # dibuat otomatis setelah game over pertama
README.md
```
