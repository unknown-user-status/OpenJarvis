"""Keyboard control tool — type text and press key combinations."""

from __future__ import annotations

from typing import Any, List

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

# Common hotkey names supported by pyautogui
_KNOWN_KEYS = {
    "enter", "return", "tab", "space", "backspace", "delete", "escape", "esc",
    "up", "down", "left", "right", "home", "end", "pageup", "pagedown",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "ctrl", "alt", "shift", "win", "command", "option",
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "print", "printscreen", "prtsc", "insert", "capslock", "numlock", "scrolllock",
    "volumeup", "volumedown", "volumemute",
}

_VALID_ACTIONS = {"type", "hotkey", "press", "key_down", "key_up"}


@ToolRegistry.register("keyboard")
class KeyboardTool(BaseTool):
    """Type text or press key combinations on the keyboard."""

    tool_id = "keyboard"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="keyboard",
            description=(
                "Control the keyboard. Actions: "
                "'type' to type a string of text; "
                "'hotkey' to press a key combination like Ctrl+C; "
                "'press' to press a single named key; "
                "'key_down'/'key_up' to hold or release a key."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(_VALID_ACTIONS),
                        "description": "Keyboard action to perform.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type (for action='type').",
                    },
                    "keys": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of key names for hotkey/press/key_down/key_up."
                            " Examples: ['ctrl', 'c'], ['win', 'd'], ['enter']."
                        ),
                    },
                    "interval": {
                        "type": "number",
                        "description": "Seconds between keystrokes when typing (default: 0.02).",
                    },
                },
                "required": ["action"],
            },
            category="desktop",
            requires_confirmation=False,
            timeout_seconds=30.0,
            required_capabilities=["desktop:control"],
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            import pyautogui
        except ImportError:
            return ToolResult(
                tool_name="keyboard",
                content="pyautogui not installed. Run: uv sync --extra desktop",
                success=False,
            )

        action = str(params.get("action", "")).lower()
        if action not in _VALID_ACTIONS:
            return ToolResult(
                tool_name="keyboard",
                content=f"Invalid action '{action}'. Valid: {sorted(_VALID_ACTIONS)}",
                success=False,
            )

        pyautogui.PAUSE = 0.05

        try:
            if action == "type":
                text = params.get("text", "")
                if not text:
                    return ToolResult(
                        tool_name="keyboard",
                        content="type action requires 'text'.",
                        success=False,
                    )
                interval = float(params.get("interval", 0.02))
                pyautogui.typewrite(text, interval=interval)
                # typewrite doesn't support unicode well; fall back to pyperclip+paste for non-ASCII
                return ToolResult(
                    tool_name="keyboard",
                    content=f"Typed {len(text)} characters.",
                    success=True,
                    metadata={"text_length": len(text)},
                )

            elif action == "hotkey":
                keys: List[str] = params.get("keys", [])
                if not keys:
                    return ToolResult(
                        tool_name="keyboard",
                        content="hotkey action requires 'keys' list.",
                        success=False,
                    )
                pyautogui.hotkey(*[k.lower() for k in keys])
                combo = "+".join(keys)
                return ToolResult(
                    tool_name="keyboard",
                    content=f"Pressed hotkey: {combo}",
                    success=True,
                    metadata={"keys": keys},
                )

            elif action == "press":
                keys = params.get("keys", [])
                if not keys:
                    return ToolResult(
                        tool_name="keyboard",
                        content="press action requires 'keys' list.",
                        success=False,
                    )
                for key in keys:
                    pyautogui.press(key.lower())
                return ToolResult(
                    tool_name="keyboard",
                    content=f"Pressed key(s): {', '.join(keys)}",
                    success=True,
                    metadata={"keys": keys},
                )

            elif action == "key_down":
                keys = params.get("keys", [])
                if not keys:
                    return ToolResult(
                        tool_name="keyboard",
                        content="key_down action requires 'keys' list.",
                        success=False,
                    )
                for key in keys:
                    pyautogui.keyDown(key.lower())
                return ToolResult(
                    tool_name="keyboard",
                    content=f"Held down key(s): {', '.join(keys)}",
                    success=True,
                    metadata={"keys": keys},
                )

            elif action == "key_up":
                keys = params.get("keys", [])
                if not keys:
                    return ToolResult(
                        tool_name="keyboard",
                        content="key_up action requires 'keys' list.",
                        success=False,
                    )
                for key in keys:
                    pyautogui.keyUp(key.lower())
                return ToolResult(
                    tool_name="keyboard",
                    content=f"Released key(s): {', '.join(keys)}",
                    success=True,
                    metadata={"keys": keys},
                )

        except Exception as exc:
            return ToolResult(
                tool_name="keyboard",
                content=f"Keyboard action failed: {exc}",
                success=False,
            )

        return ToolResult(tool_name="keyboard", content="Unknown error.", success=False)


__all__ = ["KeyboardTool"]
