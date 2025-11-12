# Wan2.2 I2V FastAPI Server Guide

## Quick Start


curl -sSL https://gist.githubusercontent.com/deeshank/e15e2f5e15d3598ae0cfcd753345aa05/raw/dc7c0ee87531110c2f8f719eb293266ac571d753/bootstrapv1.sh | bash

### 1. Deploy on RunPod

```bash
# Run the bootstrap script
./bootstrap.sh
```

The script will:
- Install system dependencies
- Clone the repository (dev branch)
- Install Python dependencies
- Download model weights (~100GB)
- Start the FastAPI server on port 8000

### 2. Access the API

- **API Root**: `http://your-pod-ip:8000`
- **Test UI**: `http://your-pod-ip:8000/test-ui`
- **Health Check**: `http://your-pod-ip:8000/health`

## API Endpoints

### 1. Generate Image-to-Video (I2V)

**POST** `/generate`

Generate a video from an image and optional text prompt.

**Parameters:**
- `image` (file, required): Input image
- `prompt` (string, optional): Text description of desired motion
- `negative_prompt` (string, optional): What to avoid in generation
- `size` (string, default: "1280*720"): Resolution as "width*height"
  - 720p: "1280*720"
  - 480p: "1024*576"
- `frame_num` (int, default: 81): Number of frames (must be 4n+1)
- `shift` (float, default: 5.0): Noise schedule shift (use 3.0 for 480p)
- `sampling_steps` (int, default: 40): Diffusion sampling steps
- `guide_scale` (float, default: 3.5): Guidance scale
- `sample_solver` (string, default: "unipc"): Solver type ("unipc" or "dpm++")
- `seed` (int, default: -1): Random seed (-1 for random)

**Example:**
```bash
curl -X POST "http://localhost:8000/generate" \
  -F "image=@cat.jpg" \
  -F "prompt=A cat walking on the beach" \
  -F "size=1280*720" \
  -F "frame_num=81" \
  -F "sampling_steps=40"
```

**Response:**
```json
{
  "job_id": "abc-123-def",
  "status": "queued",
  "message": "Job queued successfully",
  "config": {
    "size": "1280*720",
    "frame_num": 81,
    "sampling_steps": 40,
    "sample_solver": "unipc"
  }
}
```

### 2. Generate Text-to-Video (T2V)

**POST** `/generate-t2v`

Generate a video from text prompt only (no image required).

**Parameters:**
- `prompt` (string, required): Text description of the video
- `negative_prompt` (string, optional): What to avoid in generation
- `size` (string, default: "1280*720"): Resolution as "width*height"
  - 720p: "1280*720"
  - 480p: "1024*576"
- `frame_num` (int, default: 81): Number of frames (must be 4n+1)
- `shift` (float, default: 12.0): Noise schedule shift (T2V uses 12.0)
- `sampling_steps` (int, default: 40): Diffusion sampling steps
- `guide_scale` (float, default: 3.0): Guidance scale (T2V uses 3.0)
- `sample_solver` (string, default: "unipc"): Solver type ("unipc" or "dpm++")
- `seed` (int, default: -1): Random seed (-1 for random)

**Example:**
```bash
curl -X POST "http://localhost:8000/generate-t2v" \
  -F "prompt=Two anthropomorphic cats in boxing gear fighting on a stage" \
  -F "size=1280*720" \
  -F "frame_num=81" \
  -F "sampling_steps=40"
```

**Response:**
```json
{
  "job_id": "xyz-789-abc",
  "status": "queued",
  "message": "Job queued successfully",
  "type": "t2v",
  "config": {
    "size": "1280*720",
    "frame_num": 81,
    "sampling_steps": 40,
    "sample_solver": "unipc"
  }
}
```

### 3. Check Job Status

**GET** `/status/{job_id}`

**Example:**
```bash
curl "http://localhost:8000/status/abc-123-def"
```

**Response:**
```json
{
  "job_id": "abc-123-def",
  "status": "completed",
  "prompt": "A cat walking on the beach",
  "size": "1280*720",
  "created_at": "2025-01-15T10:30:00",
  "started_at": "2025-01-15T10:30:05",
  "completed_at": "2025-01-15T10:34:20",
  "processing_time_seconds": 255,
  "download_url": "/download/abc-123-def"
}
```

**Status values:**
- `queued`: Waiting in queue
- `processing`: Currently generating
- `completed`: Ready to download
- `failed`: Generation failed

### 4. Download Video

**GET** `/download/{job_id}`

**Example:**
```bash
curl "http://localhost:8000/download/abc-123-def" -o video.mp4
```

### 5. List Jobs

**GET** `/jobs?status={status}&limit={limit}`

**Parameters:**
- `status` (optional): Filter by status
- `limit` (default: 50): Max results

**Example:**
```bash
curl "http://localhost:8000/jobs?status=completed&limit=10"
```

### 6. Delete Job

**DELETE** `/job/{job_id}`

Deletes job and associated files.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/job/abc-123-def"
```

### 7. Cleanup Old Jobs

**POST** `/cleanup?older_than_hours={hours}&status={status}`

**Parameters:**
- `older_than_hours` (default: 24): Delete jobs older than this
- `status` (optional): Only delete jobs with this status

**Example:**
```bash
curl -X POST "http://localhost:8000/cleanup?older_than_hours=48&status=completed"
```

### 8. Health Check

**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "models": {
    "i2v_loaded": true,
    "t2v_loaded": true
  },
  "gpu_available": true,
  "gpu_name": "NVIDIA A100-PCIE-80GB",
  "queue_size": 2
}
```

## Usage Examples

### Python Client - Image-to-Video

```python
import requests
import time

# Submit I2V job
with open("image.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/generate",
        files={"image": f},
        data={
            "prompt": "A cat playing with a ball",
            "size": "1280*720",
            "frame_num": 81,
            "sampling_steps": 40,
        }
    )

job_id = response.json()["job_id"]
print(f"Job ID: {job_id}")

# Poll status
while True:
    status_response = requests.get(f"http://localhost:8000/status/{job_id}")
    status = status_response.json()["status"]
    print(f"Status: {status}")
    
    if status == "completed":
        # Download video
        video_response = requests.get(f"http://localhost:8000/download/{job_id}")
        with open("output.mp4", "wb") as f:
            f.write(video_response.content)
        print("Video downloaded!")
        break
    elif status == "failed":
        print("Generation failed!")
        break
    
    time.sleep(10)
```

### Python Client - Text-to-Video

```python
import requests
import time

# Submit T2V job
response = requests.post(
    "http://localhost:8000/generate-t2v",
    data={
        "prompt": "Two anthropomorphic cats in boxing gear fighting on a stage",
        "size": "1280*720",
        "frame_num": 81,
        "sampling_steps": 40,
    }
)

job_id = response.json()["job_id"]
print(f"Job ID: {job_id}")

# Poll status (same as I2V)
while True:
    status_response = requests.get(f"http://localhost:8000/status/{job_id}")
    status = status_response.json()["status"]
    print(f"Status: {status}")
    
    if status == "completed":
        video_response = requests.get(f"http://localhost:8000/download/{job_id}")
        with open("output_t2v.mp4", "wb") as f:
            f.write(video_response.content)
        print("Video downloaded!")
        break
    elif status == "failed":
        print("Generation failed!")
        break
    
    time.sleep(10)
```

### JavaScript/Node.js Client

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

async function generateVideo() {
    // Submit job
    const form = new FormData();
    form.append('image', fs.createReadStream('image.jpg'));
    form.append('prompt', 'A cat playing with a ball');
    form.append('size', '1280*720');
    
    const response = await axios.post('http://localhost:8000/generate', form, {
        headers: form.getHeaders()
    });
    
    const jobId = response.data.job_id;
    console.log(`Job ID: ${jobId}`);
    
    // Poll status
    while (true) {
        const statusResponse = await axios.get(`http://localhost:8000/status/${jobId}`);
        const status = statusResponse.data.status;
        console.log(`Status: ${status}`);
        
        if (status === 'completed') {
            // Download video
            const videoResponse = await axios.get(
                `http://localhost:8000/download/${jobId}`,
                { responseType: 'stream' }
            );
            videoResponse.data.pipe(fs.createWriteStream('output.mp4'));
            console.log('Video downloaded!');
            break;
        } else if (status === 'failed') {
            console.log('Generation failed!');
            break;
        }
        
        await new Promise(resolve => setTimeout(resolve, 10000));
    }
}

generateVideo();
```

## Performance

### Expected Generation Times (A100 80GB)

**Image-to-Video (I2V):**
- **720p (1280x720, 81 frames)**: ~3-4 minutes
- **480p (1024x576, 81 frames)**: ~2-3 minutes

**Text-to-Video (T2V):**
- **720p (1280x720, 81 frames)**: ~3-4 minutes
- **480p (1024x576, 81 frames)**: ~2-3 minutes

### Resource Usage

- **VRAM**: 70-75GB peak (per model)
- **RAM**: 30-40GB peak
- **Storage**: 
  - Model weights: ~200GB (100GB I2V + 100GB T2V)
  - Per video: ~50-100MB

## Tips

### Image-to-Video (I2V)
1. **For 480p videos**: Use `shift=3.0` for better quality
2. **Empty prompts**: The model can generate from image alone
3. **Negative prompts**: Use to exclude unwanted content

### Text-to-Video (T2V)
1. **Default shift**: T2V uses `shift=12.0` (different from I2V's 5.0)
2. **Default guide_scale**: T2V uses `3.0` (I2V uses 3.5)
3. **Detailed prompts**: More detailed prompts produce better results

### General
1. **Queue management**: Only one video generates at a time
2. **Cleanup**: Regularly clean up old jobs to save storage
3. **Model switching**: Both models stay loaded in memory for fast switching

## Troubleshooting

### Out of Memory
- Ensure you have 80GB VRAM
- Check no other processes are using GPU
- Restart the server to clear cache

### Slow Generation
- Check GPU utilization with `nvidia-smi`
- Reduce `sampling_steps` for faster (lower quality) results
- Use 480p instead of 720p

### Model Not Loading
- Verify model weights are downloaded (~100GB)
- Check `CKPT_DIR` path in server.py
- Ensure sufficient disk space

## Configuration

Edit `server.py` to customize:

```python
# Model configuration
I2V_CKPT_DIR = "./Wan2.2-I2V-A14B"  # I2V model weights path
T2V_CKPT_DIR = "./Wan2.2-T2V-A14B"  # T2V model weights path
OUTPUT_DIR = Path("./outputs")       # Generated videos
UPLOAD_DIR = Path("./uploads")       # Uploaded images

# Model loading options
convert_model_dtype=True  # Use bfloat16
t5_cpu=False             # Keep T5 on GPU
offload_model=True       # Offload between steps
```

## Model Comparison

| Feature | I2V (Image-to-Video) | T2V (Text-to-Video) |
|---------|---------------------|---------------------|
| Input | Image + Optional Prompt | Text Prompt Only |
| Default Shift | 5.0 (3.0 for 480p) | 12.0 |
| Default Guide Scale | 3.5 | 3.0 |
| Aspect Ratio | Follows input image | Fixed by size parameter |
| Use Case | Animate existing images | Generate from scratch |
