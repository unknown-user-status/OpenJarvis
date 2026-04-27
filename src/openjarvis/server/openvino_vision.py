"""OpenVINO NPU vision inference helper for OpenJarvis.

Provides image+text inference using Intel AI Boost NPU (or CPU fallback) via
openvino-genai VLMPipeline. Runs alongside Ollama — whichever backend is
available is used, with NPU preferred for speed.

Supported VLMs (officially validated by OpenVINO GenAI):
    - HuggingFaceTB/SmolVLM-256M-Instruct   (~500 MB, fastest on NPU)
    - HuggingFaceTB/SmolVLM-500M-Instruct   (~900 MB, good balance)
    - Qwen/Qwen2-VL-2B-Instruct             (~2 GB, best quality)
    - microsoft/Phi-3.5-vision-instruct      (~4 GB, high quality)
    - openbmb/MiniCPM-V-2_6                  (~2.4 GB)

Setup (run once):
    pip install openvino-genai optimum[openvino] huggingface_hub
    python -c "from src.openjarvis.server.openvino_vision import download_model; download_model()"

Or use the provided setup_openvino_npu.bat script.
"""

from __future__ import annotations

import base64
import io
import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("openjarvis.openvino_vision")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Where to store converted OpenVINO models (relative to this file's parent)
_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "ov_models"

# Model preference order (smallest/fastest first for NPU)
# These are the HuggingFace model IDs — they will be exported to OpenVINO IR
# format on first use.
MODEL_PREFERENCE = [
    ("Qwen/Qwen2-VL-2B-Instruct",           "Qwen2-VL-2B"),
    ("HuggingFaceTB/SmolVLM-500M-Instruct", "SmolVLM-500M"),
    ("HuggingFaceTB/SmolVLM-256M-Instruct", "SmolVLM-256M"),
    ("microsoft/Phi-3.5-vision-instruct",    "Phi-3.5-vision"),
    ("openbmb/MiniCPM-V-2_6",               "MiniCPM-V-2_6"),
]

# Device priority: NPU first (Intel AI Boost), then GPU (Intel iGPU), then CPU
DEVICE_PRIORITY = ["NPU", "GPU", "CPU"]

# ---------------------------------------------------------------------------
# Lazy-loaded pipeline state
# ---------------------------------------------------------------------------

_pipeline = None          # openvino_genai.VLMPipeline instance
_pipeline_lock = threading.Lock()
_pipeline_model_dir: Optional[Path] = None
_pipeline_device: Optional[str] = None
_openvino_available: Optional[bool] = None


def is_openvino_available() -> bool:
    """Return True if openvino-genai is installed."""
    global _openvino_available
    if _openvino_available is None:
        try:
            import openvino_genai  # noqa: F401
            _openvino_available = True
        except ImportError:
            _openvino_available = False
    return _openvino_available


def list_available_devices() -> list[str]:
    """Return OpenVINO device names available on this machine."""
    if not is_openvino_available():
        return []
    try:
        import openvino as ov
        core = ov.Core()
        return core.available_devices
    except Exception as exc:
        logger.warning("Cannot query OpenVINO devices: %s", exc)
        return []


def get_best_device() -> Optional[str]:
    """Return the best available device (NPU > GPU > CPU)."""
    available = list_available_devices()
    for dev in DEVICE_PRIORITY:
        if dev in available:
            return dev
    return available[0] if available else None


def find_local_model() -> Optional[Path]:
    """Return the path to the first available converted OpenVINO model dir."""
    if not _MODELS_DIR.exists():
        return None
    for _hf_id, folder_name in MODEL_PREFERENCE:
        model_dir = _MODELS_DIR / folder_name
        # A valid OV model dir contains openvino_model.xml
        if (model_dir / "openvino_model.xml").exists() or \
           (model_dir / "openvino_language_model.xml").exists():
            return model_dir
    return None


def get_status() -> dict:
    """Return a status dict for the /api/jarvis/health endpoint."""
    ov_ok = is_openvino_available()
    devices = list_available_devices() if ov_ok else []
    npu_present = "NPU" in devices
    best_dev = get_best_device() if ov_ok else None
    model_dir = find_local_model()
    ready = ov_ok and model_dir is not None

    return {
        "openvino_installed": ov_ok,
        "npu_present": npu_present,
        "devices": devices,
        "best_device": best_dev,
        "model_ready": ready,
        "model_dir": str(model_dir) if model_dir else None,
        "active_device": _pipeline_device,
    }


# ---------------------------------------------------------------------------
# Model download/convert
# ---------------------------------------------------------------------------

def download_model(
    hf_model_id: Optional[str] = None,
    folder_name: Optional[str] = None,
    device: Optional[str] = None,
    quantization: str = "int4",
) -> Path:
    """Download and convert a HuggingFace VLM to OpenVINO IR format.

    Uses ``optimum-cli export openvino`` under the hood.
    The result is cached in ``ov_models/<folder_name>/``.

    Args:
        hf_model_id:  HuggingFace model ID (default: SmolVLM-256M-Instruct)
        folder_name:  Output folder name under ov_models/ (default: auto)
        device:       Target device hint (NPU models need int4/int8 weights)
        quantization: ``"int4"`` (default, smallest) or ``"int8"`` or ``"fp16"``

    Returns:
        Path to the converted model directory.
    """
    if not is_openvino_available():
        raise RuntimeError(
            "openvino-genai is not installed. Run:\n"
            "  pip install openvino-genai optimum[openvino] huggingface_hub"
        )

    if hf_model_id is None:
        hf_model_id, folder_name = MODEL_PREFERENCE[0]
    if folder_name is None:
        folder_name = hf_model_id.split("/")[-1]

    out_dir = _MODELS_DIR / folder_name
    if find_local_model() == out_dir:
        logger.info("Model already present at %s", out_dir)
        return out_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Exporting %s → %s (quantization=%s) …", hf_model_id, out_dir, quantization)

    import subprocess, sys
    cmd = [
        sys.executable, "-m", "optimum.exporters.openvino",
        "--model", hf_model_id,
        "--task", "image-text-to-text",
        "--weight-format", quantization,
        "--trust-remote-code",
        str(out_dir),
    ]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        # Try via optimum-cli
        cmd2 = [
            "optimum-cli", "export", "openvino",
            "--model", hf_model_id,
            "--task", "image-text-to-text",
            "--weight-format", quantization,
            "--trust-remote-code",
            str(out_dir),
        ]
        result2 = subprocess.run(cmd2, capture_output=False)
        if result2.returncode != 0:
            raise RuntimeError(
                f"Model export failed. Try manually:\n"
                f"  optimum-cli export openvino --model {hf_model_id} "
                f"--task image-text-to-text --weight-format {quantization} "
                f"--trust-remote-code {out_dir}"
            )

    logger.info("Export complete: %s", out_dir)
    return out_dir


# ---------------------------------------------------------------------------
# Pipeline loading
# ---------------------------------------------------------------------------

def _load_pipeline(model_dir: Path, device: str):
    """Load (or reload) the VLMPipeline. Must be called under _pipeline_lock."""
    global _pipeline, _pipeline_model_dir, _pipeline_device
    import openvino_genai as ov_genai

    logger.info("Loading VLMPipeline from %s on %s …", model_dir, device)
    _pipeline = ov_genai.VLMPipeline(str(model_dir), device)
    _pipeline_model_dir = model_dir
    _pipeline_device = device
    logger.info("VLMPipeline ready on %s", device)


def _ensure_pipeline() -> tuple:
    """Ensure the pipeline is loaded. Returns (pipeline, device) or raises."""
    global _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline, _pipeline_device

        model_dir = find_local_model()
        if model_dir is None:
            raise RuntimeError(
                "No OpenVINO vision model found in ov_models/. "
                "Run setup_openvino_npu.bat or call download_model() first."
            )

        device = get_best_device()
        if device is None:
            raise RuntimeError("No OpenVINO device available.")

        _load_pipeline(model_dir, device)
        return _pipeline, _pipeline_device


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------

def query(image_bytes: bytes, question: str, max_new_tokens: int = 256) -> tuple[str, str]:
    """Run vision inference on image_bytes with the given question.

    Returns:
        (answer_text, device_used)

    Raises:
        RuntimeError if OpenVINO or model is not set up.
    """
    if not is_openvino_available():
        raise RuntimeError("openvino-genai not installed")

    import openvino_genai as ov_genai
    from PIL import Image  # type: ignore

    pipe, device = _ensure_pipeline()

    # Convert bytes → PIL Image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    generation_config = ov_genai.GenerationConfig()
    generation_config.max_new_tokens = max_new_tokens

    logger.debug("VLM query on %s: %r", device, question[:80])
    result = pipe.generate(question, image=image, generation_config=generation_config)
    answer = result if isinstance(result, str) else str(result)
    return answer.strip(), device


def query_b64(image_b64: str, question: str, max_new_tokens: int = 256) -> tuple[str, str]:
    """Convenience wrapper accepting base64-encoded image string."""
    image_bytes = base64.b64decode(image_b64)
    return query(image_bytes, question, max_new_tokens)
