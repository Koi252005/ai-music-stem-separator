# AI Music Stem Separator 🎸🥁🎹

> **Đồ án môn Trí tuệ Nhân tạo**  
> Tách nhạc cụ từ bài hát bằng AI — website và CLI hoàn chỉnh.

---

## Giới thiệu

**AI Music Stem Separator** là một ứng dụng web cho phép tách bất kỳ bài hát nào thành các thành phần riêng biệt (stems): vocals, drums, bass, guitar, piano... bằng các model AI tiên tiến.

Dự án được xây dựng trên nền tảng CLI `guitar-bt` ban đầu (tách electric guitar chuyên dụng), sau đó mở rộng thành website đầy đủ tính năng với nhiều model.

---

## Tính năng

- 🎸 **Electric Guitar chuyên dụng** — MelBand-Roformer Guitar (becruily), cô lập guitar điện sạch hơn model tổng quát
- 🎼 **Stem cơ bản** — Demucs htdemucs_ft: vocals, drums, bass, other
- 🎹 **Stem mở rộng** — Demucs htdemucs_6s: vocals, drums, bass, guitar, piano, other
- 🎤 **Vocal chất lượng cao** — htdemucs_ft tối ưu cho vocal
- 🎶 **Backing Track** — Mix tự động tất cả stems trừ vocals
- 🎵 **Instrumental** — Tương tự Backing Track (khi model chỉ có 1 vocal stem)
- ⬇️ **Tải từng stem** hoặc **tải ZIP** toàn bộ
- 🖥️ **CLI cũ vẫn hoạt động** độc lập (`remove_guitar.py`)
- 🌐 **Upload drag & drop**, theo dõi tiến độ real-time
- ⚡ **Auto CPU/CUDA** — tự chọn GPU nếu có

---

## Kiến trúc

```
project/
├── app/                        # FastAPI web app
│   ├── main.py                 # Entry point
│   ├── config.py               # Cấu hình tập trung
│   ├── utils.py                # Sanitize filename
│   ├── routes/jobs.py          # REST API
│   ├── services/job_service.py # Job queue & background worker
│   ├── separators/
│   │   ├── base.py             # Abstract base
│   │   ├── guitar_separator.py # Adapter cho MelBand-Roformer
│   │   └── demucs_separator.py # Adapter cho Demucs
│   ├── templates/index.html    # Frontend HTML
│   └── static/css/ js/         # CSS & JS thuần
├── legacy_cli/                 # CLI gốc (không sửa)
│   ├── remove_guitar.py
│   └── roformer_engine.py
├── roformer_arch/              # Vendored model architecture
├── models/                     # Model weights (gitignored)
│   └── README.md               # Hướng dẫn tải model
├── tests/                      # Test suite
├── remove_guitar.py            # CLI entry point (giữ nguyên)
├── roformer_engine.py          # Guitar engine (giữ nguyên)
├── run.py                      # Khởi động web server
├── THIRD_PARTY_NOTICES.md      # Attribution
└── .env.example
```

---

## Danh sách Model

| Chế độ | Model | Stems | Kích thước |
|--------|-------|-------|------------|
| Electric Guitar | MelBand-Roformer Guitar (becruily) | electric_guitar, no_electric_guitar | ~45 MB |
| Stem Basic | htdemucs_ft (Demucs) | vocals, drums, bass, other | ~320 MB (auto download) |
| Stem Extended | htdemucs_6s (Demucs) | vocals, drums, bass, guitar, piano, other | ~320 MB (auto download) |
| Vocal HQ | htdemucs_ft | vocals, drums, bass, other | Dùng chung với Stem Basic |

> **Lưu ý:** Demucs không tách percussion riêng. `drums` = full drum kit. `other` = keys, synth, v.v.

---

## Nguồn Model

- **MelBand-Roformer Guitar:** https://huggingface.co/becruily/mel-band-roformer-guitar
- **Model architecture (roformer_arch/):** https://github.com/ZFTurbo/Music-Source-Separation-Training (MIT)
- **Demucs:** https://github.com/facebookresearch/demucs (MIT)

---

## License

- Code của project này: [MIT](LICENSE) (© 2026 0ji54n / Koi252005)
- Vendored architecture (`roformer_arch/`): MIT — xem [`roformer_arch/NOTICE.md`](roformer_arch/NOTICE.md)
- Guitar model weights: Xem trang Hugging Face của model
- Demucs: MIT

Xem chi tiết tại [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

## Cài đặt

### Yêu cầu

- Python 3.10+ (tested on 3.14)
- [FFmpeg](https://ffmpeg.org) trên PATH
- Git

### Bước 1: Clone và cài dependency

```powershell
git clone https://github.com/Koi252005/ai-music-stem-separator.git
cd ai-music-stem-separator

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Bước 2: Tải model guitar

```powershell
$dir = "models\mel_band_roformer_guitar"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$base = "https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main"
Invoke-WebRequest "$base/config_guitar_becruily.yaml" -OutFile "$dir\config_guitar_becruily.yaml" -UseBasicParsing
Invoke-WebRequest "$base/becruily_guitar.ckpt" -OutFile "$dir\becruily_guitar.ckpt" -UseBasicParsing
```

> Model Demucs được tải tự động khi dùng lần đầu.

---

## Cách chạy

### Website

```powershell
python run.py
# Mở trình duyệt: http://localhost:8000
```

Với hot-reload (dev mode):

```powershell
python run.py --reload
```

### CLI guitar (chức năng gốc)

```powershell
# Tạo backing track (loại bỏ guitar)
python remove_guitar.py "song.mp3"

# Giữ riêng phần guitar
python remove_guitar.py "song.mp3" --isolate -o guitar.wav

# Output WAV, dùng CPU
python remove_guitar.py "song.mp3" -f wav --device cpu

# Từ YouTube URL
python remove_guitar.py "https://www.youtube.com/watch?v=..."
```

---

## Cấu hình FFmpeg

FFmpeg phải có trên PATH. Tải tại https://ffmpeg.org/download.html

Windows (Chocolatey):
```powershell
choco install ffmpeg
```

Windows (Scoop):
```powershell
scoop install ffmpeg
```

Kiểm tra:
```powershell
ffmpeg -version
```

---

## Cấu hình CPU và CUDA

Trong `.env` (copy từ `.env.example`):

```
DEFAULT_DEVICE=auto    # auto | cpu | cuda
```

Hoặc qua giao diện web khi upload file.

| Device | Tốc độ | Yêu cầu |
|--------|--------|---------|
| CPU | Chậm (~1-3× thời lượng bài) | Không cần GPU |
| CUDA (GPU) | Nhanh (~10-30× CPU) | NVIDIA GPU + CUDA |
| Auto | Tự chọn tốt nhất | — |

---

## Giới hạn thực tế

- Tách stem không hoàn hảo — có thể bị rò tiếng (bleed) giữa các stems
- Guitar acoustic có thể bị phát hiện nhầm là electric guitar
- Demucs không tách percussion riêng khỏi drums
- GPU RTX 3050 Laptop (4 GB VRAM) có thể gặp lỗi OOM với bài dài → dùng CPU
- Thời gian xử lý CPU: khoảng 1–3× thời lượng bài hát

---

## Xử lý lỗi thường gặp

**`[Errno 22] Invalid argument`** — Tên file chứa ký tự đặc biệt. Hệ thống tự sanitize, nhưng đảm bảo FFmpeg đã cài.

**`ffmpeg not found`** — Cài FFmpeg và thêm vào PATH.

**`Guitar model not found`** — Chạy lệnh download model ở bước 2.

**CUDA OOM** — Chọn device = CPU trong giao diện web.

**`demucs not installed`** — Chạy `pip install demucs`.

---

## Chạy tests

```powershell
pip install pytest httpx
pytest tests/ -v
```

---

## Attribution

Project ban đầu: `guitar-bt` CLI (tách electric guitar) — phát triển bởi 0ji54n / Koi252005.  
Mở rộng thành website stem separator hoàn chỉnh.  
Chi tiết: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)
