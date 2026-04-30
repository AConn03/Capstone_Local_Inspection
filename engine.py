import cv2
import numpy as np
import json
import time
from PIL import Image

class RustInferenceEngine:
    def __init__(self, settings_path="settings.json"):
        print("[DEBUG] Engine Init: Starting heavy library imports...")
        start_time = time.time()
        
        import os
        import torch
        from transformers import AutoModelForImageClassification, ViTImageProcessor
        print(f"[DEBUG] Engine Init: Imported Torch/Transformers in {time.time() - start_time:.2f} seconds.")

        with open(settings_path, 'r') as f:
            self.cfg = json.load(f)
        
        # --- EXPLICIT GPU CHECK ---
        wants_gpu = self.cfg.get("USE_GPU", True)
        if wants_gpu and torch.cuda.is_available():
            self.device = torch.device("cuda")
            print(f"[DEBUG] Engine Init: GPU supported and enabled! Using {torch.cuda.get_device_name(0)}")
        else:
            self.device = torch.device("cpu")
            if wants_gpu:
                print("[WARNING] Engine Init: GPU requested, but CUDA is not available. Falling back to CPU.")
            else:
                print("[DEBUG] Engine Init: GPU disabled in settings. Using CPU.")
        
        # --- CRASH PROTECTION ---
        model_path = os.path.join(self.cfg.get('MODELS_DIR', './models'), self.cfg.get('MODEL_VERSION', ''))
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model directory missing! Expected to find model at: {os.path.abspath(model_path)}")
            
        try:
            load_start = time.time()
            self.processor = ViTImageProcessor.from_pretrained(model_path)
            self.model = AutoModelForImageClassification.from_pretrained(model_path).to(self.device)
            self.model.eval()
            self.labels = self.model.config.id2label
            print(f"[DEBUG] Engine Init: Model loaded into VRAM/RAM in {time.time() - load_start:.2f} seconds.")
        except Exception as e:
            raise RuntimeError(f"Failed to load the model correctly. Error: {str(e)}")

    def refresh_settings(self):
        with open("settings.json", 'r') as f:
            self.cfg = json.load(f)

    def prepare_image(self, img):
        mode = self.cfg.get("RESIZE_MODE", "Stretch (Current)")
        target_size = (224, 224) 
        
        if mode == "Stretch (Current)":
            return cv2.resize(img, target_size)
        elif mode == "Pad to Fit":
            h, w = img.shape[:2]
            ratio = min(target_size[0]/h, target_size[1]/w)
            new_size = (int(w*ratio), int(h*ratio))
            resized = cv2.resize(img, new_size)
            pad_img = np.zeros((target_size[1], target_size[0], 3), dtype=np.uint8)
            pad_img[:new_size[1], :new_size[0]] = resized
            return pad_img
        return cv2.resize(img, target_size)

    def analyze_frame(self, frame):
        import torch # Needed here since we moved the global import
        
        self.refresh_settings()
        h, w, _ = frame.shape
        grid_size = self.cfg["GRID_SIZE"]
        gh, gw = h // grid_size, w // grid_size
        
        results = []
        for i in range(grid_size):
            for j in range(grid_size):
                left, top = j * gw, i * gh
                crop = frame[top:top+gh, left:left+gw]
                
                prep_crop = self.prepare_image(crop)
                pil_img = Image.fromarray(cv2.cvtColor(prep_crop, cv2.COLOR_BGR2RGB))
                inputs = self.processor(images=pil_img, return_tensors="pt").to(self.device)
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    probs = torch.sigmoid(outputs.logits).squeeze().cpu().numpy()
                
                detections = []
                for idx, prob in enumerate(probs):
                    label = self.labels[idx].lower()
                    thresh = self.cfg['MIN_RUST_CONFIDENCE'] if 'rust' in label else self.cfg['MIN_CRACK_CONFIDENCE']
                    if prob > (thresh / 100.0): 
                        detections.append({"label": label, "score": float(prob)})
                
                results.append({"box": (left, top, left+gw, top+gh), "detections": detections})
        return results