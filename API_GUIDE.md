# Wan2.2 I2V FastAPI Server Guide

## Quick Start

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

### 1. Generate Video

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

### 2. Check Job Status

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

### 3. Download Video

**GET** `/download/{job_id}`

**Example:**
```bash
curl "http://localhost:8000/download/abc-123-def" -o video.mp4
```

### 4. List Jobs

**GET** `/jobs?status={status}&limit={limit}`

**Parameters:**
- `status` (optional): Filter by status
- `limit` (default: 50): Max results

**Example:**
```bash
curl "http://localhost:8000/jobs?status=completed&limit=10"
```

### 5. Delete Job

**DELETE** `/job/{job_id}`

Deletes job and associated files.

**Example:**
```bash
curl -X DELETE "http://localhost:8000/job/abc-123-def"
```

### 6. Cleanup Old Jobs

**POST** `/cleanup?older_than_hours={hours}&status={status}`

**Parameters:**
- `older_than_hours` (default: 24): Delete jobs older than this
- `status` (optional): Only delete jobs with this status

**Example:**
```bash
curl -X POST "http://localhost:8000/cleanup?older_than_hours=48&status=completed"
```

### 7. Health Check

**GET** `/health`

**Response:**
```json
{
  "status": "healthy",
  "model_loaded": true,
  "gpu_available": true,
  "gpu_name": "NVIDIA A100-PCIE-80GB",
  "queue_size": 2
}
```

## Usage Examples

### Python Client

```python
import requests
import time

# Submit job
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

- **720p (1280x720, 81 frames)**: ~3-4 minutes
- **480p (1024x576, 81 frames)**: ~2-3 minutes

### Resource Usage

- **VRAM**: 70-75GB peak
- **RAM**: 30-40GB peak
- **Storage**: ~50-100MB per video

## Tips

1. **For 480p videos**: Use `shift=3.0` for better quality
2. **Empty prompts**: The model can generate from image alone
3. **Negative prompts**: Use to exclude unwanted content
4. **Queue management**: Only one video generates at a time
5. **Cleanup**: Regularly clean up old jobs to save storage

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
CKPT_DIR = "./Wan2.2-I2V-A14B"  # Model weights path
OUTPUT_DIR = Path("./outputs")   # Generated videos
UPLOAD_DIR = Path("./uploads")   # Uploaded images

# Model loading options
convert_model_dtype=True  # Use bfloat16
t5_cpu=False             # Keep T5 on GPU
offload_model=True       # Offload between steps
```
