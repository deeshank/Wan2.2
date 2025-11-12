# Text-to-Video (T2V) Support Added ✅

## What's New

The FastAPI server now supports **both Image-to-Video (I2V) and Text-to-Video (T2V)** generation!

## Changes Made

### 1. **server.py** - Enhanced with T2V Support
- ✅ Added `WanT2V` model loading
- ✅ New `/generate-t2v` endpoint for text-only video generation
- ✅ Separate job processing for I2V and T2V
- ✅ Both models loaded simultaneously for fast switching
- ✅ Updated health check to show both model statuses

### 2. **bootstrap.sh** - Downloads Both Models
- ✅ Downloads I2V model (~100GB)
- ✅ Downloads T2V model (~100GB)
- ✅ Total: ~200GB of model weights

### 3. **API_GUIDE.md** - Complete Documentation
- ✅ T2V endpoint documentation
- ✅ Python examples for both I2V and T2V
- ✅ Model comparison table
- ✅ Updated performance metrics

## API Endpoints

### Image-to-Video (I2V)
```bash
POST /generate
- Requires: image file + optional prompt
- Use case: Animate existing images
```

### Text-to-Video (T2V)
```bash
POST /generate-t2v
- Requires: text prompt only
- Use case: Generate videos from scratch
```

## Quick Examples

### I2V - Animate an Image
```bash
curl -X POST "http://localhost:8000/generate" \
  -F "image=@cat.jpg" \
  -F "prompt=A cat walking on the beach" \
  -F "size=1280*720"
```

### T2V - Generate from Text
```bash
curl -X POST "http://localhost:8000/generate-t2v" \
  -F "prompt=Two cats boxing on a stage" \
  -F "size=1280*720"
```

## Key Differences

| Feature | I2V | T2V |
|---------|-----|-----|
| **Input** | Image + Optional Prompt | Text Prompt Only |
| **Default Shift** | 5.0 | 12.0 |
| **Default Guide Scale** | 3.5 | 3.0 |
| **Aspect Ratio** | Follows input image | Fixed by size |
| **Generation Time** | ~3-4 min (720p) | ~3-4 min (720p) |

## Resource Requirements

### Storage
- **I2V Model**: ~100GB
- **T2V Model**: ~100GB
- **Total**: ~200GB

### GPU Memory
- **VRAM**: 70-75GB peak (per model)
- **Both models loaded**: Uses same VRAM (models offload when not in use)

### Generation
- **Queue**: Single worker processes one job at a time
- **Switching**: Automatic between I2V and T2V jobs

## Installation

### For New Deployments
```bash
./bootstrap.sh
```
The script will automatically download both models.

### For Existing Deployments
```bash
# Download T2V model
cd /workspace/Wan2.2
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B --local-dir ./Wan2.2-T2V-A14B

# Restart server
python server.py
```

## Testing

### Check Health
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "models": {
    "i2v_loaded": true,
    "t2v_loaded": true
  },
  "gpu_available": true,
  "gpu_name": "NVIDIA A100-PCIE-80GB",
  "queue_size": 0
}
```

### Test T2V Generation
```bash
curl -X POST "http://localhost:8000/generate-t2v" \
  -F "prompt=A beautiful sunset over the ocean with waves" \
  -F "size=1280*720" \
  -F "frame_num=81"
```

## Notes

1. **Both models stay loaded** in memory for fast switching between I2V and T2V jobs
2. **Model offloading** is enabled to manage VRAM efficiently
3. **Queue system** processes one job at a time (I2V or T2V)
4. **Job types** are tracked - check `/status/{job_id}` to see if it's I2V or T2V

## Troubleshooting

### T2V Model Not Loading
```bash
# Check if model exists
ls -lh /workspace/Wan2.2/Wan2.2-T2V-A14B

# If missing, download manually
huggingface-cli download Wan-AI/Wan2.2-T2V-A14B --local-dir ./Wan2.2-T2V-A14B
```

### Out of Memory
- Both models use ~70-75GB VRAM peak
- Ensure you have A100 80GB or equivalent
- Models offload automatically when not in use

### Slow Generation
- T2V uses `shift=12.0` by default (vs I2V's 5.0)
- This is intentional for better quality
- Reduce `sampling_steps` for faster (lower quality) results
