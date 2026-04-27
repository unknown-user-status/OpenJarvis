@echo off
setlocal enabledelayedexpansion
title OpenJarvis - OpenVINO NPU Setup

echo.
echo ============================================================
echo  OpenJarvis - Intel NPU / OpenVINO Vision Setup
echo ============================================================
echo.
echo  This script installs OpenVINO GenAI and downloads a small
echo  vision model that runs on your Intel AI Boost NPU.
echo.
echo  Your hardware: Intel Core Ultra (Meteor Lake)
echo  NPU: Intel AI Boost (~11 TOPS)
echo.
echo  Models available (choose one):
echo  [1] SmolVLM-256M  ~500 MB   Fastest, minimal quality (best for NPU)
echo  [2] SmolVLM-500M  ~900 MB   Good balance speed/quality
echo  [3] Qwen2-VL-2B   ~2 GB     Best quality small model
echo.
set /p choice="Enter choice [1]: "
if "%choice%"=="" set choice=1

if "%choice%"=="1" (
    set HF_MODEL=HuggingFaceTB/SmolVLM-256M-Instruct
    set MODEL_DIR=SmolVLM-256M
)
if "%choice%"=="2" (
    set HF_MODEL=HuggingFaceTB/SmolVLM-500M-Instruct
    set MODEL_DIR=SmolVLM-500M
)
if "%choice%"=="3" (
    set HF_MODEL=Qwen/Qwen2-VL-2B-Instruct
    set MODEL_DIR=Qwen2-VL-2B
)

if "%HF_MODEL%"=="" (
    echo Invalid choice. Defaulting to SmolVLM-256M.
    set HF_MODEL=HuggingFaceTB/SmolVLM-256M-Instruct
    set MODEL_DIR=SmolVLM-256M
)

echo.
echo  [1/3] Installing Python packages...
echo        (openvino-genai, optimum[openvino], Pillow, huggingface_hub)
echo.
uv pip install openvino-genai "optimum[openvino]" Pillow huggingface_hub

if %errorlevel% neq 0 (
    echo.
    echo  [!] Package install failed. Trying with pip...
    pip install openvino-genai "optimum[openvino]" Pillow huggingface_hub
)

echo.
echo  [2/3] Checking NPU availability...
python -c "import openvino as ov; core=ov.Core(); devs=core.available_devices; print('  Devices found:', devs); print('  NPU available:', 'NPU' in devs)"

echo.
echo  [3/3] Downloading and converting model: %HF_MODEL%
echo        Output: ov_models\%MODEL_DIR%\
echo        Quantization: int4 (smallest, best for NPU)
echo        This may take 5-15 minutes and ~2-4 GB disk/download space.
echo.

if not exist "ov_models" mkdir ov_models
if not exist "ov_models\%MODEL_DIR%" mkdir "ov_models\%MODEL_DIR%"

optimum-cli export openvino ^
    --model %HF_MODEL% ^
    --task image-text-to-text ^
    --weight-format int4 ^
    --trust-remote-code ^
    "ov_models\%MODEL_DIR%"

if %errorlevel% neq 0 (
    echo.
    echo  [!] optimum-cli failed. Trying Python export...
    python -c "from optimum.intel import OVModelForVisualCausalLM; m=OVModelForVisualCausalLM.from_pretrained('%HF_MODEL%', export=True, load_in_4bit=True, trust_remote_code=True); m.save_pretrained('ov_models/%MODEL_DIR%')"
)

echo.
echo  ============================================================
echo   Setup complete!
echo  ============================================================
echo.
echo   Model stored in: ov_models\%MODEL_DIR%\
echo.
echo   OpenJarvis will now automatically:
echo    1. Detect your Intel NPU
echo    2. Load %MODEL_DIR% on the NPU
echo    3. Use it for Camera Vision (faster than CPU/Ollama)
echo    4. Fall back to Ollama (CPU) if NPU is unavailable
echo.
echo   Restart the OpenJarvis server to activate NPU inference.
echo.
pause
