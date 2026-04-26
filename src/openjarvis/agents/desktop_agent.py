"""DesktopAgent — vision-guided agent that controls the local machine.

Loop:
  1. Take a screenshot
  2. Send screenshot + goal to a vision LLM (Groq llama-4-scout)
  3. LLM decides the next action (mouse, keyboard, window, shell, or done)
  4. Execute the action
  5. Repeat until the LLM says "DONE" or max_steps is reached

Designed to be used standalone (no registry wiring needed) so it works
directly from jarvis-voice.py and jarvis-terminal.sh.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported action schema the LLM must follow
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are DesktopAgent, an AI that controls a Windows computer to complete tasks.

Each turn you receive:
- The user's goal
- A screenshot of the current screen (base64 PNG)
- The history of actions taken so far

You must respond with a single JSON object — nothing else, no markdown, no explanation.

## Available actions

### Mouse
{"action": "mouse", "params": {"action": "click", "x": 100, "y": 200}}
{"action": "mouse", "params": {"action": "double_click", "x": 100, "y": 200}}
{"action": "mouse", "params": {"action": "right_click", "x": 100, "y": 200}}
{"action": "mouse", "params": {"action": "move", "x": 100, "y": 200}}
{"action": "mouse", "params": {"action": "scroll", "x": 100, "y": 200, "scroll_amount": -3}}
{"action": "mouse", "params": {"action": "drag", "x": 100, "y": 200, "end_x": 300, "end_y": 400}}

### Keyboard
{"action": "keyboard", "params": {"action": "type", "text": "hello world"}}
{"action": "keyboard", "params": {"action": "hotkey", "keys": ["ctrl", "c"]}}
{"action": "keyboard", "params": {"action": "press", "keys": ["enter"]}}
{"action": "keyboard", "params": {"action": "hotkey", "keys": ["win", "d"]}}

### Window
{"action": "window", "params": {"action": "list"}}
{"action": "window", "params": {"action": "focus", "title": "Chrome"}}
{"action": "window", "params": {"action": "maximize", "title": "Notepad"}}

### Shell
{"action": "shell", "params": {"command": "start notepad"}}
{"action": "shell", "params": {"command": "start chrome https://google.com"}}

### Screenshot (take a fresh screenshot to see the updated screen)
{"action": "screenshot"}

### Done (task is complete)
{"action": "done", "summary": "I opened Chrome and searched for the weather."}

## Rules
- Always look at the screenshot carefully before acting
- Prefer clicking visible UI elements rather than guessing coordinates
- After typing into a search box, press Enter to submit
- If something does not work, try a different approach
- When the task is complete, respond with {"action": "done", "summary": "..."}
- Never respond with anything other than a single JSON object
"""


# ---------------------------------------------------------------------------
# DesktopAgent
# ---------------------------------------------------------------------------


class DesktopAgent:
    """Vision-guided desktop control agent using Groq llama-4-scout."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-4-scout-17b-16e-instruct",
        max_steps: int = 20,
        step_delay: float = 1.0,
        verbose: bool = True,
    ) -> None:
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._model = model
        self._max_steps = max_steps
        self._step_delay = step_delay
        self._verbose = verbose

        if not self._api_key:
            raise RuntimeError("GROQ_API_KEY not set.")

        from openai import OpenAI
        self._client = OpenAI(
            api_key=self._api_key,
            base_url="https://api.groq.com/openai/v1",
        )

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, goal: str) -> str:
        """Run the agent to complete *goal*. Returns a summary string."""
        self._log(f"Goal: {goal}")
        history: List[Dict[str, Any]] = []

        for step in range(1, self._max_steps + 1):
            self._log(f"\n--- Step {step}/{self._max_steps} ---")

            # Take screenshot
            screenshot_b64 = self._take_screenshot()

            # Ask the LLM what to do next
            action_obj = self._decide(goal, screenshot_b64, history)
            self._log(f"LLM action: {json.dumps(action_obj)}")

            # Execute the action
            result, done, summary = self._execute(action_obj)
            self._log(f"Result: {result}")

            history.append({
                "step": step,
                "action": action_obj,
                "result": result,
            })

            if done:
                self._log(f"\nDone: {summary}")
                return summary

            # Brief pause to let the UI settle
            time.sleep(self._step_delay)

        return f"Reached max steps ({self._max_steps}) without completing the goal."

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _take_screenshot(self) -> str:
        """Capture the screen and return base64 PNG string."""
        try:
            import pyautogui
            img = pyautogui.screenshot()
            buf = io.BytesIO()
            # Downscale to 1280px wide to fit in LLM context
            w, h = img.size
            if w > 1280:
                ratio = 1280 / w
                img = img.resize((1280, int(h * ratio)))
            img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception as exc:
            logger.error("Screenshot failed: %s", exc)
            return ""

    def _decide(
        self,
        goal: str,
        screenshot_b64: str,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Call the vision LLM and get the next action as a dict."""
        history_text = ""
        if history:
            lines = []
            for h in history[-5:]:  # last 5 steps only
                lines.append(
                    f"Step {h['step']}: {json.dumps(h['action'])} -> {h['result']}"
                )
            history_text = "Recent actions:\n" + "\n".join(lines)

        user_content: List[Any] = [
            {"type": "text", "text": f"Goal: {goal}\n\n{history_text}\n\nWhat is the next action?"},
        ]
        if screenshot_b64:
            user_content.insert(0, {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
            })

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=512,
                temperature=0.1,
            )
            raw = resp.choices[0].message.content.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("LLM returned non-JSON: %s", exc)
            return {"action": "screenshot"}  # safe fallback: re-observe
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            return {"action": "done", "summary": f"Agent stopped due to error: {exc}"}

    def _execute(self, action_obj: Dict[str, Any]) -> tuple[str, bool, str]:
        """Execute one action. Returns (result_text, is_done, summary)."""
        action = action_obj.get("action", "")
        params = action_obj.get("params", {})

        if action == "done":
            summary = action_obj.get("summary", "Task complete.")
            return summary, True, summary

        if action == "screenshot":
            return "Screenshot taken.", False, ""

        if action == "shell":
            command = params.get("command", "")
            if not command:
                return "No command provided.", False, ""
            try:
                import subprocess
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=15
                )
                out = (result.stdout + result.stderr).strip()[:500]
                return out or "(no output)", False, ""
            except Exception as exc:
                return f"Shell error: {exc}", False, ""

        if action == "mouse":
            try:
                from openjarvis.tools.mouse_tool import MouseTool
                tool = MouseTool()
                res = tool.execute(**params)
                return res.content, False, ""
            except Exception as exc:
                return f"Mouse error: {exc}", False, ""

        if action == "keyboard":
            try:
                from openjarvis.tools.keyboard_tool import KeyboardTool
                tool = KeyboardTool()
                res = tool.execute(**params)
                return res.content, False, ""
            except Exception as exc:
                return f"Keyboard error: {exc}", False, ""

        if action == "window":
            try:
                from openjarvis.tools.window_tool import WindowTool
                tool = WindowTool()
                res = tool.execute(**params)
                return res.content, False, ""
            except Exception as exc:
                return f"Window error: {exc}", False, ""

        return f"Unknown action: '{action}'", False, ""

    def _log(self, msg: str) -> None:
        if self._verbose:
            print(msg)


__all__ = ["DesktopAgent"]
