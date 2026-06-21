# sosyal-halisaha-downloader

[![tests](https://github.com/nurosmanisik/sosyal-halisaha-downloader/actions/workflows/tests.yml/badge.svg)](https://github.com/nurosmanisik/sosyal-halisaha-downloader/actions/workflows/tests.yml)

Sosyal Hali Saha mac detay sayfalarinda tarayicida zaten erisilebilen video linklerini bulan ve indiren lokal Python aracidir. CLI ve `127.0.0.1:5000` uzerinden calisan basit web arayuzu vardir.

> Bu proje public video indirme servisi degildir. Uygulama kullanicinin kendi bilgisayarinda calismak uzere tasarlanmistir.

## Etik kullanim

Bu arac yalnizca erisim hakkiniz olan kendi mac kayitlarinizi indirmek icin tasarlanmistir.

- DRM, sifre kirma, giris atlatma veya yetki asma yapmaz.
- Gizli, ozel veya yetkisiz icerik cekmek icin kullanilmamalidir.
- Video kayitlarinda kisiler gorunebilecegi icin paylasim ve saklama sorumlulugu kullaniciya aittir.
- Sosyal Hali Saha ile resmi baglantisi yoktur.

## Ozellikler

- Mac detay linkinden `.mp4` veya `.m3u8` video linklerini bulur.
- Direkt video linklerini indirebilir.
- Otomatik mac bulma modunda il, ilce, tesis, tarih, saat ve saha secimiyle maci arar.
- Birden fazla mac veya video varsa secim listesi gosterir.
- Direkt `.mp4` indirmelerinde `aria2c` ile hizli ve resume destekli indirme dener.
- `yt-dlp` fallback destegi vardir.
- Kalan sure, hiz, indirilen/kalan boyut ve pause/resume/cancel iceren lokal web arayuzu vardir.
- Varsayilan indirme klasoru: `~/Downloads/SosyalHaliSaha`.

## Kurulum

Projeyi klonlayin:

```bash
git clone https://github.com/nurosmanisik/sosyal-halisaha-downloader.git
cd sosyal-halisaha-downloader
```

Python sanal ortamini olusturun ve paketleri kurun:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

macOS icin indirme araclarini Homebrew ile kurun:

```bash
brew install yt-dlp aria2 ffmpeg
```

## Mac uygulamasi gibi kullanma

Native Mac uygulamasi icin desktop bagimliliklarini kurun:

```bash
.venv/bin/python -m pip install -r requirements-desktop.txt
```

Uygulamayi paketleyin:

```bash
packaging/macos/build_app.sh
```

Olusan native uygulama:

```text
dist/Sosyal Hali Saha Downloader.app
```

Bu uygulama tarayici yerine kendi Mac penceresinde acilir. Pencere kapaninca lokal server da kapanir.

Desktop/iCloud altinda paketlerken macOS imza uyarisi gorebilirsiniz. Bu genelde file-provider metadata'sindan kaynaklanir; lokal kullanim icin paket yine olusur.

Alternatif olarak hafif tarayici launcher uygulamasini olusturabilirsiniz:

```bash
scripts/make_macos_app.sh
```

Olusan launcher:

```text
Sosyal Hali Saha Downloader.app
```

Uygulamaya cift tiklayinca:

- Lokal server gerekiyorsa baslatilir.
- Server zaten calisiyorsa tekrar baslatilmaz.
- Tarayici otomatik olarak `http://127.0.0.1:5000` adresini acar.

Server'i durdurmak icin:

```bash
scripts/stop_web.sh
```

Launcher loglari:

```text
.launcher/web.log
```

Not: Her iki `.app` de lokalde calisir. Projeyi public server olarak yayinlamaz.

## Web arayuzu

Lokal arayuzu baslatin:

```bash
.venv/bin/python app.py
```

Tarayicida acin:

```text
http://127.0.0.1:5000
```

Web arayuzunde iki mod vardir:

- `Link ile indir`: mac detay linki veya direkt video linki girilir.
- `Maci otomatik bul`: tarih, saat, il, ilce, tesis ve saha secilir; sistem mac detay linkini ve video linklerini bulur.

Varsayilan otomatik profil:

```text
Il: Istanbul
Ilce: Uskudar
Tesis: Ufuk Hali Saha
Saha: Ust Saha
Saat: 11:00
```

## CLI kullanimi

Mac detay linkinden indirme:

```bash
.venv/bin/python main.py "https://sosyalhalisaha.com/mac-detay/174415967"
```

Direkt video linkinden indirme:

```bash
.venv/bin/python main.py "https://s1.sosyalhalisaha.com/matches/disk5/shst34s12/build/20260619230002.1-1.mp4"
```

Farkli klasore indirme:

```bash
.venv/bin/python main.py URL --output ~/Downloads/Maclar
```

Sadece bulunan linkleri gosterme:

```bash
.venv/bin/python main.py URL --dry-run
```

Ek secenekler:

```bash
.venv/bin/python main.py URL --connections auto
.venv/bin/python main.py URL --connections 16
.venv/bin/python main.py URL --use-ytdlp
.venv/bin/python main.py URL --use-aria2
.venv/bin/python main.py URL --discover-cameras
.venv/bin/python main.py URL --select 1
.venv/bin/python main.py URL --output-name mac-final.mp4
.venv/bin/python main.py URL --overwrite
.venv/bin/python main.py URL --no-preflight
.venv/bin/python main.py URL --dry-run --json
.venv/bin/python main.py --history
```

## Davranis

- Sadece `http` ve `https` URL kabul eder.
- `shell=True` kullanmaz; dis komutlari liste argumaniyla calistirilir.
- Direkt `.mp4` linklerinde once `aria2c` denenir.
- `aria2c` yoksa veya basarisiz olursa `yt-dlp` fallback denenir.
- `.m3u8` linklerinde `yt-dlp` kullanilir; video yeniden encode edilmez.
- Indirme oncesi preflight kontrolu ile boyut, icerik turu ve resume destegi okunur.
- `--connections auto` sunucu parcali indirmeyi desteklemiyorsa tek baglantiya duser.
- Eksik dosya varsa resume devam eder; ayni dosyayi bastan indirmek icin `--overwrite` gerekir.
- Basarili indirmeler `~/Downloads/SosyalHaliSaha/downloads.jsonl` dosyasina kaydedilir.

## Test

```bash
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m py_compile app.py downloader.py extractor.py finder.py jobs.py utils.py main.py camera.py preflight.py history.py desktop_app.py
node --check static/app.js
```

## Gelistirme

Gelistirme araclarini kurmak icin:

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
```

Kod kalitesi kontrolu:

```bash
.venv/bin/python -m ruff check .
```

## GitHub'a yayinlama

Bu klasor henuz Git repo degilse:

```bash
git init
git branch -M main
git add .
git commit -m "Initial release"
git remote add origin https://github.com/nurosmanisik/sosyal-halisaha-downloader.git
git push -u origin main
```

Commit oncesi kontrol:

```bash
git status --short
```

`.venv`, `.idea`, `__pycache__`, indirilen videolar, loglar ve lokal gecmis dosyalari commit'e girmemelidir.

## Olası hatalar ve cozumler

`yt-dlp veya aria2c bulunamadi`

```bash
brew install yt-dlp aria2 ffmpeg
```

`Sayfada video linki bulunamadi`

- Linki tarayicida acip erisebildiginizden emin olun.
- Gerekirse direkt `.mp4` veya `.m3u8` linkini programa verin.

`Bu tarih ve saatte mac bulunamadi`

- Tarih, saat, tesis ve saha secimini kontrol edin.
- Saha adini `Ust Saha` veya `Alt Saha` olarak deneyin.
- Mac kaydi henuz yayinlanmamis olabilir.

`Port 5000 kullaniliyor`

- Eski lokal sunucuyu kapatin ve tekrar deneyin.
- macOS'ta AirPlay Receiver bazen 5000 portunu kullanabilir.

`aria2c ile indirme basarisiz oldu`

```bash
.venv/bin/python main.py URL --use-aria2 --connections 4
```

Sorun devam ederse otomatik fallback icin `--use-aria2` vermeden calistirin.
