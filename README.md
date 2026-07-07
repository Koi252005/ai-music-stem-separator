# AI Music Stem Separator — StemAI

> **Đồ án môn Trí tuệ Nhân tạo** — Website tách nhạc cụ từ bài hát sử dụng AI.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.13%2B-green)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Demo

Upload file nhạc → AI tách thành **Vocals / Drums / Bass / Guitar / Piano** → Nghe thử từng stem và tải về.

**Chức năng chính:**
- 🎸 **Electric Guitar Isolation** — Model chuyên dụng MelBand-Roformer (becruily)
- 🎵 **4-Stem Split** — Vocals, Drums, Bass, Other (htdemucs_ft)
- 🎹 **6-Stem Split** — Thêm Guitar và Piano (htdemucs_6s)
- 🎤 **Vocal Isolator** — Tách vocal và backing track
- 🎛️ **Multi-stem Player** — Nghe đồng bộ, mute/solo/volume từng track
- 📊 **Waveform visualization** — Xem dạng sóng của từng stem

---

## Cài đặt

### Yêu cầu hệ thống

- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) — **bắt buộc** (cần có trong PATH)
- 4GB RAM tối thiểu (8GB khuyến nghị cho Demucs)
- GPU (CUDA) tùy chọn — sẽ tự dùng CPU nếu không có GPU

### Bước 1: Clone repository

```bash
git clone https://github.com/Koi252005/ai-music-stem-separator.git
cd ai-music-stem-separator
```

### Bước 2: Cài dependencies

```bash
pip install -r requirements.txt
```

### Bước 3: Kiểm tra FFmpeg

```bash
ffmpeg -version
```

Nếu chưa cài, download tại https://ffmpeg.org/download.html và thêm vào PATH.

### Bước 4: Tải model Guitar (đã có sẵn)

Model guitar (`becruily_guitar.ckpt`) đã nằm trong `models/mel_band_roformer_guitar/`.

> **Lưu ý:** File checkpoint (43MB) **không** được commit vào Git. Nếu chưa có, xem hướng dẫn tại `models/README.md`.

### Bước 5: Chạy server

```bash
python run.py
```

Mở trình duyệt: http://localhost:8000

#### Tùy chọn:

```bash
python run.py --host 127.0.0.1 --port 7860   # custom host/port
python run.py --reload                          # auto-reload khi sửa code
```

---

## Cách dùng

1. **Upload** file nhạc (MP3, WAV, FLAC, M4A — tối đa 200MB)
2. **Chọn chế độ** tách (Guitar / 4-Stem / 6-Stem / Vocal)
3. **Nhấn "Bắt đầu tách stem"** — AI xử lý trong background
4. **Nghe thử** trong Studio Player:
   - Phát đồng bộ tất cả stem
   - Mute/Solo từng track
   - Điều chỉnh volume riêng
   - Seek trên waveform
5. **Tải về** từng stem (WAV) hoặc tất cả (ZIP)

---

## Kiến trúc

```
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Đường dẫn và cấu hình
│   ├── utils.py             # Utilities
│   ├── routes/
│   │   └── jobs.py          # REST API: POST/GET/DELETE /api/jobs
│   ├── services/
│   │   └── job_service.py   # In-memory job queue + background worker
│   ├── separators/
│   │   ├── base.py          # BaseSeparator interface
│   │   ├── guitar_separator.py   # MelBand-Roformer Guitar model
│   │   └── demucs_separator.py   # Demucs htdemucs_ft / htdemucs_6s
│   ├── static/
│   │   ├── css/style.css    # Professional dark studio UI
│   │   └── js/app.js        # Web Audio API player + SSE client
│   └── templates/
│       └── index.html       # Single-page app shell
├── models/
│   └── mel_band_roformer_guitar/
│       ├── becruily_guitar.ckpt    # Guitar model checkpoint
│       └── config_guitar_becruily.yaml
├── legacy_cli/
│   └── remove_guitar.py     # CLI gốc (vẫn hoạt động độc lập)
├── roformer_arch/           # MelBand-Roformer architecture code
├── roformer_engine.py       # Inference engine cho guitar model
├── run.py                   # Khởi động server
└── requirements.txt
```

### API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| `GET` | `/api/health` | Health check |
| `GET` | `/api/models` | Danh sách models |
| `POST` | `/api/jobs` | Upload file + tạo job |
| `GET` | `/api/jobs/{id}` | Trạng thái job (JSON) |
| `GET` | `/api/jobs/{id}/events` | Server-Sent Events (real-time) |
| `GET` | `/api/jobs/{id}/stems/{stem}` | Stream file WAV (Range-aware) |
| `GET` | `/api/jobs/{id}/download` | Download ZIP tất cả stems |
| `POST` | `/api/jobs/{id}/cancel` | Hủy job |
| `DELETE` | `/api/jobs/{id}` | Xóa job + file |

---

## Models

### Electric Guitar (MelBand-Roformer)

- **Nguồn:** [becruily/mel-band-roformer-guitar](https://huggingface.co/becruily/mel-band-roformer-guitar)
- **Output:** `electric_guitar.wav` + `no_electric_guitar.wav`
- **Kích thước:** ~43MB checkpoint
- **Tốc độ (CPU):** ~30-90s cho bài 3 phút

### Demucs (htdemucs_ft)

- **Nguồn:** [facebookresearch/demucs](https://github.com/facebookresearch/demucs)
- **Output:** vocals, drums, bass, other
- **Tự động tải lần đầu** qua Demucs
- **Tốc độ (CPU):** ~2-5 phút cho bài 3 phút

### Demucs (htdemucs_6s)

- **Output:** vocals, drums, bass, guitar, piano, other
- **Tốc độ (CPU):** ~3-7 phút cho bài 3 phút

---

## Xử lý lỗi thường gặp

### "ffmpeg not found"
Cài FFmpeg và đảm bảo nó có trong PATH:
```bash
# Windows: Download từ https://ffmpeg.org/download.html
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

### "Guitar model not found"
Đảm bảo file tồn tại:
```
models/mel_band_roformer_guitar/becruily_guitar.ckpt
models/mel_band_roformer_guitar/config_guitar_becruily.yaml
```

### Demucs tải chậm lần đầu
Demucs tự download model (~130MB) lần đầu chạy. Cần kết nối internet.

### Server crash khi tách
Kiểm tra RAM — Demucs cần ~2-4GB. Đóng ứng dụng khác.

---

## Phát triển

```bash
# Chạy với auto-reload
python run.py --reload

# Test pipeline
python test_job.py
```

---

## Credits

- **MelBand-Roformer Guitar Model** — [becruily](https://huggingface.co/becruily) (MIT License)
- **Demucs** — [Facebook Research](https://github.com/facebookresearch/demucs) (MIT License)
- **FastAPI** — [Sebastián Ramírez](https://fastapi.tiangolo.com)

---

## License

MIT License — Xem file [LICENSE](LICENSE).
