import os
import subprocess
from pathlib import Path

def render_single_segment_1080p(segment: dict, index: int, temp_dir: str) -> str:
    """Convertit une séquence verticale en 1920x1080 (fond flouté, 30fps, muet)."""
    output_seg = os.path.join(temp_dir, f"seg_{index:03d}.mp4")
    
    vf_filter = (
        "split[original][copy];"
        "[copy]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,boxblur=25:5[blurred];"
        "[original]scale=-1:1080[scaled];"
        "[blurred][scaled]overlay=(W-w)/2:(H-h)/2,fps=30,format=yuv420p"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(segment["start"]),
        "-i", segment["video_path"],
        "-t", str(segment["duration"]),
        "-vf", vf_filter,
        "-an",  # Vidéo strictement muette
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        output_seg
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_seg

def build_final_anniversary_video(
    all_segments: list[dict], 
    output_file: str, 
    work_dir: str,
    target_duration_sec: int = 150 # 150s = 2 minutes 30 secondes
) -> str:
    Path(work_dir).mkdir(parents=True, exist_ok=True)
    clip_duration = 3.0
    max_clips = int(target_duration_sec // clip_duration) # 50 séquences de 3s

    # 1. Garde les 50 meilleures séquences par score qualité
    all_segments.sort(key=lambda x: x["score"], reverse=True)
    selected_segments = all_segments[:max_clips]

    # 2. Trie les séquences retenues par ordre chronologique pour raconter l'histoire de l'entreprise
    selected_segments.sort(key=lambda x: (x["timestamp"], x["start"]))

    rendered_files = []
    for idx, seg in enumerate(selected_segments):
        try:
            out_seg = render_single_segment_1080p(seg, idx, work_dir)
            rendered_files.append(out_seg)
        except Exception as e:
            print(f"Erreur rendu segment {idx}: {e}")

    # 3. Création du fichier de concaténation FFmpeg
    concat_list_path = os.path.join(work_dir, "concat_list.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for file_path in rendered_files:
            abs_path = os.path.abspath(file_path).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")

    # 4. Assemblage final sans ré-encodage (ultra-rapide)
    Path(os.path.dirname(output_file)).mkdir(parents=True, exist_ok=True)
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        "-an",
        output_file
    ]
    subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return output_file