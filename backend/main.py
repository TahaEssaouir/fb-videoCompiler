import uuid
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from scraper import download_facebook_reels
from ai_filter import ContentFilter
from analyzer import extract_best_segments_from_reel
from renderer import build_final_anniversary_video

app = FastAPI(title="Facebook Reels Anniversary Maker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage de l'état des jobs en mémoire
JOBS = {}
content_filter = ContentFilter()

class JobRequest(BaseModel):
    page_url: str
    max_reels: int = 35
    target_duration: int = 150 # 150 sec (2min30)

def run_video_pipeline(job_id: str, page_url: str, max_reels: int, target_duration: int):
    base_dir = f"workspace/{job_id}"
    raw_dir = f"{base_dir}/raw"
    segments_dir = f"{base_dir}/segments"
    final_output = f"{base_dir}/anniversaire_1920x1080.mp4"

    try:
        # ÉTAPE A : Téléchargement
        JOBS[job_id]["status"] = "Téléchargement des Reels depuis la page Facebook..."
        JOBS[job_id]["progress"] = 15
        reels = download_facebook_reels(page_url, output_dir=raw_dir, max_reels=max_reels)
        if not reels:
            raise Exception("Aucun Reel récupéré. Vérifiez le lien ou activez cookiesfrombrowser.")

        # ÉTAPE B : Filtrage Visuel CLIP (Anti-IA / Voyages & Moments)
        JOBS[job_id]["status"] = f"Filtrage IA sur {len(reels)} Reels (Moments privilégiés & Voyages)..."
        JOBS[job_id]["progress"] = 40
        valid_reels = []
        for r in reels:
            is_valid, category, conf = content_filter.is_valid_reel(r["path"])
            if is_valid:
                r["category"] = category
                valid_reels.append(r)

        if not valid_reels:
            raise Exception("Tous les Reels ont été rejetés par le filtre anti-IA.")

        # ÉTAPE C : Découpage & Score Qualité OpenCV
        JOBS[job_id]["status"] = f"Extraction des meilleures séquences ({len(valid_reels)} Reels retenus)..."
        JOBS[job_id]["progress"] = 65
        all_best_segments = []
        for r in valid_reels:
            segs = extract_best_segments_from_reel(r, clip_duration=3.0, max_per_reel=3)
            all_best_segments.extend(segs)

        if not all_best_segments:
            raise Exception("Impossible d'extraire des séquences de qualité suffisante.")

        # ÉTAPE D : Montage 1920x1080 Muet
        JOBS[job_id]["status"] = "Montage de la vidéo finale 1920×1080 (muette)..."
        JOBS[job_id]["progress"] = 85
        build_final_anniversary_video(
            all_best_segments, 
            output_file=final_output, 
            work_dir=segments_dir,
            target_duration_sec=target_duration
        )

        JOBS[job_id]["status"] = "Terminé !"
        JOBS[job_id]["progress"] = 100
        JOBS[job_id]["completed"] = True
        JOBS[job_id]["output_file"] = final_output

    except Exception as e:
        JOBS[job_id]["status"] = f"Erreur : {str(e)}"
        JOBS[job_id]["error"] = True

@app.post("/api/start-job")
def start_job(req: JobRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "status": "Initialisation du pipeline...",
        "progress": 5,
        "completed": False,
        "error": False,
        "output_file": None
    }
    background_tasks.add_task(run_video_pipeline, job_id, req.page_url, req.max_reels, req.target_duration)
    return {"job_id": job_id}

@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job introuvable")
    return JOBS[job_id]

@app.get("/api/download/{job_id}")
def download_video(job_id: str):
    job = JOBS.get(job_id)
    if not job or not job.get("completed") or not os.path.exists(job["output_file"]):
        raise HTTPException(status_code=400, detail="Vidéo non disponible")
    return FileResponse(
        job["output_file"], 
        media_type="video/mp4", 
        filename="Video_Anniversaire_Entreprise_1080p.mp4"
    )