# RTX 5060 (Blackwell SM 12.0) Optimized Training Script
# Uses FP16/BF16 pipelines for maximum tensor core saturation.

$env:CUDA_VISIBLE_DEVICES="0"

Write-Host "Initializing Aerial Training Pipeline..." -ForegroundColor Green
Write-Host "Forcing AMP (Automatic Mixed Precision) on Blackwell Architecture" -ForegroundColor Cyan

yolo task=detect mode=train model=yolo11l.pt data=custom_liveries.yaml epochs=100 imgsz=640 batch=16 device=0 workers=8 amp=True half=True
