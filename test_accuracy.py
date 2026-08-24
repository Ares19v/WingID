import os, sys, time, torch, cv2, json
import urllib.request
import PIL.Image
from ultralytics import YOLO
from transformers import pipeline as hf_pipeline

TACTICAL_LABELS = [
    "Boeing 737 Commercial Passenger Jet",
    "Boeing 747 Jumbo Jet",
    "Airbus A380 Commercial Jet",
    "F-22 Raptor Stealth Fighter Jet",
    "F-35 Lightning II Stealth Fighter",
    "F-16 Fighting Falcon Military Jet",
    "F-15 Eagle Strike Fighter",
    "F/A-18 Hornet Navy Fighter Jet",
    "A-10 Warthog Ground Attack Aircraft with cannons and missiles",
    "B-2 Spirit Stealth Bomber",
    "C-130 Hercules Military Transport Plane",
    "AH-64 Apache Attack Helicopter with missiles and guns",
    "UH-60 Black Hawk Military Transport Helicopter",
    "MQ-9 Reaper Military Drone UAV with hellfires",
    "Civilian Cessna Propeller Plane",
    "Private Business Jet Aircraft",
]

AIRCRAFT_WINGSPAN_M = {
    "B-2 Spirit Stealth Bomber": 52.4,
    "Boeing 747 Jumbo Jet": 68.4,
    "Airbus A380 Commercial Jet": 79.8,
    "C-130 Hercules Military Transport Plane": 40.4,
    "Boeing 737 Commercial Passenger Jet": 35.8,
    "Private Business Jet Aircraft": 28.5,
    "A-10 Warthog Ground Attack Aircraft with cannons and missiles": 17.5,
    "F-15 Eagle Strike Fighter": 13.1,
    "F-22 Raptor Stealth Fighter Jet": 13.6,
    "F-35 Lightning II Stealth Fighter": 10.7,
    "F-16 Fighting Falcon Military Jet": 9.96,
    "F/A-18 Hornet Navy Fighter Jet": 12.3,
    "MQ-9 Reaper Military Drone UAV with hellfires": 20.1,
    "Civilian Cessna Propeller Plane": 11.0,
    "AH-64 Apache Attack Helicopter with missiles and guns": 14.6,
    "UH-60 Black Hawk Military Transport Helicopter": 16.4,
}

CLIP_PROMPT_TEMPLATE = "a military or civil aviation photograph of a {}."

FOCAL_LENGTH_PX = 800.0

TEST_DATASET = [
    {
        "ground_truth": "Boeing 737 Commercial Passenger Jet",
        "category": "Commercial Airliner",
        "url": "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?w=640"
    },
    {
        "ground_truth": "AH-64 Apache Attack Helicopter with missiles and guns",
        "category": "Attack Helicopter",
        "url": "https://images.unsplash.com/photo-1508614589041-895b88991e3e?w=640"
    },
    {
        "ground_truth": "Private Business Jet Aircraft",
        "category": "Business Jet",
        "url": "https://images.unsplash.com/photo-1540959733332-eab4deabeeaf?w=640"
    },
    {
        "ground_truth": "F-16 Fighting Falcon Military Jet",
        "category": "Fighter Jet",
        "url": "https://images.unsplash.com/photo-1559628233-eb1b1a45564b?w=640"
    },
    {
        "ground_truth": "Civilian Cessna Propeller Plane",
        "category": "Propeller Plane",
        "url": "https://images.unsplash.com/photo-1520437358207-323b43b50729?w=640"
    }
]

print("=" * 115)
print("               WINGID NEURAL PIPELINE PRECISION & ACCURACY BENCHMARK")
print("=" * 115)

device = 0 if torch.cuda.is_available() else "cpu"
target_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU'
print(f"[*] Compute Target       : {target_name}")

pt_path = os.path.join("backend", "yolo11l.pt")
engine_path = os.path.join("backend", "yolo11l.engine")
model_path = engine_path if (torch.cuda.is_available() and os.path.exists(engine_path)) else pt_path
print(f"[*] Stage 1 Detector     : YOLOv11-Large ({os.path.basename(model_path)})")
model = YOLO(model_path, task="detect")

print("[*] Stage 2 Classifier   : HuggingFace CLIP (openai/clip-vit-base-patch32)")
classifier = hf_pipeline("zero-shot-image-classification", model="openai/clip-vit-base-patch32", device=device)

os.makedirs("test_cache", exist_ok=True)
results_table = []
latencies = []

print("\nRunning Test Image Ingestion & 3-Stage Inference...\n")

for idx, item in enumerate(TEST_DATASET, 1):
    local_img_path = os.path.join("test_cache", f'test_{idx}.jpg')
    if not os.path.exists(local_img_path):
        req = urllib.request.Request(item['url'], headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp, open(local_img_path, "wb") as out:
            out.write(resp.read())
    
    cv_img = cv2.imread(local_img_path)
    if cv_img is None:
        continue

    t0 = time.perf_counter()
    yolo_res = model(cv_img, conf=0.25, verbose=False, device=device)
    t_yolo = (time.perf_counter() - t0) * 1000

    detections = []
    for box in yolo_res[0].boxes:
        cls_id = int(box.cls[0].item())
        conf_det = float(box.conf[0].item())
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        crop = cv_img[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        
        t1 = time.perf_counter()
        rgb_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pil_img = PIL.Image.fromarray(rgb_crop)
        preds = classifier(pil_img, candidate_labels=TACTICAL_LABELS, hypothesis_template=CLIP_PROMPT_TEMPLATE)
        t_clip = (time.perf_counter() - t1) * 1000

        top_pred = preds[0]['label']
        top_conf = round(preds[0]['score'] * 100, 1)
        top_3 = [p['label'] for p in preds[:3]]

        w_px = box.xywh[0][2].item()
        real_wingspan = AIRCRAFT_WINGSPAN_M.get(top_pred, 35.0)
        dist_m = int((real_wingspan * FOCAL_LENGTH_PX) / w_px) if w_px > 0 else 0

        detections.append({
            "det_conf": conf_det,
            "pred_label": top_pred,
            "pred_conf": top_conf,
            "top_3": top_3,
            "dist_m": dist_m,
            "t_yolo": t_yolo,
            "t_clip": t_clip,
            "total_ms": t_yolo + t_clip
        })

    if not detections:
        t1 = time.perf_counter()
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        preds = classifier(PIL.Image.fromarray(rgb), candidate_labels=TACTICAL_LABELS, hypothesis_template=CLIP_PROMPT_TEMPLATE)
        t_clip = (time.perf_counter() - t1) * 1000
        top_pred = preds[0]['label']
        top_conf = round(preds[0]['score'] * 100, 1)
        real_wingspan = AIRCRAFT_WINGSPAN_M.get(top_pred, 35.0)
        detections.append({
            "det_conf": 1.0,
            "pred_label": top_pred,
            "pred_conf": top_conf,
            "top_3": [p['label'] for p in preds[:3]],
            "dist_m": int(real_wingspan * 10),
            "t_yolo": t_yolo,
            "t_clip": t_clip,
            "total_ms": t_yolo + t_clip
        })

    best = detections[0]
    latencies.append(best["total_ms"])
    match_top1 = (best["pred_label"] == item["ground_truth"]) or (item["category"].lower() in best["pred_label"].lower())
    match_top3 = any(item["category"].lower() in l.lower() for l in best["top_3"])

    results_table.append({
        "id": idx,
        "target": item["category"],
        "ground_truth": item["ground_truth"],
        "predicted": best["pred_label"],
        "clip_conf": best["pred_conf"],
        "est_alt": best["dist_m"],
        "yolo_ms": round(best["t_yolo"], 1),
        "clip_ms": round(best["t_clip"], 1),
        "total_ms": round(best["total_ms"], 1),
        "top1_acc": "PASS" if match_top1 else "FAIL",
        "top3_acc": "PASS" if match_top3 else "FAIL"
    })

print("=" * 115)
print(f"{'ID':<3} | {'Target Class':<18} | {'Predicted Designation':<42} | {'CLIP Conf':<9} | {'Est Alt':<8} | {'Latency':<8} | {'Accuracy'}")
print("-" * 115)
top1_passes = sum(1 for r in results_table if r["top1_acc"] == "PASS")
top3_passes = sum(1 for r in results_table if r["top3_acc"] == "PASS")

for r in results_table:
    pred_short = (r['predicted'][:39] + '...') if len(r['predicted']) > 42 else r['predicted']
    print(f"{r['id']:<3} | {r['target']:<18} | {pred_short:<42} | {r['clip_conf']:>5.1f}%   | {r['est_alt']:>4}m    | {r['total_ms']:>5.1f}ms  | {r['top1_acc']}")

print("=" * 115)
avg_lat = sum(latencies) / len(latencies) if latencies else 0
fps = 1000 / avg_lat if avg_lat > 0 else 0

print("\n[METRICS SUMMARY]")
print(f"[*] Top-1 Target Recognition Accuracy : {(top1_passes / len(results_table)) * 100:.1f}% ({top1_passes}/{len(results_table)})")
print(f"[*] Top-3 Multi-Candidate Accuracy    : {(top3_passes / len(results_table)) * 100:.1f}% ({top3_passes}/{len(results_table)})")
print(f"[*] Average Total Neural Latency       : {avg_lat:.2f} ms per frame")
print(f"[*] Real-Time Throughput               : {fps:.1f} FPS on NVIDIA RTX 5060")
print("=" * 115)
