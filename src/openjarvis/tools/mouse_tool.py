"""Mouse control tool — move, click, scroll, and drag the mouse cursor."""

from __future__ import annotations

from typing import Any

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_VALID_BUTTONS = {"left", "right", "middle"}
_VALID_ACTIONS = {"move", "click", "double_click", "right_click", "scroll", "drag"}


@ToolRegistry.register("mouse")
class MouseTool(BaseTool):
    """Control the mouse: move, click, double-click, right-click, scroll, drag."""

    tool_id = "mouse"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="mouse",
            description=(
                "Control the mouse cursor. Supports: move, click, double_click,"
                " right_click, scroll, drag. Coordinates are in screen pixels."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(_VALID_ACTIONS),
                        "description": "Mouse action to perform.",
                    },
                    "x": {
                        "type": "integer",
                        "description": "X coordinate (pixels from left edge of screen).",
                    },
                    "y": {
                        "type": "integer",
                        "description": "Y coordinate (pixels from top edge of screen).",
                    },
                    "end_x": {
                        "type": "integer",
                        "description": "End X coordinate for drag action.",
                    },
                    "end_y": {
                        "type": "integer",
                        "description": "End Y coordinate for drag action.",
                    },
                    "button": {
                        "type": "string",
                        "enum": list(_VALID_BUTTONS),
                        "description": "Mouse button for click/double_click (default: left).",
                    },
                    "scroll_amount": {
                        "type": "integer",
                        "description": (
                            "Number of scroll clicks. Positive = down, negative = up."
                            " Default: 3."
                        ),
                    },
                    "duration": {
                        "type": "number",
                        "description": "Movement duration in seconds for smooth motion (default: 0.1).",
                    },
                },
                "required": ["action"],
            },
            category="desktop",
            requires_confirmation=False,
            timeout_seconds=15.0,
            required_capabilities=["desktop:control"],
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            import pyautogui
        except ImportError:
            return ToolResult(
                tool_name="mouse",
                content="pyautogui not installed. Run: uv sync --extra desktop",
                success=False,
            )

        action = str(params.get("action", "")).lower()
        if action not in _VALID_ACTIONS:
            return ToolResult(
                tool_name="mouse",
                content=f"Invalid action '{action}'. Valid: {sorted(_VALID_ACTIONS)}",
                success=False,
            )

        x = params.get("x")
        y = params.get("y")
        button = str(params.get("button", "left")).lower()
        if button not in _VALID_BUTTONS:
            button = "left"
        scroll_amount = int(params.get("scroll_amount", 3))
        duration = float(params.get("duration", 0.1))

        # Failsafe: pyautogui raises FailSafeException if mouse hits corner
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05

        try:
            if action == "move":
                if x is None or y is None:
                    return ToolResult(
                        tool_name="mouse",
                        content="move requires x and y.",
                        success=False,
                    )
                pyautogui.moveTo(int(x), int(y), duration=duration)
                return ToolResult(
                    tool_name="mouse",
                    content=f"Moved mouse to ({x}, {y}).",
                    success=True,
                    metadata={"x": x, "y": y},
                )

            elif action == "click":
                if x is not None and y is not None:
                    pyautogui.click(int(x), int(y), button=button, duration=duration)
                else:
                    pyautogui.click(button=button)
                pos = pyautogui.position()
                return ToolResult(
                    tool_name="mouse",
                    content=f"Clicked {button} button at ({pos.x}, {pos.y}).",
                    success=True,
                    metadata={"x": pos.x, "y": pos.y, "button": button},
                )

            elif action == "double_click":
                if x is not None and y is not None:
                    pyautogui.doubleClick(int(x), int(y), button=button, duration=duration)
                else:
                    pyautogui.doubleClick(button=button)
                pos = pyautogui.position()
                return ToolResult(
                    tool_name="mouse",
                    content=f"Double-clicked {button} button at ({pos.x}, {pos.y}).",
                    success=True,
                    metadata={"x": pos.x, "y": pos.y, "button": button},
                )

            elif action == "right_click":
                if x is not None and y is not None:
                    pyautogui.rightClick(int(x), int(y), duration=duration)
                else:
                    pyautogui.rightClick()
                pos = pyautogui.position()
                return ToolResult(
                    tool_name="mouse",
                    content=f"Right-clicked at ({pos.x}, {pos.y}).",
                    success=True,
                    metadata={"x": pos.x, "y": pos.y},
                )

            elif action == "scroll":
                if x is not None and y is not None:
                    pyautogui.moveTo(int(x), int(y), duration=duration)
                pyautogui.scroll(scroll_amount)
                pos = pyautogui.position()
                direction = "down" if scroll_amount > 0 else "up"
                return ToolResult(
                    tool_name="mouse",
                    content=f"Scrolled {direction} {abs(scroll_amount)} clicks at ({pos.x}, {pos.y}).",
                    success=True,
                    metadata={"x": pos.x, "y": pos.y, "scroll_amount": scroll_amount},
                )

            elif action == "drag":
                end_x = params.get("end_x")
                end_y = params.get("end_y")
                if any(v is None for v in (x, y, end_x, end_y)):
                    return ToolResult(
                        tool_name="mouse",
                        content="drag requires x, y, end_x, end_y.",
                        success=False,
                    )
                pyautogui.drag(
                    int(end_x) - int(x),
                    int(end_y) - int(y),
                    startX=int(x),
                    startY=int(y),
                    duration=duration,
                    button=button,
                )
                return ToolResult(
                    tool_name="mouse",
                    content=f"Dragged from ({x}, {y}) to ({end_x}, {end_y}).",
                    success=True,
                    metadata={"from": (x, y), "to": (end_x, end_y), "button": button},
                )

        except pyautogui.FailSafeException:
            return ToolResult(
                tool_name="mouse",
                content="Mouse failsafe triggered (cursor in corner). Move mouse away from corner.",
                success=False,
            )
        except Exception as exc:
            return ToolResult(
                tool_name="mouse",
                content=f"Mouse action failed: {exc}",
                success=False,
            )

        return ToolResult(tool_name="mouse", content="Unknown error.", success=False)


__all__ = ["MouseTool"]
