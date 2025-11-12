import os
import uuid
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict
from queue import Queue
from threading import Thread

import torch
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
import uvicorn

from wan import WanI2V
from wan.configs import WAN_CONFIGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Wan2.2 I2V API")

# Configuration
CKPT_DIR = "./Wan2.2-I2V-A14B"
OUTPUT_DIR = Path("./outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Job storage
jobs: Dict[str, dict] = {}
job_queue = Queue()

# Model instance (loaded once)
model = None


def load_model():
    """Load the Wan I2V model"""
    global model
    if model is None:
        logger.info("Loading Wan2.2 I2V model...")
        cfg = WAN_CONFIGS["i2v-A14B"]
        model = WanI2V(
            config=cfg,
            checkpoint_dir=CKPT_DIR,
            device_id=0,
            rank=0,
            t5_fsdp=False,
            dit_fsdp=False,
            use_sp=False,
            t5_cpu=False,
            init_on_cpu=True,
            convert_model_dtype=True,
        )
        logger.info("Model loaded successfully")
    return model


def process_job(job_id: str, image_path: str, prompt: str, config: dict):
    """Process a single video generation job"""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["started_at"] = datetime.now().isoformat()
        
        logger.info(f"Job {job_id}: Starting generation")
        logger.info(f"Job {job_id}: Config - size: {config.get('max_area')}, frames: {config.get('frame_num')}, "
                   f"steps: {config.get('sampling_steps')}, solver: {config.get('sample_solver')}")
        
        # Load image
        img = Image.open(image_path).convert("RGB")
        logger.info(f"Job {job_id}: Image loaded - size: {img.size}")
        
        # Load model
        wan_model = load_model()
        
        # Generate video
        logger.info(f"Job {job_id}: Starting video generation...")
        video = wan_model.generate(
            input_prompt=prompt if prompt else "",
            img=img,
            max_area=config.get("max_area", 720 * 1280),
            frame_num=config.get("frame_num", 81),
            shift=config.get("shift", 5.0),
            sample_solver=config.get("sample_solver", "unipc"),
            sampling_steps=config.get("sampling_steps", 40),
            guide_scale=config.get("guide_scale", 3.5),
            n_prompt=config.get("n_prompt", ""),
            seed=config.get("seed", -1),
            offload_model=True,
        )
        
        # Save video
        output_path = OUTPUT_DIR / f"{job_id}.mp4"
        logger.info(f"Job {job_id}: Saving video to {output_path}")
        
        from wan.utils.utils import save_video
        save_video(
            tensor=video[None],
            save_file=str(output_path),
            fps=16,
            nrow=1,
            normalize=True,
            value_range=(-1, 1),
        )
        
        # Get file size
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        jobs[job_id]["output_path"] = str(output_path)
        jobs[job_id]["file_size_mb"] = round(file_size_mb, 2)
        
        logger.info(f"Job {job_id}: Completed successfully (file size: {file_size_mb:.2f} MB)")
        
        # Clean up CUDA cache
        torch.cuda.empty_cache()
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Job {job_id}: Failed with error: {str(e)}")
        logger.error(f"Job {job_id}: Traceback:\n{error_trace}")
        
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        
        # Clean up CUDA cache on error
        torch.cuda.empty_cache()


def worker():
    """Background worker to process jobs from queue"""
    while True:
        job_data = job_queue.get()
        if job_data is None:
            break
        
        process_job(
            job_data["job_id"],
            job_data["image_path"],
            job_data["prompt"],
            job_data["config"],
        )
        job_queue.task_done()


# Start background worker
worker_thread = Thread(target=worker, daemon=True)
worker_thread.start()


@app.on_event("startup")
async def startup_event():
    """Preload model on startup"""
    logger.info("Starting up...")
    load_model()


@app.get("/")
async def root():
    return {
        "message": "Wan2.2 I2V API",
        "version": "1.0.0",
        "model": "Wan2.2-I2V-A14B",
        "endpoints": {
            "health": "/health",
            "generate": "/generate (POST)",
            "status": "/status/{job_id} (GET)",
            "download": "/download/{job_id} (GET)",
            "delete": "/job/{job_id} (DELETE)",
        },
        "supported_features": {
            "resolutions": ["1280*720 (720p)", "1024*576 (480p)", "custom"],
            "frame_counts": "4n+1 (e.g., 81, 85, 89)",
            "solvers": ["unipc", "dpm++"],
            "image_only_generation": True,
            "negative_prompts": True,
        }
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "gpu_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "queue_size": job_queue.qsize(),
    }


@app.post("/generate")
async def generate_video(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    negative_prompt: Optional[str] = Form(""),
    size: Optional[str] = Form("1280*720"),
    frame_num: Optional[int] = Form(81),
    shift: Optional[float] = Form(5.0),
    sampling_steps: Optional[int] = Form(40),
    guide_scale: Optional[float] = Form(3.5),
    sample_solver: Optional[str] = Form("unipc"),
    seed: Optional[int] = Form(-1),
):
    """
    Generate video from image and prompt
    
    Parameters:
    - image: Input image file (required)
    - prompt: Text prompt (optional, can be empty for image-only generation)
    - negative_prompt: Negative prompt for content exclusion (optional)
    - size: Video resolution area as "width*height" (e.g., "1280*720" or "1024*576")
    - frame_num: Number of frames (must be 4n+1, default: 81)
    - shift: Noise schedule shift (default: 5.0, use 3.0 for 480p)
    - sampling_steps: Number of diffusion steps (default: 40)
    - guide_scale: Guidance scale (default: 3.5)
    - sample_solver: Solver type - "unipc" or "dpm++" (default: "unipc")
    - seed: Random seed, -1 for random (default: -1)
    """
    
    # Validate image
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Validate parameters
    if frame_num % 4 != 1:
        raise HTTPException(status_code=400, detail="frame_num must be 4n+1 (e.g., 81, 85, 89)")
    
    if sample_solver not in ["unipc", "dpm++"]:
        raise HTTPException(status_code=400, detail="sample_solver must be 'unipc' or 'dpm++'")
    
    # Parse size
    try:
        width, height = map(int, size.split("*"))
        max_area = width * height
    except:
        raise HTTPException(status_code=400, detail="size must be in format 'width*height' (e.g., '1280*720')")
    
    # Create job ID
    job_id = str(uuid.uuid4())
    
    # Save uploaded image
    image_path = UPLOAD_DIR / f"{job_id}.jpg"
    with open(image_path, "wb") as f:
        content = await image.read()
        f.write(content)
    
    # Create job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "prompt": prompt,
        "size": size,
        "created_at": datetime.now().isoformat(),
        "image_path": str(image_path),
    }
    
    # Queue job
    config = {
        "max_area": max_area,
        "frame_num": frame_num,
        "shift": shift,
        "sampling_steps": sampling_steps,
        "guide_scale": guide_scale,
        "seed": seed,
        "n_prompt": negative_prompt,
        "sample_solver": sample_solver,
    }
    
    job_queue.put({
        "job_id": job_id,
        "image_path": str(image_path),
        "prompt": prompt,
        "config": config,
    })
    
    logger.info(f"Job {job_id} queued (size: {size}, solver: {sample_solver}). Queue size: {job_queue.qsize()}")
    
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued successfully",
        "config": {
            "size": size,
            "frame_num": frame_num,
            "sampling_steps": sampling_steps,
            "sample_solver": sample_solver,
        }
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Get job status"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    response = {
        "job_id": job_id,
        "status": job["status"],
        "prompt": job.get("prompt", ""),
        "size": job.get("size", ""),
        "created_at": job["created_at"],
        "queue_position": None,
    }
    
    # Calculate queue position if queued
    if job["status"] == "queued":
        queue_list = list(job_queue.queue)
        for i, queued_job in enumerate(queue_list):
            if queued_job["job_id"] == job_id:
                response["queue_position"] = i + 1
                break
    
    if "started_at" in job:
        response["started_at"] = job["started_at"]
    
    if "completed_at" in job:
        response["completed_at"] = job["completed_at"]
        
        # Calculate processing time
        if "started_at" in job:
            from datetime import datetime
            started = datetime.fromisoformat(job["started_at"])
            completed = datetime.fromisoformat(job["completed_at"])
            response["processing_time_seconds"] = (completed - started).total_seconds()
    
    if job["status"] == "completed":
        response["download_url"] = f"/download/{job_id}"
    
    if job["status"] == "failed":
        response["error"] = job.get("error", "Unknown error")
    
    return response


@app.get("/jobs")
async def list_jobs(status: Optional[str] = None, limit: int = 50):
    """
    List all jobs with optional status filter
    
    Parameters:
    - status: Filter by status (queued, processing, completed, failed)
    - limit: Maximum number of jobs to return (default: 50)
    """
    filtered_jobs = []
    
    for job_id, job in jobs.items():
        if status is None or job["status"] == status:
            filtered_jobs.append({
                "job_id": job_id,
                "status": job["status"],
                "prompt": job.get("prompt", "")[:50] + "..." if len(job.get("prompt", "")) > 50 else job.get("prompt", ""),
                "created_at": job["created_at"],
            })
    
    # Sort by created_at descending
    filtered_jobs.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {
        "total": len(filtered_jobs),
        "jobs": filtered_jobs[:limit],
        "queue_size": job_queue.qsize(),
    }


@app.get("/download/{job_id}")
async def download_video(job_id: str):
    """Download generated video"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail=f"Job status is {job['status']}, not completed")
    
    output_path = job.get("output_path")
    if not output_path or not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"{job_id}.mp4",
    )


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete job and associated files"""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    # Cannot delete processing jobs
    if job["status"] == "processing":
        raise HTTPException(status_code=400, detail="Cannot delete job that is currently processing")
    
    # Delete files
    deleted_files = []
    if "image_path" in job and os.path.exists(job["image_path"]):
        os.remove(job["image_path"])
        deleted_files.append("input_image")
    
    if "output_path" in job and os.path.exists(job["output_path"]):
        os.remove(job["output_path"])
        deleted_files.append("output_video")
    
    # Remove from jobs
    del jobs[job_id]
    
    return {
        "message": "Job deleted successfully",
        "deleted_files": deleted_files,
    }


@app.post("/cleanup")
async def cleanup_old_jobs(older_than_hours: int = 24, status: Optional[str] = None):
    """
    Clean up old jobs and their files
    
    Parameters:
    - older_than_hours: Delete jobs older than this many hours (default: 24)
    - status: Only delete jobs with this status (optional)
    """
    from datetime import datetime, timedelta
    
    cutoff_time = datetime.now() - timedelta(hours=older_than_hours)
    deleted_count = 0
    
    jobs_to_delete = []
    for job_id, job in jobs.items():
        if job["status"] == "processing":
            continue
            
        created_at = datetime.fromisoformat(job["created_at"])
        if created_at < cutoff_time:
            if status is None or job["status"] == status:
                jobs_to_delete.append(job_id)
    
    for job_id in jobs_to_delete:
        try:
            await delete_job(job_id)
            deleted_count += 1
        except:
            pass
    
    return {
        "message": f"Cleaned up {deleted_count} old jobs",
        "deleted_count": deleted_count,
    }


@app.get("/test-ui")
async def test_ui():
    """Simple HTML test interface"""
    from fastapi.responses import HTMLResponse
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Wan2.2 I2V Test Interface</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, select, textarea { width: 100%; padding: 8px; box-sizing: border-box; }
            button { background: #007bff; color: white; padding: 10px 20px; border: none; cursor: pointer; }
            button:hover { background: #0056b3; }
            .result { margin-top: 20px; padding: 15px; background: #f0f0f0; border-radius: 5px; }
        </style>
    </head>
    <body>
        <h1>Wan2.2 Image-to-Video Generator</h1>
        <form id="uploadForm" enctype="multipart/form-data">
            <div class="form-group">
                <label>Image:</label>
                <input type="file" name="image" accept="image/*" required>
            </div>
            <div class="form-group">
                <label>Prompt (optional):</label>
                <textarea name="prompt" rows="3" placeholder="Describe the motion you want..."></textarea>
            </div>
            <div class="form-group">
                <label>Resolution:</label>
                <select name="size">
                    <option value="1280*720">720p (1280x720)</option>
                    <option value="1024*576">480p (1024x576)</option>
                </select>
            </div>
            <div class="form-group">
                <label>Frames:</label>
                <input type="number" name="frame_num" value="81" step="4">
            </div>
            <div class="form-group">
                <label>Sampling Steps:</label>
                <input type="number" name="sampling_steps" value="40" min="10" max="100">
            </div>
            <button type="submit">Generate Video</button>
        </form>
        <div id="result" class="result" style="display:none;"></div>
        
        <script>
            document.getElementById('uploadForm').onsubmit = async (e) => {
                e.preventDefault();
                const formData = new FormData(e.target);
                const resultDiv = document.getElementById('result');
                resultDiv.style.display = 'block';
                resultDiv.innerHTML = 'Submitting job...';
                
                try {
                    const response = await fetch('/generate', {
                        method: 'POST',
                        body: formData
                    });
                    const data = await response.json();
                    
                    if (response.ok) {
                        resultDiv.innerHTML = `
                            <h3>Job Submitted!</h3>
                            <p>Job ID: ${data.job_id}</p>
                            <p>Status: ${data.status}</p>
                            <p>Check status at: <a href="/status/${data.job_id}" target="_blank">/status/${data.job_id}</a></p>
                        `;
                    } else {
                        resultDiv.innerHTML = `<p style="color:red;">Error: ${data.detail}</p>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<p style="color:red;">Error: ${error.message}</p>`;
                }
            };
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
