"""Window management tool — list, focus, minimize, maximize, and close windows."""

from __future__ import annotations

from typing import Any, List

from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_VALID_ACTIONS = {"list", "focus", "minimize", "maximize", "restore", "close", "get_active"}


@ToolRegistry.register("window")
class WindowTool(BaseTool):
    """Manage OS windows: list open windows, focus, minimize, maximize, or close them."""

    tool_id = "window"
    is_local = True

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="window",
            description=(
                "Manage desktop windows. Actions: "
                "'list' to see all open windows with their titles; "
                "'get_active' to get the currently focused window; "
                "'focus' to bring a window to the foreground by title; "
                "'minimize'/'maximize'/'restore' to resize a window; "
                "'close' to close a window by title."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": list(_VALID_ACTIONS),
                        "description": "Window action to perform.",
                    },
                    "title": {
                        "type": "string",
                        "description": (
                            "Window title (or partial title) to target."
                            " Case-insensitive substring match."
                            " Required for focus/minimize/maximize/restore/close."
                        ),
                    },
                },
                "required": ["action"],
            },
            category="desktop",
            requires_confirmation=False,
            timeout_seconds=10.0,
            required_capabilities=["desktop:control"],
        )

    def execute(self, **params: Any) -> ToolResult:
        try:
            import pygetwindow as gw
        except ImportError:
            return ToolResult(
                tool_name="window",
                content="pygetwindow not installed. Run: uv sync --extra desktop",
                success=False,
            )

        action = str(params.get("action", "")).lower()
        if action not in _VALID_ACTIONS:
            return ToolResult(
                tool_name="window",
                content=f"Invalid action '{action}'. Valid: {sorted(_VALID_ACTIONS)}",
                success=False,
            )

        try:
            if action == "list":
                all_titles: List[str] = gw.getAllTitles()
                # Filter out empty/blank titles
                titles = [t for t in all_titles if t and t.strip()]
                if not titles:
                    return ToolResult(
                        tool_name="window",
                        content="No open windows found.",
                        success=True,
                        metadata={"count": 0, "titles": []},
                    )
                listing = "\n".join(f"  - {t}" for t in titles)
                return ToolResult(
                    tool_name="window",
                    content=f"Open windows ({len(titles)}):\n{listing}",
                    success=True,
                    metadata={"count": len(titles), "titles": titles},
                )

            elif action == "get_active":
                active = gw.getActiveWindow()
                if active is None:
                    return ToolResult(
                        tool_name="window",
                        content="No active window detected.",
                        success=True,
                        metadata={"title": None},
                    )
                return ToolResult(
                    tool_name="window",
                    content=f"Active window: '{active.title}'",
                    success=True,
                    metadata={
                        "title": active.title,
                        "left": active.left,
                        "top": active.top,
                        "width": active.width,
                        "height": active.height,
                    },
                )

            else:
                # Actions that require a title target
                title_query = params.get("title", "")
                if not title_query:
                    return ToolResult(
                        tool_name="window",
                        content=f"'{action}' requires a 'title' parameter.",
                        success=False,
                    )

                matches = gw.getWindowsWithTitle(title_query)
                if not matches:
                    # Try case-insensitive partial match
                    all_wins = gw.getAllWindows()
                    matches = [
                        w for w in all_wins
                        if title_query.lower() in (w.title or "").lower()
                    ]

                if not matches:
                    return ToolResult(
                        tool_name="window",
                        content=f"No window found matching '{title_query}'.",
                        success=False,
                    )

                win = matches[0]
                title = win.title

                if action == "focus":
                    win.activate()
                    return ToolResult(
                        tool_name="window",
                        content=f"Focused window: '{title}'",
                        success=True,
                        metadata={"title": title},
                    )

                elif action == "minimize":
                    win.minimize()
                    return ToolResult(
                        tool_name="window",
                        content=f"Minimized window: '{title}'",
                        success=True,
                        metadata={"title": title},
                    )

                elif action == "maximize":
                    win.maximize()
                    return ToolResult(
                        tool_name="window",
                        content=f"Maximized window: '{title}'",
                        success=True,
                        metadata={"title": title},
                    )

                elif action == "restore":
                    win.restore()
                    return ToolResult(
                        tool_name="window",
                        content=f"Restored window: '{title}'",
                        success=True,
                        metadata={"title": title},
                    )

                elif action == "close":
                    win.close()
                    return ToolResult(
                        tool_name="window",
                        content=f"Closed window: '{title}'",
                        success=True,
                        metadata={"title": title},
                    )

        except Exception as exc:
            return ToolResult(
                tool_name="window",
                content=f"Window action failed: {exc}",
                success=False,
            )

        return ToolResult(tool_name="window", content="Unknown error.", success=False)


__all__ = ["WindowTool"]
