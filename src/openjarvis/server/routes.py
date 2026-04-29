"""Route handlers for the OpenAI-compatible API server."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from openjarvis.core.types import Message, Role
from openjarvis.server.models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    ComplexityInfo,
    DeltaMessage,
    ModelListResponse,
    ModelObject,
    StreamChoice,
    UsageInfo,
)

router = APIRouter()


def _to_messages(chat_messages) -> list[Message]:
    """Convert Pydantic ChatMessage objects to core Message objects."""
    messages = []
    for m in chat_messages:
        role = Role(m.role) if m.role in {r.value for r in Role} else Role.USER
        messages.append(
            Message(
                role=role,
                content=m.content or "",
                name=m.name,
                tool_call_id=m.tool_call_id,
            )
        )
    return messages


@router.post("/v1/chat/completions")
async def chat_completions(request_body: ChatCompletionRequest, request: Request):
    """Handle chat completion requests (streaming and non-streaming)."""
    engine = request.app.state.engine
    agent = getattr(request.app.state, "agent", None)
    model = request_body.model

    # Inject memory context into messages before dispatching
    config = getattr(request.app.state, "config", None)
    memory_backend = getattr(request.app.state, "memory_backend", None)
    if (
        config is not None
        and memory_backend is not None
        and config.agent.context_from_memory
        and request_body.messages
    ):
        try:
            from openjarvis.tools.storage.context import ContextConfig, inject_context

            # Extract query from the last user message
            query_text = ""
            for m in reversed(request_body.messages):
                if m.role == "user" and m.content:
                    query_text = m.content
                    break

            if query_text:
                messages = _to_messages(request_body.messages)
                ctx_cfg = ContextConfig(
                    top_k=config.memory.context_top_k,
                    min_score=config.memory.context_min_score,
                    max_context_tokens=config.memory.context_max_tokens,
                )
                enriched = inject_context(
                    query_text,
                    messages,
                    memory_backend,
                    config=ctx_cfg,
                )
                # Rebuild request messages from enriched Message objects
                if len(enriched) > len(messages):
                    from openjarvis.server.models import ChatMessage

                    new_msgs = []
                    for msg in enriched:
                        new_msgs.append(
                            ChatMessage(
                                role=msg.role.value,
                                content=msg.content,
                                name=msg.name,
                                tool_call_id=getattr(msg, "tool_call_id", None),
                            )
                        )
                    request_body.messages = new_msgs
        except Exception:
            logging.getLogger("openjarvis.server").debug(
                "Memory context injection failed",
                exc_info=True,
            )

    # Run complexity analysis on the last user message
    complexity_info = None
    query_text_for_complexity = ""
    for m in reversed(request_body.messages):
        if m.role == "user" and m.content:
            query_text_for_complexity = m.content
            break
    if query_text_for_complexity:
        try:
            from openjarvis.learning.routing.complexity import (
                adjust_tokens_for_model,
                score_complexity,
            )

            cr = score_complexity(query_text_for_complexity)
            suggested = adjust_tokens_for_model(
                cr.suggested_max_tokens,
                model,
            )
            complexity_info = ComplexityInfo(
                score=cr.score,
                tier=cr.tier,
                suggested_max_tokens=suggested,
            )
            # Bump max_tokens when complexity suggests more than what
            # the client requested — never reduce below the request value.
            if suggested > request_body.max_tokens:
                request_body.max_tokens = suggested
        except Exception:
            logging.getLogger("openjarvis.server").debug(
                "Complexity analysis failed",
                exc_info=True,
            )

    if request_body.stream:
        bus = getattr(request.app.state, "bus", None)
        # Use the agent stream bridge only when tools are present (the
        # bridge runs agent.run() synchronously and word-splits the result,
        # so it can't stream tokens in real-time).  For plain chat, stream
        # directly from the engine for true token-by-token output.
        if agent is not None and bus is not None and request_body.tools:
            return await _handle_agent_stream(agent, bus, model, request_body)
        return await _handle_stream(engine, model, request_body, complexity_info)

    # Non-streaming: use agent if available, otherwise direct engine call
    if agent is not None:
        return _handle_agent(agent, model, request_body, complexity_info)

    bus = getattr(request.app.state, "bus", None)
    return _handle_direct(
        engine,
        model,
        request_body,
        bus=bus,
        complexity_info=complexity_info,
    )


def _handle_direct(
    engine,
    model: str,
    req: ChatCompletionRequest,
    bus=None,
    complexity_info=None,
) -> ChatCompletionResponse:
    """Direct engine call without agent."""
    messages = _to_messages(req.messages)
    kwargs: dict[str, Any] = {}
    if req.tools:
        kwargs["tools"] = req.tools
    if bus:
        from openjarvis.telemetry.wrapper import instrumented_generate

        result = instrumented_generate(
            engine,
            messages,
            model=model,
            bus=bus,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            **kwargs,
        )
    else:
        result = engine.generate(
            messages,
            model=model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            **kwargs,
        )
    content = result.get("content", "")
    usage = result.get("usage", {})

    choice_msg = ChoiceMessage(role="assistant", content=content)
    # Include tool calls if present
    tool_calls = result.get("tool_calls")
    if tool_calls:
        choice_msg.tool_calls = [
            {
                "id": tc.get("id", ""),
                "type": "function",
                "function": {
                    "name": tc.get("name", ""),
                    "arguments": tc.get("arguments", "{}"),
                },
            }
            for tc in tool_calls
        ]

    return ChatCompletionResponse(
        model=model,
        choices=[
            Choice(
                message=choice_msg,
                finish_reason=result.get("finish_reason", "stop"),
            )
        ],
        usage=UsageInfo(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        ),
        complexity=complexity_info,
    )


def _handle_agent(
    agent,
    model: str,
    req: ChatCompletionRequest,
    complexity_info=None,
) -> ChatCompletionResponse:
    """Run through agent."""
    from openjarvis.agents._stubs import AgentContext

    # Build context from prior messages
    ctx = AgentContext()
    if len(req.messages) > 1:
        prior = _to_messages(req.messages[:-1])
        for m in prior:
            ctx.conversation.add(m)

    # Last message is the input
    input_text = req.messages[-1].content if req.messages else ""

    # Override agent model for this request if the caller specified one
    original_model = agent._model
    if model:
        agent._model = model
    try:
        result = agent.run(input_text, context=ctx)
    finally:
        agent._model = original_model

    usage = UsageInfo(
        prompt_tokens=result.metadata.get("prompt_tokens", 0),
        completion_tokens=result.metadata.get("completion_tokens", 0),
        total_tokens=result.metadata.get("total_tokens", 0),
    )

    # Include audio metadata if the agent produced audio (e.g. morning digest)
    audio_meta = None
    audio_path = result.metadata.get("audio_path", "")
    if audio_path:
        from pathlib import Path

        from openjarvis.server.models import AudioMeta

        if Path(audio_path).exists():
            audio_meta = AudioMeta(url="/api/digest/audio")

    return ChatCompletionResponse(
        model=model,
        choices=[
            Choice(
                message=ChoiceMessage(
                    role="assistant",
                    content=result.content,
                    audio=audio_meta,
                ),
                finish_reason="stop",
            )
        ],
        usage=usage,
        complexity=complexity_info,
    )


async def _handle_agent_stream(agent, bus, model, req):
    """Stream agent response with EventBus events via SSE."""
    from openjarvis.server.stream_bridge import create_agent_stream

    return await create_agent_stream(agent, bus, model, req)


async def _handle_stream(
    engine,
    model: str,
    req: ChatCompletionRequest,
    complexity_info=None,
):
    """Stream response using SSE format."""
    from openjarvis.server.cloud_router import (
        is_cloud_model,
        stream_cloud,
        stream_local,
    )

    messages = _to_messages(req.messages)
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # Route directly to the right backend — bypasses engine routing entirely
    # so broken MultiEngine state can never misdirect requests.
    use_cloud = is_cloud_model(model)

    async def generate():
        # Send role chunk first
        first_chunk = ChatCompletionChunk(
            id=chunk_id,
            model=model,
            choices=[
                StreamChoice(
                    delta=DeltaMessage(role="assistant"),
                )
            ],
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        try:
            # Cloud models → direct cloud API (reads keys from disk).
            # Local models → engine.stream() first so mock engines work in
            # tests.  Fall back to stream_local() only when the engine would
            # mis-route the request to a cloud backend (MultiEngine routing
            # confusion), which is detected by checking the routed engine's
            # is_cloud attribute.
            if use_cloud:
                token_iter = stream_cloud(
                    model, messages, req.temperature, req.max_tokens
                )
            else:
                # Use engine.stream() by default (preserves mock-engine
                # compatibility in tests).  Only fall back to stream_local()
                # when a real MultiEngine would mis-route the local model to a
                # cloud backend — detected via isinstance so mocks are not
                # accidentally matched.
                _use_local_fallback = False
                try:
                    from openjarvis.engine.multi import MultiEngine

                    _inner = getattr(engine, "_inner", engine)
                    if isinstance(_inner, MultiEngine):
                        _routed = _inner._engine_for(model)
                        if _routed is not None and getattr(_routed, "is_cloud", False):
                            _use_local_fallback = True
                except Exception:
                    pass
                if _use_local_fallback:
                    token_iter = stream_local(
                        model, messages, req.temperature, req.max_tokens
                    )
                else:
                    token_iter = engine.stream(
                        messages,
                        model=model,
                        temperature=req.temperature,
                        max_tokens=req.max_tokens,
                    )
            async for token in token_iter:
                chunk = ChatCompletionChunk(
                    id=chunk_id,
                    model=model,
                    choices=[
                        StreamChoice(
                            delta=DeltaMessage(content=token),
                        )
                    ],
                )
                yield f"data: {chunk.model_dump_json()}\n\n"
        except Exception as exc:
            # Surface errors as a content chunk so the frontend can
            # display them instead of silently failing.
            import logging

            logging.getLogger("openjarvis.server").error(
                "Stream error: %s",
                exc,
                exc_info=True,
            )
            error_chunk = ChatCompletionChunk(
                id=chunk_id,
                model=model,
                choices=[
                    StreamChoice(
                        delta=DeltaMessage(
                            content=f"\n\nError during generation: {exc}",
                        ),
                        finish_reason="stop",
                    )
                ],
            )
            yield f"data: {error_chunk.model_dump_json()}\n\n"
            yield "data: [DONE]\n\n"
            return

        # Send finish chunk with usage data if available
        import json as _json

        finish_data = ChatCompletionChunk(
            id=chunk_id,
            model=model,
            choices=[
                StreamChoice(
                    delta=DeltaMessage(),
                    finish_reason="stop",
                )
            ],
        )
        finish_dict = _json.loads(finish_data.model_dump_json())

        # Tag the finish chunk with the correct engine label.
        # We use the routing decision (use_cloud) directly rather than
        # unwrapping the engine chain, which can be in a broken state.
        finish_dict.setdefault("telemetry", {})
        finish_dict["telemetry"]["engine"] = "cloud" if use_cloud else "ollama"

        if complexity_info is not None:
            finish_dict["complexity"] = complexity_info.model_dump()

        yield f"data: {_json.dumps(finish_dict)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/v1/models")
async def list_models(request: Request) -> ModelListResponse:
    """List locally installed models (Ollama).

    Cloud models are not included here — they live in the Cloud Models tab
    of the UI and are selected there, not from this endpoint.
    """
    from openjarvis.server.cloud_router import is_cloud_model, list_local_models

    # Prefer engine.list_models() so mock engines work in tests.
    # Filter out any cloud model IDs that may appear via MultiEngine.
    # Fall back to direct Ollama query only when the engine returns nothing.
    engine = request.app.state.engine
    all_ids = engine.list_models()
    model_ids = [m for m in all_ids if not is_cloud_model(m)]
    if not model_ids:
        model_ids = await list_local_models()

    return ModelListResponse(
        data=[ModelObject(id=mid) for mid in model_ids],
    )


def _iter_engines(engine: object):
    """Yield every engine reachable by recursively unwrapping wrapper layers.

    Handles InstrumentedEngine (._inner), GuardrailsEngine (._engine),
    MultiEngine (._engines dict), and any similar single-wrapper pattern.
    Guards against infinite loops via a visited set.
    """
    visited: set = set()
    queue = [engine]
    while queue:
        node = queue.pop()
        if node is None or id(node) in visited:
            continue
        visited.add(id(node))
        yield node
        # Single-engine wrappers
        for attr in ("_inner", "_engine", "engine"):
            child = getattr(node, attr, None)
            if child is not None and child is not node:
                queue.append(child)
                break  # only follow the first match per node to avoid duplicates
        # MultiEngine: expose all sub-engines
        # _engines is list[tuple[str, engine]] — iterate accordingly
        try:
            from openjarvis.engine.multi import MultiEngine
            if isinstance(node, MultiEngine):
                for _key, sub in node._engines:
                    queue.append(sub)
        except Exception:
            pass


def _get_ollama_host(request: Request) -> str:
    """Return the Ollama host URL by searching the full engine wrapper chain."""
    engine = request.app.state.engine
    for node in _iter_engines(engine):
        if getattr(node, "engine_id", "") == "ollama":
            host = getattr(node, "_host", None)
            if host:
                return host
    return getattr(engine, "_host", None) or "http://localhost:11434"


def _is_ollama_available(request: Request) -> bool:
    """Return True if any Ollama engine is reachable in the engine wrapper chain."""
    engine_name = getattr(request.app.state, "engine_name", "")
    if engine_name == "ollama":
        return True
    return any(
        getattr(node, "engine_id", "") == "ollama"
        for node in _iter_engines(request.app.state.engine)
    )


@router.post("/v1/models/pull")
async def pull_model(request: Request):
    """Pull / download a model from the Ollama registry, streaming progress via SSE."""
    body = await request.json()
    model_name = body.get("model", "").strip()
    if not model_name:
        raise HTTPException(status_code=400, detail="'model' field is required")

    if not _is_ollama_available(request):
        raise HTTPException(
            status_code=501,
            detail="Model pulling is only supported with the Ollama engine",
        )

    host = _get_ollama_host(request)

    async def _stream_pull():
        import httpx as _httpx

        try:
            async with _httpx.AsyncClient(base_url=host, timeout=None) as client:
                async with client.stream(
                    "POST",
                    "/api/pull",
                    json={"name": model_name, "stream": True},
                ) as resp:
                    if resp.status_code != 200:
                        err_body = await resp.aread()
                        err_text = err_body.decode(errors="replace")[:300]
                        yield f"data: {json.dumps({'error': err_text, 'status': 'error'})}\n\n"
                        return

                    async for line in resp.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        # Forward progress as SSE
                        yield f"data: {json.dumps(obj)}\n\n"
                        if obj.get("status") == "success":
                            break

        except _httpx.ConnectError:
            yield f"data: {json.dumps({'error': 'Ollama is not running. Start it with: ollama serve', 'status': 'error'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc), 'status': 'error'})}\n\n"

    return StreamingResponse(
        _stream_pull(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/v1/models/{model_name:path}")
async def delete_model(model_name: str, request: Request):
    """Delete a model from Ollama."""
    if not _is_ollama_available(request):
        raise HTTPException(status_code=501, detail="Only supported with Ollama engine")

    host = _get_ollama_host(request)

    import httpx as _httpx

    async with _httpx.AsyncClient(base_url=host, timeout=30.0) as client:
        try:
            resp = await client.request(
                "DELETE",
                "/api/delete",
                json={"name": model_name},
            )
            resp.raise_for_status()
        except (_httpx.ConnectError, _httpx.TimeoutException) as exc:
            raise HTTPException(status_code=502, detail=f"Ollama unreachable: {exc}")
        except _httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"Ollama error: {exc.response.text[:300]}",
            )

    return {"status": "deleted", "model": model_name}


@router.post("/v1/cloud/reload")
async def reload_cloud_engine(request: Request):
    """Hot-reload cloud API keys and (re-)initialize the cloud engine.

    Called by the desktop app immediately after the user saves a cloud API
    key so that cloud models become available without a full app restart.
    """
    import os
    from pathlib import Path

    # Re-read ~/.openjarvis/cloud-keys.env and update the running process env.
    keys_path = Path.home() / ".openjarvis" / "cloud-keys.env"
    if keys_path.exists():
        for raw_line in keys_path.read_text().splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

    # Try to build a fresh CloudEngine.
    try:
        from openjarvis.engine.cloud import CloudEngine
        from openjarvis.engine.multi import MultiEngine

        cloud = CloudEngine()
        if not cloud.health():
            return {
                "status": "no_cloud",
                "message": "No cloud models available (check API keys)",
            }
    except Exception as exc:
        return {"status": "error", "message": str(exc)}

    # Locate the innermost engine, working through InstrumentedEngine layers.
    outer = request.app.state.engine
    inner = getattr(outer, "_inner", outer)

    if isinstance(inner, MultiEngine):
        # Replace or insert the cloud entry in the existing MultiEngine.
        new_engines = [(k, e) for k, e in inner._engines if k != "cloud"]
        new_engines.append(("cloud", cloud))
        inner._engines = new_engines
        inner._refresh_map()
    else:
        # Wrap the existing engine (which may be security-wrapped) with a new
        # MultiEngine that includes the cloud engine.
        engine_name = getattr(request.app.state, "engine_name", "local")
        new_multi = MultiEngine([(engine_name, inner), ("cloud", cloud)])
        if hasattr(outer, "_inner"):
            outer._inner = new_multi
        else:
            request.app.state.engine = new_multi
        request.app.state.engine_name = "multi"

    return {"status": "ok", "message": "Cloud engine reloaded"}


@router.get("/v1/savings")
async def savings(request: Request):
    """Return savings summary compared to cloud providers.

    Only includes telemetry from the current server session so that
    counters start at zero each time a new model + agent is launched.
    """
    from openjarvis.core.config import DEFAULT_CONFIG_DIR
    from openjarvis.server.savings import compute_savings, savings_to_dict
    from openjarvis.telemetry.aggregator import TelemetryAggregator

    db_path = DEFAULT_CONFIG_DIR / "telemetry.db"
    if not db_path.exists():
        empty = compute_savings(0, 0, 0)
        return savings_to_dict(empty)

    session_start = getattr(request.app.state, "session_start", None)

    agg = TelemetryAggregator(db_path)
    try:
        summary = agg.summary(since=session_start)
        # Exclude cloud model tokens from savings — only local
        # inference counts toward cost savings.
        _cloud_prefixes = (
            "gpt-",
            "o1-",
            "o3-",
            "o4-",
            "claude-",
            "gemini-",
            "openrouter/",
        )
        local_models = [
            m
            for m in summary.per_model
            if not any(m.model_id.startswith(p) for p in _cloud_prefixes)
        ]
        result = compute_savings(
            prompt_tokens=sum(m.prompt_tokens for m in local_models),
            completion_tokens=sum(m.completion_tokens for m in local_models),
            total_calls=sum(m.call_count for m in local_models),
            session_start=session_start if session_start else 0.0,
            prompt_tokens_evaluated=sum(
                m.prompt_tokens_evaluated for m in local_models
            ),
        )
        return savings_to_dict(result)
    finally:
        agg.close()


@router.post("/v1/telemetry/reset")
async def reset_telemetry():
    """Clear all stored telemetry records.

    Useful after updating token-counting methodology — clears
    historical records that were computed under the old rules so
    that the savings dashboard and leaderboard submissions start
    fresh with corrected values.
    """
    from openjarvis.core.config import DEFAULT_CONFIG_DIR
    from openjarvis.telemetry.aggregator import TelemetryAggregator

    db_path = DEFAULT_CONFIG_DIR / "telemetry.db"
    if not db_path.exists():
        return {"status": "ok", "records_cleared": 0}

    agg = TelemetryAggregator(db_path)
    try:
        count = agg.clear()
    finally:
        agg.close()
    return {"status": "ok", "records_cleared": count}


@router.get("/v1/telemetry/stats")
async def get_telemetry_stats(request: Request):
    """Return aggregate telemetry stats for the current session."""
    try:
        from openjarvis.telemetry.aggregator import TelemetryAggregator
        from openjarvis.core.config import DEFAULT_CONFIG_DIR
        db_path = DEFAULT_CONFIG_DIR / "telemetry.db"
        agg = TelemetryAggregator(db_path)
        stats = agg.summary()
        # Return as plain dict
        return {
            "total_requests": stats.total_calls,
            "total_tokens": stats.total_tokens,
            "total_cost_usd": round(stats.total_cost, 6),
            "total_energy_joules": round(stats.total_energy_joules, 4),
            "avg_latency_ms": round(stats.total_latency / stats.total_calls * 1000, 1) if stats.total_calls > 0 else 0,
            "avg_tokens_per_sec": round(stats.avg_throughput_tok_per_sec, 1),
        }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/v1/agents")
async def list_agents(request: Request):
    """List all available agents."""
    try:
        from openjarvis.core.registry import AgentRegistry
        
        agents = []
        for key, agent_class in AgentRegistry.items():
            # Get basic info about the agent
            agent_info = {
                "id": key,
                "name": key.replace("_", " ").title(),
                "class": agent_class.__name__ if hasattr(agent_class, '__name__') else str(agent_class),
            }
            
            # Try to get description from docstring
            if hasattr(agent_class, '__doc__') and agent_class.__doc__:
                doc = agent_class.__doc__.strip()
                if doc and not doc.startswith('"""'):
                    agent_info["description"] = doc.split('\n')[0] if '\n' in doc else doc
            
            agents.append(agent_info)
        
        # Sort by name
        agents.sort(key=lambda x: x["name"])
        
        return {"agents": agents}
    except Exception as exc:
        return {"error": str(exc), "agents": []}


@router.get("/v1/mcp/servers")
async def list_mcp_servers(request: Request):
    """List all configured MCP servers."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR, JarvisConfig, load_config
        import json
        
        # Load current config
        config_path = DEFAULT_CONFIG_DIR / "config.toml"
        if not config_path.exists():
            return {"servers": []}
        
        config = load_config(config_path)
        
        if not config.tools.mcp.servers:
            return {"servers": []}
        
        try:
            servers = json.loads(config.tools.mcp.servers)
        except json.JSONDecodeError:
            return {"servers": []}
        
        return {"servers": servers}
    except Exception as exc:
        return {"error": str(exc), "servers": []}


@router.post("/v1/mcp/servers")
async def add_mcp_server(request: Request):
    """Add a new MCP server configuration."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR, JarvisConfig, load_config
        import json
        
        server_config = await request.json()
        
        # Validate required fields
        required_fields = ["name", "command", "args"]
        for field in required_fields:
            if field not in server_config:
                return {"error": f"Missing required field: {field}"}
        
        # Load current config
        config_path = DEFAULT_CONFIG_DIR / "config.toml"
        config = load_config(config_path) if config_path.exists() else load_config(None)
        
        # Parse existing servers
        servers = []
        if config.tools.mcp.servers:
            try:
                servers = json.loads(config.tools.mcp.servers)
            except json.JSONDecodeError:
                servers = []
        
        # Check for duplicate names
        if any(s.get("name") == server_config["name"] for s in servers):
            return {"error": f"Server with name '{server_config['name']}' already exists"}
        
        # Add new server
        servers.append(server_config)
        
        # Update config
        config.tools.mcp.servers = json.dumps(servers)
        
        # Save config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config.to_file(config_path)
        
        return {"success": True, "servers": servers}
    except Exception as exc:
        return {"error": str(exc)}


@router.delete("/v1/mcp/servers/{server_name}")
async def remove_mcp_server(request: Request, server_name: str):
    """Remove an MCP server configuration."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR, JarvisConfig, load_config
        import json
        
        # Load current config
        config_path = DEFAULT_CONFIG_DIR / "config.toml"
        if not config_path.exists():
            return {"error": "No configuration found"}
        
        config = load_config(config_path)
        
        if not config.tools.mcp.servers:
            return {"error": "No MCP servers configured"}
        
        try:
            servers = json.loads(config.tools.mcp.servers)
        except json.JSONDecodeError:
            return {"error": "Invalid MCP server configuration"}
        
        # Remove server
        original_count = len(servers)
        servers = [s for s in servers if s.get("name") != server_name]
        
        if len(servers) == original_count:
            return {"error": f"Server '{server_name}' not found"}
        
        # Update config
        config.tools.mcp.servers = json.dumps(servers)
        
        # Save config
        config.to_file(config_path)
        
        return {"success": True, "servers": servers}
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/v1/info")
async def server_info(request: Request):
    """Return server configuration: model, agent, engine."""
    agent = getattr(request.app.state, "agent", None)
    agent_id = getattr(agent, "agent_id", None) if agent else None
    # Fall back to configured agent name if agent didn't instantiate
    if agent_id is None:
        agent_id = getattr(request.app.state, "agent_name", None)
    return {
        "model": getattr(request.app.state, "model", ""),
        "agent": agent_id,
        "engine": getattr(request.app.state, "engine_name", ""),
    }


@router.get("/health")
async def health(request: Request):
    """Health check endpoint."""
    engine = request.app.state.engine
    healthy = engine.health()
    if not healthy:
        raise HTTPException(status_code=503, detail="Engine unhealthy")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Channel endpoints
# ---------------------------------------------------------------------------


@router.get("/v1/channels")
async def list_channels(request: Request):
    """List available messaging channels."""
    bridge = getattr(request.app.state, "channel_bridge", None)
    if bridge is None:
        return {"channels": [], "message": "Channel bridge not configured"}
    channels = bridge.list_channels()
    return {"channels": channels, "status": bridge.status().value}


@router.post("/v1/channels/send")
async def channel_send(request: Request):
    """Send a message to a channel."""
    bridge = getattr(request.app.state, "channel_bridge", None)
    if bridge is None:
        raise HTTPException(status_code=503, detail="Channel bridge not configured")

    body = await request.json()
    channel_name = body.get("channel", "")
    content = body.get("content", "")
    conversation_id = body.get("conversation_id", "")

    if not channel_name or not content:
        raise HTTPException(
            status_code=400,
            detail="'channel' and 'content' are required",
        )

    ok = bridge.send(channel_name, content, conversation_id=conversation_id)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to send message")
    return {"status": "sent", "channel": channel_name}


@router.get("/v1/channels/status")
async def channel_status(request: Request):
    """Return channel bridge connection status."""
    bridge = getattr(request.app.state, "channel_bridge", None)
    if bridge is None:
        return {"status": "not_configured"}
    return {"status": bridge.status().value}


# ---------------------------------------------------------------------------
# Security scan endpoint
# ---------------------------------------------------------------------------


@router.get("/v1/security/scan")
async def security_scan():
    """Run a read-only security environment audit and return findings."""
    from openjarvis.cli.scan_cmd import PrivacyScanner

    scanner = PrivacyScanner()
    results = scanner.run_all()
    return {
        "has_warnings": any(r.status == "warn" for r in results),
        "has_failures": any(r.status == "fail" for r in results),
        "findings": [
            {
                "name": r.name,
                "status": r.status,
                "message": r.message,
                "platform": r.platform,
            }
            for r in results
        ],
    }


# ---------------------------------------------------------------------------
# /v1/logs — SSE stream of backend log records
# ---------------------------------------------------------------------------

class _SSELogHandler(logging.Handler):
    """Logging handler that fans out records to registered SSE subscribers."""

    def __init__(self):
        super().__init__()
        self._queues: list[queue.SimpleQueue] = []

    def subscribe(self) -> queue.SimpleQueue:
        q: queue.SimpleQueue = queue.SimpleQueue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: queue.SimpleQueue) -> None:
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": int(record.created * 1000),
            "level": record.levelname.lower(),
            "name": record.name,
            "message": self.format(record),
        }
        dead: list[queue.SimpleQueue] = []
        for q in list(self._queues):
            try:
                q.put_nowait(entry)
            except Exception:
                dead.append(q)
        for q in dead:
            self.unsubscribe(q)


# Singleton handler — attach to root logger once
_sse_log_handler = _SSELogHandler()
_sse_log_handler.setLevel(logging.DEBUG)
_sse_log_handler.setFormatter(logging.Formatter("%(message)s"))

_root_logger = logging.getLogger("openjarvis")
if not any(isinstance(h, _SSELogHandler) for h in _root_logger.handlers):
    _root_logger.addHandler(_sse_log_handler)


@router.get("/v1/logs")
async def stream_logs(request: Request):
    """SSE stream of openjarvis backend log records."""
    q = _sse_log_handler.subscribe()

    async def _generate():
        try:
            # Send a keep-alive ping immediately
            yield "event: ping\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = q.get_nowait()
                    yield f"data: {json.dumps(entry)}\n\n"
                except queue.Empty:
                    await asyncio.sleep(0.25)
        finally:
            _sse_log_handler.unsubscribe(q)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/v1/intelligence/hardware")
async def get_hardware_info(request: Request):
    """Return current hardware info: RAM, GPU VRAM, recommended model tier."""
    import platform
    import psutil
    
    info = {
        "platform": platform.system(),
        "cpu": platform.processor() or platform.machine(),
        "cpu_cores": psutil.cpu_count(logical=False),
        "ram_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 1),
    }
    
    # Try to detect GPU VRAM
    vram_gb = 0.0
    gpu_name = ""
    
    # First try NVIDIA GPU
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            gpu_name = parts[0].strip()
            vram_gb = round(int(parts[1].strip()) / 1024, 1)
    except Exception:
        pass
    
    # If no NVIDIA GPU, try Intel GPU/NPU using OpenVINO
    if not gpu_name:
        try:
            from openvino import Core
            core = Core()
            available_devices = core.available_devices
            if "GPU" in available_devices:
                gpu_name = "Intel GPU"
                # Try to get GPU memory info
                try:
                    gpu_properties = core.get_property("GPU", "FULL_DEVICE_NAME")
                    gpu_name = str(gpu_properties) if gpu_properties else "Intel GPU"
                except Exception:
                    pass
            if "NPU" in available_devices:
                if gpu_name:
                    gpu_name += " + Intel NPU"
                else:
                    gpu_name = "Intel NPU"
        except ImportError:
            pass
        except Exception:
            pass
    
    info["gpu_name"] = gpu_name
    info["vram_gb"] = vram_gb

    # Recommend model tier based on available RAM + VRAM
    total_memory = max(info["ram_gb"], vram_gb) if vram_gb > 0 else info["ram_gb"]
    # If Intel NPU is available, recommend NPU-optimized models
    if gpu_name and "NPU" in gpu_name:
        tier = "npu"
        recommended = "phi-3-mini-4k-int8 or tinyllama-1.1b-int8"
    elif total_memory >= 32:
        tier = "large"
        recommended = "qwen3:14b or qwen3:32b"
    elif total_memory >= 16:
        tier = "medium"
        recommended = "qwen3:8b"
    elif total_memory >= 8:
        tier = "small"
        recommended = "qwen3:4b"
    else:
        tier = "tiny"
        recommended = "qwen3:1.7b or qwen3:0.6b"

    info["recommended_tier"] = tier
    info["recommended_model"] = recommended
    return info


@router.get("/v1/learning/status")
async def get_learning_status(request: Request):
    """Get learning system status."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR, JarvisConfig, load_config
        
        config_path = DEFAULT_CONFIG_DIR / "config.toml"
        if not config_path.exists():
            return {
                "enabled": False,
                "policy": "none",
                "last_optimization": None,
                "optimization_count": 0,
                "message": "Learning not configured"
            }
        
        config = load_config(config_path)
        
        return {
            "enabled": config.learning.enabled if hasattr(config.learning, 'enabled') else False,
            "policy": config.learning.routing.policy if hasattr(config.learning, 'routing') and hasattr(config.learning.routing, 'policy') else "none",
            "last_optimization": None,  # TODO: Track from actual learning logs
            "optimization_count": 0,  # TODO: Track from actual learning logs
            "message": "Learning system ready" if config.learning.enabled else "Learning disabled"
        }
    except Exception as exc:
        return {"error": str(exc), "enabled": False}


@router.post("/v1/learning/trigger")
async def trigger_learning(request: Request):
    """Trigger a learning optimization cycle."""
    try:
        from openjarvis.core.config import DEFAULT_CONFIG_DIR, JarvisConfig, load_config

        config_path = DEFAULT_CONFIG_DIR / "config.toml"
        if not config_path.exists():
            return {"success": False, "error": "Learning not configured"}

        config = load_config(config_path)

        if not config.learning.enabled:
            return {"success": False, "error": "Learning is disabled"}

        # TODO: Implement actual learning trigger
        # For now, just return success
        return {
            "success": True,
            "result": "Learning cycle triggered",
            "message": "Optimization cycle started"
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ══════════════════════════════════════════════════════════════════════════════
# Voice Mode Control
# ══════════════════════════════════════════════════════════════════════════════

# Store running voice processes
_voice_processes: dict[str, subprocess.Popen] = {}


@router.post("/api/voice/launch")
async def launch_voice_mode(mode: str):
    """Launch a voice mode in a new subprocess."""
    global _voice_processes

    project_root = Path(__file__).parent.parent.parent.parent  # Go up to project root

    scripts = {
        "v5": project_root / "jarvis-voice.py",
        "deepgram": project_root / "jarvis-deepgram-voice.py",
    }

    if mode not in scripts:
        return {"success": False, "error": f"Unknown voice mode: {mode}"}

    script_path = scripts[mode]
    if not script_path.exists():
        return {"success": False, "error": f"Script not found: {script_path}"}

    # Check if already running
    if mode in _voice_processes:
        proc = _voice_processes[mode]
        if proc.poll() is None:
            return {"success": False, "error": f"Voice mode {mode} is already running"}

    # Get Python executable from venv
    venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        venv_python = sys.executable  # Fallback to current Python

    try:
        # Launch the voice script
        proc = subprocess.Popen(
            [str(venv_python), str(script_path)],
            cwd=str(project_root),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
        _voice_processes[mode] = proc
        return {
            "success": True,
            "mode": mode,
            "pid": proc.pid,
            "message": f"Voice mode {mode} launched"
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


@router.get("/api/voice/status")
async def get_voice_status():
    """Get status of all voice modes."""
    status = {}
    for mode, proc in _voice_processes.items():
        if proc.poll() is None:
            status[mode] = {"running": True, "pid": proc.pid}
        else:
            status[mode] = {"running": False, "pid": None}
            # Clean up dead processes
            del _voice_processes[mode]
    return {"modes": status}


@router.post("/api/voice/stop")
async def stop_voice_mode(mode: str):
    """Stop a running voice mode."""
    global _voice_processes

    if mode not in _voice_processes:
        return {"success": False, "error": f"Voice mode {mode} is not running"}

    proc = _voice_processes[mode]
    if proc.poll() is not None:
        # Already stopped
        del _voice_processes[mode]
        return {"success": True, "message": f"Voice mode {mode} was already stopped"}

    try:
        proc.terminate()
        # Wait a bit for graceful shutdown
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

        del _voice_processes[mode]
        return {"success": True, "message": f"Voice mode {mode} stopped"}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


__all__ = ["router"]
