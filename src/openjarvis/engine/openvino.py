"""OpenVINO inference engine backend for Intel NPU/GPU acceleration."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Sequence
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import EngineRegistry
from openjarvis.core.types import Message
from openjarvis.engine._base import (
    InferenceEngine,
    estimate_prompt_tokens,
    messages_to_dicts,
)
from openjarvis.engine._stubs import StreamChunk

logger = logging.getLogger(__name__)


@EngineRegistry.register("openvino")
class OpenVINOEngine(InferenceEngine):
    """OpenVINO backend for Intel NPU/GPU acceleration with Hugging Face models."""

    engine_id = "openvino"
    is_cloud = False

    def __init__(
        self,
        model_path: str | None = None,
        *,
        device: str = "CPU",  # CPU, GPU, NPU, or AUTO
        load_in_8bit: bool = True,
        cache_dir: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize OpenVINO engine.
        
        Args:
            model_path: Path to OpenVINO IR model or Hugging Face model ID
            device: Target device (CPU, GPU, NPU, AUTO)
            load_in_8bit: Enable INT8 quantization
            cache_dir: Directory for caching converted models
        """
        self._model_path = model_path
        self._device = device.upper()
        self._load_in_8bit = load_in_8bit
        self._cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".openjarvis", "openvino_cache")
        
        # Lazy loading - model loaded on first use
        self._model = None
        self._tokenizer = None
        self._initialized = False

    def _initialize_model(self) -> None:
        """Lazy initialize the OpenVINO model and tokenizer."""
        if self._initialized:
            return

        try:
            import openvino as ov
            from transformers import AutoTokenizer

            logger.info(f"Loading OpenVINO model: {self._model_path}")
            
            # Load tokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_path)
            
            # For now, raise NotImplementedError since automatic conversion
            # requires complex dependencies (optimum-intel with compatible versions)
            # Users can pre-convert models using OpenVINO tools
            raise NotImplementedError(
                "OpenVINO NPU inference requires pre-converted models. "
                "Please convert models using OpenVINO model converter tools, "
                "or install compatible optimum-intel dependencies. "
                "For now, please use the cloud engine or Ollama for inference."
            )

        except ImportError as e:
            logger.error(f"OpenVINO dependencies not installed: {e}")
            raise ImportError(
                "OpenVINO dependencies required. Install with: "
                "pip install openvino transformers"
            ) from e
        except Exception as e:
            logger.error(f"Failed to load OpenVINO model: {e}")
            raise

    def generate(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Synchronous completion using OpenVINO."""
        self._initialize_model()
        
        # Convert messages to prompt
        msg_dicts = messages_to_dicts(messages)
        prompt = self._format_messages(msg_dicts)
        
        # Tokenize
        inputs = self._tokenizer(prompt, return_tensors="pt")
        
        # Generate
        with self._model.device:
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id,
                **kwargs,
            )
        
        # Decode
        generated_text = self._tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Remove the original prompt from the response
        if generated_text.startswith(prompt):
            content = generated_text[len(prompt):].strip()
        else:
            content = generated_text
        
        # Estimate token usage
        prompt_tokens = estimate_prompt_tokens(messages)
        completion_tokens = len(self._tokenizer.encode(content))
        
        return {
            "content": content,
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        }

    async def stream(
        self,
        messages: Sequence[Message],
        *,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream tokens using OpenVINO."""
        self._initialize_model()
        
        # Convert messages to prompt
        msg_dicts = messages_to_dicts(messages)
        prompt = self._format_messages(msg_dicts)
        
        # Tokenize
        inputs = self._tokenizer(prompt, return_tensors="pt")
        
        # Stream generation
        streamer = self._model.generate(
            **inputs,
            max_new_tokens=max_tokens,
            temperature=temperature,
            do_sample=temperature > 0,
            pad_token_id=self._tokenizer.eos_token_id,
            **kwargs,
        )
        
        # Decode and yield tokens
        for token in streamer:
            if token:
                yield token

    def _format_messages(self, messages: Sequence[Dict[str, Any]]) -> str:
        """Format messages into a single prompt string."""
        # Simple chat format - can be enhanced based on model requirements
        formatted = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                formatted.append(f"System: {content}")
            elif role == "user":
                formatted.append(f"User: {content}")
            elif role == "assistant":
                formatted.append(f"Assistant: {content}")
        
        return "\n".join(formatted)

    def check_availability(self) -> bool:
        """Check if OpenVINO is available and properly configured."""
        try:
            import openvino as ov
            # Check if NPU/GPU devices are available
            core = ov.Core()
            available_devices = core.available_devices
            return len(available_devices) > 0
        except ImportError:
            return False
        except Exception:
            return False

    def health(self) -> bool:
        """Check if the OpenVINO engine is healthy and ready."""
        return self.check_availability()

    def list_models(self) -> List[str]:
        """Return list of available NPU-optimized models."""
        # Return NPU-optimized models from the catalog
        return [
            "phi-3-mini-4k-instruct",
            "tinyllama-1.1b",
            "gemma-2b",
            "llama-3.2-3b",
        ]