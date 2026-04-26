"""Screenshot tool — capture the screen and return it as a base64-encoded PNG."""

from __future__ import annotations

import base64
import io
from typing import Any, Optional

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec


@ToolRegistry.register("screenshot")
class ScreenshotTool(BaseTool):
    """Capture the current screen (or a region) and return base64-encoded PNG."""

    tool_id = "screenshot"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="screenshot",
            description=(
                "Capture the current screen and return a base64-encoded PNG image."
                " Optionally capture only a region with x, y, width, height."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "x": {
                        "type": "integer",
                        "description": "Left edge of capture region in pixels (default: 0).",
                    },
                    "y": {
                        "type": "integer",
                        "description": "Top edge of capture region in pixels (default: 0).",
                    },
                    "width": {
                        "type": "integer",
                        "description": "Width of capture region in pixels (default: full screen).",
                    },
                    "height": {
                        "type": "integer",
                        "description": "Height of capture region in pixels (default: full screen).",
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Optional file path to also save the PNG to disk.",
                    },
                },
                "required": [],
            },
            category="desktop",
            timeout_seconds=10.0,
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            import pyautogui
        except ImportError:
            return ToolResult(
                tool_name="screenshot",
                content="pyautogui not installed. Run: uv sync --extra desktop",
                success=False,
            )

        x: Optional[int] = params.get("x")
        y: Optional[int] = params.get("y")
        width: Optional[int] = params.get("width")
        height: Optional[int] = params.get("height")
        save_path: Optional[str] = params.get("save_path")

        # Determine region
        region = None
        if all(v is not None for v in (x, y, width, height)):
            region = (int(x), int(y), int(width), int(height))

        try:
            img = pyautogui.screenshot(region=region)
        except Exception as exc:
            return ToolResult(
                tool_name="screenshot",
                content=f"Screenshot failed: {exc}",
                success=False,
            )

        # Encode to base64 PNG
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        b64 = base64.b64encode(png_bytes).decode("ascii")

        # Optionally save to disk
        if save_path:
            try:
                img.save(save_path)
            except Exception as exc:
                return ToolResult(
                    tool_name="screenshot",
                    content=f"Screenshot captured but could not save to '{save_path}': {exc}",
                    success=False,
                    metadata={"base64_png": b64, "size": img.size},
                )

        return ToolResult(
            tool_name="screenshot",
            content=b64,
            success=True,
            metadata={
                "width": img.size[0],
                "height": img.size[1],
                "format": "PNG",
                "saved_to": save_path or "",
                "bytes": len(png_bytes),
            },
        )


__all__ = ["ScreenshotTool"]
