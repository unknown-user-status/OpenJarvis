"""OpenJarvis plugin system — mirrors the sukeesh/Jarvis @plugin decorator pattern.

Usage
-----
Create a file anywhere under ``plugins/`` or ``custom/`` and decorate your
function with ``@plugin``:

    from openjarvis.plugins import plugin

    @plugin("hello")
    def hello(jarvis, s):
        \"\"\"Say hello back\"\"\"
        jarvis.say(f"Hello! You said: {s}")

The plugin name is the command the user types. The docstring becomes the
help text. ``jarvis`` is a :class:`JarvisContext` instance that exposes
``say``, ``ask``, ``control``, and other helpers.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import pathlib
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Registry: command_name -> (function, help_text)
_REGISTRY: Dict[str, tuple[Callable, str]] = {}


def plugin(name: str):
    """Decorator to register a Jarvis plugin command.

    Parameters
    ----------
    name:
        The command keyword(s) the user types. Supports spaces, e.g. ``"tell joke"``.
    """
    def decorator(fn: Callable) -> Callable:
        help_text = (fn.__doc__ or "").strip().split("\n")[0]
        _REGISTRY[name.lower()] = (fn, help_text)
        logger.debug("Registered plugin: %s", name)
        return fn
    return decorator


def get_plugins() -> Dict[str, tuple[Callable, str]]:
    """Return all registered plugins as {name: (fn, help_text)}."""
    return dict(_REGISTRY)


def load_directory(directory: str | pathlib.Path) -> int:
    """Import all .py files in *directory* so their @plugin decorators fire.

    Returns the number of files loaded.
    """
    path = pathlib.Path(directory)
    if not path.is_dir():
        return 0
    count = 0
    for py_file in sorted(path.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore[arg-type]
                count += 1
        except Exception as exc:
            logger.warning("Failed to load plugin %s: %s", py_file, exc)
    return count


# ---------------------------------------------------------------------------
# JarvisContext — passed as first arg to every plugin function
# ---------------------------------------------------------------------------

class JarvisContext:
    """Runtime context passed to plugin functions.

    Mirrors ``JarvisAPI`` from sukeesh/Jarvis with OpenJarvis-native backends.
    Includes persistent memory (MK37-style long_term.json).
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: str = "llama-3.3-70b-versatile",
    ) -> None:
        import os
        self._api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self._model = model
        self._output: List[str] = []
        # Lazy-load memory so the module can be imported without it
        self._memory: Optional[dict] = None

    # ------------------------------------------------------------------
    # Core methods
    # ------------------------------------------------------------------

    def say(self, text: str, speak: bool = True) -> None:
        """Print *text* and optionally speak it via TTS."""
        print(text)
        self._output.append(text)
        if speak:
            try:
                from openjarvis.speech.groq_tts import speak as _speak
                _speak(text)
            except Exception:
                pass

    def ask(self, question: str) -> str:
        """Ask Groq LLaMA a question and return the answer string."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key, base_url="https://api.groq.com/openai/v1")
            resp = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": question}],
                max_tokens=1024,
                temperature=0.7,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            return f"Error: {exc}"

    def control(self, goal: str) -> str:
        """Run DesktopAgent to control the machine. Returns summary."""
        try:
            from openjarvis.agents.desktop_agent import DesktopAgent
            agent = DesktopAgent(api_key=self._api_key, max_steps=15, verbose=True)
            return agent.run(goal)
        except Exception as exc:
            return f"Control error: {exc}"

    def input(self, prompt: str = "") -> str:
        """Get input from the user."""
        return input(prompt)

    def get_output(self) -> List[str]:
        """Return all text emitted via say() this session."""
        return list(self._output)

    # ------------------------------------------------------------------
    # Memory (MK37-style persistent store)
    # ------------------------------------------------------------------

    def _get_memory(self) -> dict:
        if self._memory is None:
            try:
                from openjarvis.memory.memory_manager import load_memory
                self._memory = load_memory()
            except Exception:
                self._memory = {}
        return self._memory

    def remember(self, key: str, value: str, category: str = "notes") -> str:
        """Persist a key/value pair in long-term memory."""
        try:
            from openjarvis.memory.memory_manager import remember as _remember
            result = _remember(key, value, category)
            self._memory = None  # invalidate cache
            return result
        except Exception as exc:
            return f"Memory error: {exc}"

    def recall(self, key: str, category: str = "notes") -> str:
        """Retrieve a value from long-term memory."""
        mem = self._get_memory()
        cat = mem.get(category, {})
        entry = cat.get(key)
        if entry:
            return entry.get("value", "") if isinstance(entry, dict) else str(entry)
        # Search all categories
        for cat_name, cat_data in mem.items():
            if isinstance(cat_data, dict) and key in cat_data:
                entry = cat_data[key]
                return entry.get("value", "") if isinstance(entry, dict) else str(entry)
        return ""

    def forget(self, key: str, category: str = "notes") -> str:
        """Remove a key from long-term memory."""
        try:
            from openjarvis.memory.memory_manager import forget as _forget
            result = _forget(key, category)
            self._memory = None
            return result
        except Exception as exc:
            return f"Memory error: {exc}"

    def memory_summary(self) -> str:
        """Return a formatted string of all known memory."""
        try:
            from openjarvis.memory.memory_manager import format_memory_for_prompt
            return format_memory_for_prompt(self._get_memory())
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def dispatch(command: str, context: Optional[JarvisContext] = None) -> Optional[str]:
    """Find and run the plugin matching *command*.

    Parameters
    ----------
    command:
        Raw user input string.
    context:
        JarvisContext instance. Created automatically if not provided.

    Returns
    -------
    str or None
        The output text, or None if no plugin matched.
    """
    ctx = context or JarvisContext()
    command = command.strip()

    # Try longest matching plugin name first (mirrors sukeesh/Jarvis behaviour)
    plugins = _REGISTRY
    matched_name = ""
    matched_fn = None
    for name in sorted(plugins, key=len, reverse=True):
        if command.lower().startswith(name):
            matched_name = name
            matched_fn, _ = plugins[name]
            break

    if matched_fn is None:
        return None

    remainder = command[len(matched_name):].strip()
    try:
        matched_fn(ctx, remainder)
    except Exception as exc:
        ctx.say(f"Plugin error: {exc}")

    return "\n".join(ctx.get_output())


__all__ = ["plugin", "get_plugins", "load_directory", "JarvisContext", "dispatch"]
