"""Prompt expansion and scene plan generation via configurable LLM provider.

Reads `config.yaml` → `llm.provider` to route to Anthropic, OpenAI, OpenRouter,
or Gemini. Accepts raw user input plus optional conversation history, extracts
what it can infer, and returns:
  - gaps: missing fields the agent should ask about (empty = no questions needed)
  - brief_fields: partial brief fields inferred from input
  - scene_plan: full scene_plan artifact (only when gaps is empty)
  - video_prompts: per-scene video generation prompts using the 5-aspect formula
  - confidence: per-field confidence scores
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Provider defaults — overridden by config.yaml llm.model when non-null
_PROVIDER_DEFAULTS: dict[str, str] = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-4o",
    "openrouter": "openai/gpt-4o",
    "gemini": "gemini-2.0-flash",
}

_BRIEF_FIELDS = ["purpose", "audience", "platform", "tone", "outcome", "constraints", "references"]

# Optional fields — never block generation if only these are missing
_OPTIONAL_FIELDS = {"references", "constraints"}

_SYSTEM_PROMPT = """\
You are a video production expert and creative director working inside OpenMontage,
an AI-orchestrated video production platform.

## Your Task

Analyze the user's input (and any prior conversation history) and return a JSON object
with these top-level keys:

```json
{
  "brief_fields": {
    "purpose": "...",       // why the video exists: educate|sell|inspire|document|entertain
    "audience": "...",      // who watches it
    "platform": "...",      // where it lives: youtube|instagram|tiktok|linkedin|generic
    "tone": "...",          // feel: serious|playful|cinematic|raw|warm|provocative
    "outcome": "...",       // what viewer should do/feel after
    "constraints": "...",   // budget, timeline, must-include (null if unspecified)
    "references": []        // video/image references mentioned (empty list if none)
  },
  "confidence": {
    "purpose": 0.9,         // 0.0-1.0 per field
    ...
  },
  "gaps": ["audience", "platform"],   // fields with confidence < 0.6, priority-ordered
  "scene_plan": null,       // populated ONLY when gaps is empty (see schema below)
  "video_prompts": []       // populated ONLY when gaps is empty (one entry per scene)
}
```

## When to set scene_plan

Set `scene_plan` and `video_prompts` only when `gaps` is empty (you have enough
information). Otherwise set both to null / [].

### scene_plan schema (abbreviated)

```json
{
  "version": "1.0",
  "style_playbook": null,
  "scenes": [
    {
      "id": "scene_01",
      "type": "generated",          // talking_head|broll|animation|generated|text_card|transition
      "description": "...",
      "start_seconds": 0,
      "end_seconds": 5,
      "shot_language": {
        "shot_size": "medium_close_up",
        "camera_movement": "dolly_in",
        "lighting_key": "natural",
        "depth_of_field": "shallow",
        "color_temperature": "warm"
      },
      "narrative_role": "hook",     // hook|establish_context|build_tension|climax|resolution|call_to_action etc.
      "required_assets": [
        {
          "type": "video_clip",
          "description": "...",
          "source": "generate"      // generate|source|provided|record
        }
      ]
    }
  ]
}
```

## Video Prompt Formula (5-aspect)

Each entry in `video_prompts` must fill all five slots:

```
[Subject]        type + key visual attributes
[Subject Motion] actions in temporal order; interactions
[Scene]          setting + time of day + scene dynamics
[Spatial]        shot size + position-in-frame + depth (FG/MG/BG)
[Camera]         speed → lens → height → angle → focus/DoF → steadiness → movement
```

Prompt length should match the target model sweet spot (~200–400 words for Seedance/Wan,
100–250 for Sora/VEO, ≤80 for LTX/Runway). Default to 200 words when model is unknown.

## Important Rules

- Extract only what the user actually said or clearly implied. Do NOT invent intent.
- Mark inferred fields in confidence (0.6–0.8 = inferred, 0.9–1.0 = explicitly stated).
- gaps must be ordered by priority: purpose > audience > platform > tone > outcome > constraints > references
- references and constraints are optional — never include them in gaps unless you have
  zero information and the user seems like they might have strong preferences.
- Return ONLY valid JSON. No markdown fences, no prose outside the JSON object.
"""


def _load_config() -> tuple[str, Optional[str], float, int]:
    """Return (provider, model_override, temperature, max_tokens) from config.yaml."""
    try:
        from lib.config_model import OpenMontageConfig
        cfg = OpenMontageConfig.load()
        return (
            cfg.llm.provider,
            cfg.llm.model,
            cfg.llm.temperature,
            cfg.llm.max_tokens,
        )
    except Exception:
        return ("anthropic", None, 0.7, 4096)


def _resolve_model(provider: str, model_override: Optional[str]) -> str:
    if model_override:
        return model_override
    return _PROVIDER_DEFAULTS.get(provider, "claude-sonnet-5")


class PromptExpansion(BaseTool):
    name = "prompt_expansion"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "prompt_expansion"
    provider = "llm_gateway"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set one of: ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, or GOOGLE_API_KEY "
        "matching the llm.provider in config.yaml."
    )
    agent_skills = ["video-gen-prompting"]

    capabilities = ["prompt_expansion", "scene_plan_generation", "brief_extraction"]
    supports = {
        "multi_turn_history": True,
        "gap_detection": True,
        "scene_plan_output": True,
        "video_prompt_output": True,
        "provider_configurable": True,
    }
    best_for = [
        "expanding vague user briefs into structured scene plans",
        "detecting what information is missing before starting production",
        "generating per-scene video prompts using the 5-aspect formula",
        "skipping multi-turn Q&A when the user provides a detailed professional prompt",
    ]
    not_good_for = ["offline generation", "image generation"]

    input_schema = {
        "type": "object",
        "required": ["raw_input"],
        "properties": {
            "raw_input": {
                "type": "string",
                "description": "The user's latest message describing the video they want.",
            },
            "conversation_history": {
                "type": "array",
                "description": "Prior turns as [{role: user|assistant, content: str}].",
                "items": {
                    "type": "object",
                    "required": ["role", "content"],
                    "properties": {
                        "role": {"type": "string", "enum": ["user", "assistant"]},
                        "content": {"type": "string"},
                    },
                },
                "default": [],
            },
            "pipeline_type": {
                "type": "string",
                "enum": ["cinematic", "explainer", "animation", "hybrid", "talking-head", "avatar-spokesperson"],
                "description": "Pipeline context — helps the LLM tailor scene types.",
            },
            "target_duration_seconds": {
                "type": "integer",
                "description": "Desired video length in seconds (optional hint).",
            },
            "style_hints": {
                "type": "object",
                "description": "Free-form style constraints already known (e.g. from a style playbook).",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "gaps": {"type": "array", "items": {"type": "string"}},
            "brief_fields": {"type": "object"},
            "confidence": {"type": "object"},
            "scene_plan": {"type": ["object", "null"]},
            "video_prompts": {"type": "array", "items": {"type": "string"}},
            "provider_used": {"type": "string"},
            "model_used": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout", "overloaded"])

    # ------------------------------------------------------------------ #

    def get_status(self) -> ToolStatus:
        provider, _, _, _ = _load_config()
        key_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "gemini": "GOOGLE_API_KEY",
        }
        env_key = key_map.get(provider)
        if env_key and os.environ.get(env_key):
            return ToolStatus.AVAILABLE
        # Fallback: any of the known keys is enough to attempt
        for k in key_map.values():
            if os.environ.get(k):
                return ToolStatus.DEGRADED
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # ~2k tokens input + ~1k output at typical rates
        provider, _, _, _ = _load_config()
        if provider == "anthropic":
            return 0.003  # claude-sonnet-5 ~$3/Mtok in, $15/Mtok out → ~$0.003
        if provider in ("openai", "openrouter"):
            return 0.005
        return 0.002

    # ------------------------------------------------------------------ #

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        provider, model_override, temperature, max_tokens = _load_config()
        model = _resolve_model(provider, model_override)

        raw_input: str = inputs["raw_input"]
        history: list[dict] = inputs.get("conversation_history") or []
        pipeline_type: str = inputs.get("pipeline_type", "")
        target_duration: int | None = inputs.get("target_duration_seconds")
        style_hints: dict = inputs.get("style_hints") or {}

        # Build the user message
        user_parts = [raw_input]
        if pipeline_type:
            user_parts.append(f"\n[Pipeline context: {pipeline_type}]")
        if target_duration:
            user_parts.append(f"\n[Target duration: {target_duration}s]")
        if style_hints:
            user_parts.append(f"\n[Style hints: {json.dumps(style_hints)}]")
        user_message = "".join(user_parts)

        messages = [*history, {"role": "user", "content": user_message}]

        try:
            raw_json = self._call_llm(provider, model, temperature, max_tokens, messages)
        except Exception as e:
            return ToolResult(success=False, error=f"LLM call failed ({provider}/{model}): {e}")

        try:
            result = json.loads(raw_json)
        except json.JSONDecodeError as e:
            return ToolResult(success=False, error=f"LLM returned invalid JSON: {e}\n\nRaw output:\n{raw_json[:500]}")

        gaps: list[str] = result.get("gaps", [])
        scene_plan = result.get("scene_plan")
        video_prompts: list[str] = result.get("video_prompts") or []

        # Validate scene_plan against schema when present
        if scene_plan:
            schema_error = self._validate_scene_plan(scene_plan)
            if schema_error:
                # Return with a warning but don't fail — agent can still use partial output
                result["scene_plan_validation_warning"] = schema_error

        return ToolResult(
            success=True,
            data={
                "gaps": gaps,
                "brief_fields": result.get("brief_fields", {}),
                "confidence": result.get("confidence", {}),
                "scene_plan": scene_plan,
                "video_prompts": video_prompts,
                "provider_used": provider,
                "model_used": model,
                "ready_for_production": len(gaps) == 0,
                **({"scene_plan_validation_warning": result["scene_plan_validation_warning"]}
                   if "scene_plan_validation_warning" in result else {}),
            },
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )

    # ------------------------------------------------------------------ #

    def _call_llm(
        self,
        provider: str,
        model: str,
        temperature: float,
        max_tokens: int,
        messages: list[dict],
    ) -> str:
        if provider == "anthropic":
            return self._call_anthropic(model, temperature, max_tokens, messages)
        if provider == "openai":
            return self._call_openai(model, temperature, max_tokens, messages, base_url=None)
        if provider == "openrouter":
            return self._call_openai(
                model, temperature, max_tokens, messages,
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            )
        if provider == "gemini":
            return self._call_gemini(model, temperature, max_tokens, messages)
        raise ValueError(f"Unsupported llm.provider: {provider!r}. Valid: anthropic, openai, openrouter, gemini")

    def _call_anthropic(self, model: str, temperature: float, max_tokens: int, messages: list[dict]) -> str:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        return response.content[0].text

    def _call_openai(
        self,
        model: str,
        temperature: float,
        max_tokens: int,
        messages: list[dict],
        base_url: Optional[str],
        api_key: Optional[str] = None,
    ) -> str:
        import openai
        kwargs: dict[str, Any] = {
            "api_key": api_key or os.environ.get("OPENAI_API_KEY", ""),
        }
        if base_url:
            kwargs["base_url"] = base_url
        client = openai.OpenAI(**kwargs)
        full_messages = [{"role": "system", "content": _SYSTEM_PROMPT}, *messages]
        response = client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    def _call_gemini(self, model: str, temperature: float, max_tokens: int, messages: list[dict]) -> str:
        import google.generativeai as genai
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        # Convert OpenAI-style message list to Gemini contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [msg["content"]]})
        response = gemini_model.generate_content(contents)
        return response.text

    def _validate_scene_plan(self, scene_plan: dict) -> Optional[str]:
        """Light validation — checks required top-level and per-scene fields."""
        if not isinstance(scene_plan, dict):
            return "scene_plan is not an object"
        if "scenes" not in scene_plan:
            return "scene_plan missing required field: scenes"
        scenes = scene_plan.get("scenes", [])
        if not isinstance(scenes, list) or len(scenes) == 0:
            return "scene_plan.scenes must be a non-empty array"
        required_scene_fields = {"id", "type", "description", "start_seconds", "end_seconds"}
        valid_types = {
            "talking_head", "broll", "animation", "character_scene",
            "diagram", "text_card", "transition", "generated", "screen_recording",
        }
        for i, scene in enumerate(scenes):
            missing = required_scene_fields - set(scene.keys())
            if missing:
                return f"scenes[{i}] missing fields: {sorted(missing)}"
            if scene.get("type") not in valid_types:
                return f"scenes[{i}].type {scene.get('type')!r} not in valid enum"
        return None
