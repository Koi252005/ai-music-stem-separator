# Third-Party Notices

This document records all third-party code, models, and libraries incorporated
into this project, together with their licenses and attribution requirements.

---

## 1. Original Project: guitar-bt

| Field | Value |
|-------|-------|
| **Repository** | This project was developed starting from scratch by the repository owner (Koi252005 / khoiphan252005@gmail.com), with the guitar separation CLI `remove_guitar.py` and engine `roformer_engine.py` authored originally under MIT License (© 2026 0ji54n). |
| **What was kept** | `remove_guitar.py`, `roformer_engine.py`, `roformer_arch/` (vendored architecture), original `requirements.txt` and `README.md` |
| **What was added** | Full web application: FastAPI backend, job system, Demucs integration, backing track generation, frontend UI, test suite, this documentation. |
| **License** | MIT — see [`LICENSE`](LICENSE) |

---

## 2. Vendored Model Architecture: roformer_arch/

The files in `roformer_arch/` (`mel_band_roformer.py`, `attend.py`) are vendored
from upstream MIT-licensed projects and are **not** original to this repository.

### 2a. ZFTurbo / Music-Source-Separation-Training

- **Repository:** https://github.com/ZFTurbo/Music-Source-Separation-Training
- **Author:** Roman Solovyev (ZFTurbo)
- **License:** MIT License, Copyright (c) 2024 Roman Solovyev
- **What is used:** The MelBandRoformer model architecture (`mel_band_roformer.py`)
  and attention module (`attend.py`), lightly adapted (one import path change).
- **Full license text:** See [`roformer_arch/NOTICE.md`](roformer_arch/NOTICE.md)

### 2b. lucidrains / BS-RoFormer

- **Repository:** https://github.com/lucidrains/BS-RoFormer
- **Author:** Phil Wang (lucidrains)
- **License:** MIT License, Copyright (c) 2023 Phil Wang
- **What is used:** Original BS-RoFormer implementation from which ZFTurbo's
  variant is derived.
- **Full license text:** See [`roformer_arch/NOTICE.md`](roformer_arch/NOTICE.md)

---

## 3. Guitar Separation Model Weights

| Field | Value |
|-------|-------|
| **Model** | MelBand-Roformer Guitar by becruily |
| **Source** | https://huggingface.co/becruily/mel-band-roformer-guitar |
| **File** | `becruily_guitar.ckpt` (~45 MB) |
| **Status** | Downloaded at setup time; **not** distributed in this repository |
| **Terms** | Governed by the terms on the Hugging Face model page |

---

## 4. Demucs (Facebook Research)

| Field | Value |
|-------|-------|
| **Repository** | https://github.com/facebookresearch/demucs |
| **Author** | Facebook Research / Alexandre Défossez et al. |
| **License** | MIT License |
| **Version used** | demucs==4.0.1 (installed as dependency) |
| **What is used** | `htdemucs_ft` (4-stem) and `htdemucs_6s` (6-stem) pretrained models for general stem separation |
| **Models** | Downloaded automatically by demucs on first use |

---

## 5. Summary of Developed Additions

The following components were developed as part of this project (AI đồ án):

- `app/` — Complete FastAPI web application
- `app/separators/` — Adapter layer isolating guitar and Demucs models
- `app/services/` — Job management and audio mixing services  
- `app/routes/` — REST API endpoints
- `app/templates/` + `app/static/` — Frontend UI
- `tests/` — Test suite
- `models/README.md` — Model setup guide
- `THIRD_PARTY_NOTICES.md` — This file
- Updated `README.md`, `.gitignore`, `.env.example`

---

*This file was created to comply with the attribution requirements of the MIT
License and to provide transparent documentation of code provenance.*
