import cv2
from scenedetect import open_video, SceneManager
from scenedetect.detectors import ContentDetector

# Détecteur de visages léger intégré à OpenCV pour bonifier les "Moments privilégiés"
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

def score_segment(video_path: str, start_sec: float, duration_sec: float = 3.0) -> float:
    """Calcule un score de qualité technique et humain sur une séquence de 3 secondes."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    start_frame = int(start_sec * fps)
    end_frame = int((start_sec + duration_sec) * fps)
    
    sharpness_list = []
    exposure_list = []
    face_bonus = 1.0

    # Analyse 1 frame toutes les 10 frames pour la rapidité
    for f_idx in range(start_frame, end_frame, 10):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            break
            
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # 1. Netteté (Variance du Laplacien)
        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_list.append(min(sharpness, 1000.0)) # Plafonne pour éviter les biais
        
        # 2. Exposition (idéal entre 55 et 200)
        mean_lum = gray.mean()
        exp_score = 1.0 if 55 <= mean_lum <= 200 else 0.3
        exposure_list.append(exp_score)

        # 3. Bonus Visages (Moments d'entreprise / Équipe)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=5, minSize=(40, 40))
        if len(faces) > 0:
            face_bonus = 1.35

    cap.release()
    if not sharpness_list:
        return 0.0

    avg_sharpness = sum(sharpness_list) / len(sharpness_list)
    avg_exposure = sum(exposure_list) / len(exposure_list)
    
    return round(avg_sharpness * avg_exposure * face_bonus, 2)

def extract_best_segments_from_reel(reel: dict, clip_duration: float = 3.0, max_per_reel: int = 2) -> list[dict]:
    """Détecte les scènes d'un Reel et retourne les 2 meilleures séquences de 3 secondes."""
    video_path = reel["path"]
    try:
        video = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=27.0))
        scene_manager.detect_scenes(video)
        scene_list = scene_manager.get_scene_list()
    except Exception:
        scene_list = []

    candidates = []
    
    # Si PySceneDetect ne trouve pas de coupure franche, on découpe en tranches de 3s
    if not scene_list:
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_sec = (cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps)
        cap.release()
        
        curr = 0.5
        while curr + clip_duration <= total_sec:
            score = score_segment(video_path, curr, clip_duration)
            candidates.append({"start": curr, "duration": clip_duration, "score": score})
            curr += clip_duration
    else:
        for scene in scene_list:
            start_sec = scene[0].get_seconds()
            end_sec = scene[1].get_seconds()
            if end_sec - start_sec >= clip_duration:
                score = score_segment(video_path, start_sec, clip_duration)
                candidates.append({"start": start_sec, "duration": clip_duration, "score": score})

    # Trie par score décroissant et garde les `max_per_reel` meilleures séquences
    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[:max_per_reel]
    
    for b in best:
        b["video_path"] = video_path
        b["reel_id"] = reel["id"]
        b["timestamp"] = reel["timestamp"]
        
    return best