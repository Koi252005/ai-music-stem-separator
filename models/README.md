# Models Directory

This directory holds pretrained model weights.  
**Model files are NOT committed to git** (too large; governed by their own licenses).  
Download each model once using the commands below.

---

## 1. MelBand-Roformer Guitar (becruily)

| Field | Value |
|-------|-------|
| **Model name** | `mel_band_roformer_guitar` |
| **Repository** | https://huggingface.co/becruily/mel-band-roformer-guitar |
| **License** | See model page on Hugging Face |
| **Size** | ~45 MB |
| **Stems** | `electric_guitar`, `no_electric_guitar` |
| **Expected path** | `models/mel_band_roformer_guitar/becruily_guitar.ckpt` |

### Download (PowerShell)

```powershell
$dir = "models\mel_band_roformer_guitar"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$base = "https://huggingface.co/becruily/mel-band-roformer-guitar/resolve/main"
Invoke-WebRequest "$base/config_guitar_becruily.yaml" -OutFile "$dir\config_guitar_becruily.yaml" -UseBasicParsing
Invoke-WebRequest "$base/becruily_guitar.ckpt"        -OutFile "$dir\becruily_guitar.ckpt" -UseBasicParsing
```

---

## 2. Demucs — htdemucs_ft (4-stem)

| Field | Value |
|-------|-------|
| **Model name** | `htdemucs_ft` |
| **Repository** | https://github.com/facebookresearch/demucs |
| **License** | MIT |
| **Size** | ~320 MB (downloaded automatically by demucs on first use) |
| **Stems** | `vocals`, `drums`, `bass`, `other` |
| **Storage** | Cached in `~/.cache/torch/hub/` by demucs |

> **Download:** Run automatically by demucs when first used. No manual action needed.

---

## 3. Demucs — htdemucs_6s (6-stem)

| Field | Value |
|-------|-------|
| **Model name** | `htdemucs_6s` |
| **Repository** | https://github.com/facebookresearch/demucs |
| **License** | MIT |
| **Size** | ~320 MB (downloaded automatically) |
| **Stems** | `vocals`, `drums`, `bass`, `guitar`, `piano`, `other` |
| **Storage** | Cached in `~/.cache/torch/hub/` by demucs |

> **Download:** Run automatically by demucs when first used. No manual action needed.

---

## Notes

- **Percussion:** Demucs does NOT isolate percussion separately. `drums` = the full drum kit. `other` = keys, synth, and anything not in a named stem.
- **Guitar in htdemucs_6s:** This is a general guitar stem (acoustic + electric). For dedicated electric guitar separation, use the MelBand-Roformer Guitar model (mode 1).
- **VRAM:** htdemucs_ft/6s require ~4–8 GB VRAM. Falls back to CPU automatically.
