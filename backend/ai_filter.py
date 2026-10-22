import cv2
import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel

class ContentFilter:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(self.device)
        self.processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        
        # Catégories cibles (0, 1) vs Catégories à rejeter (2, 3)
        self.labels = [
            "real people smiling, corporate event, team building, privileged moment", # Index 0 (Positif)
            "travel video, real landscape, vacation trip, outdoor exploration",       # Index 1 (Positif)
            "AI generated art, 3D animation, synthetic digital render, CGI",          # Index 2 (Négatif IA)
            "static text poster, graphic design template, marketing flyer"            # Index 3 (Négatif Flyer)
        ]

    def extract_sample_frames(self, video_path: str) -> list[Image.Image]:
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames < 10:
            cap.release()
            return []

        # Prend 3 frames : à 20%, 50% et 80% de la vidéo
        indices = [int(total_frames * 0.2), int(total_frames * 0.5), int(total_frames * 0.8)]
        frames = []
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(Image.fromarray(rgb))
        cap.release()
        return frames

    def is_valid_reel(self, video_path: str) -> tuple[bool, str, float]:
        """Retourne (Est_Valide, Catégorie_Dominante, Score_Confiance)"""
        frames = self.extract_sample_frames(video_path)
        if not frames:
            return False, "unreadable", 0.0

        inputs = self.processor(
            text=self.labels, images=frames, return_tensors="pt", padding=True
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = outputs.logits_per_image.softmax(dim=1).mean(dim=0)

        prob_moment = probs[0].item()
        prob_travel = probs[1].item()
        prob_ai = probs[2].item()
        prob_flyer = probs[3].item()

        positive_score = prob_moment + prob_travel
        negative_score = prob_ai + prob_flyer

        # Si la probabilité IA/Flyer dépasse 45%, on rejette la vidéo
        if negative_score > 0.45 or positive_score < 0.50:
            return False, "AI_or_Flyer", negative_score

        category = "Moment Privilégié" if prob_moment >= prob_travel else "Voyage"
        return True, category, positive_score