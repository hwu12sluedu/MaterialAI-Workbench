"""Optional LLM adapter for natural-language simulation planning."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from material_ai_workbench.config import REPO_ROOT, WORKSPACE_ROOT


ENV_FILE = Path(
    os.environ.get(
        "MATERIALAI_ENV_FILE",
        str(REPO_ROOT / ".env" if (REPO_ROOT / "pyproject.toml").exists() else WORKSPACE_ROOT / ".env"),
    )
).expanduser()
LLM_PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "custom": {
        "label": "自定义 OpenAI-Compatible",
        "base_url": "",
        "model": "",
        "api_key_env": "MATERIALAI_LLM_API_KEY",
        "require_api_key": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "api_key_env": "OPENAI_API_KEY",
        "require_api_key": True,
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "require_api_key": True,
    },
    "qwen": {
        "label": "通义千问 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "api_key_env": "DASHSCOPE_API_KEY",
        "require_api_key": True,
    },
    "siliconflow": {
        "label": "SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "model": "Qwen/Qwen2.5-7B-Instruct",
        "api_key_env": "SILICONFLOW_API_KEY",
        "require_api_key": True,
    },
    "ollama": {
        "label": "本地 Ollama",
        "base_url": "http://localhost:11434/v1",
        "model": "qwen2.5:7b",
        "api_key_env": "OLLAMA_API_KEY",
        "require_api_key": False,
    },
}


def _load_dotenv_into_environ(path: Path = ENV_FILE) -> None:
    for key, value in read_env_file(path).items():
        os.environ.setdefault(key, value)


def read_env_file(path: Path = ENV_FILE) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def write_env_values(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.exists() else []
    remaining = dict(updates)
    lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines.append(f"{key}={_env_quote(remaining.pop(key))}")
        else:
            lines.append(line)
    for key, value in remaining.items():
        lines.append(f"{key}={_env_quote(value)}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def _env_quote(value: str) -> str:
    text = str(value)
    if not text or any(ch.isspace() for ch in text) or "#" in text:
        return json.dumps(text, ensure_ascii=False)
    return text


_load_dotenv_into_environ()

DEFAULT_LLM_BASE_URL = os.environ.get("MATERIALAI_LLM_BASE_URL", "")
DEFAULT_LLM_MODEL = os.environ.get("MATERIALAI_LLM_MODEL", "")
DEFAULT_LLM_API_KEY_ENV = os.environ.get("MATERIALAI_LLM_API_KEY_ENV", "MATERIALAI_LLM_API_KEY")

Transport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]


class LlmConfigError(RuntimeError):
    """Raised when an LLM request is not configured enough to run."""


class LlmResponseError(RuntimeError):
    """Raised when the LLM response cannot be converted into a task JSON."""


@dataclass
class LlmChatConfig:
    provider_name: str = "custom"
    base_url: str = field(default_factory=lambda: os.environ.get("MATERIALAI_LLM_BASE_URL", DEFAULT_LLM_BASE_URL))
    model: str = field(default_factory=lambda: os.environ.get("MATERIALAI_LLM_MODEL", DEFAULT_LLM_MODEL))
    api_key_env: str = field(default_factory=lambda: os.environ.get("MATERIALAI_LLM_API_KEY_ENV", DEFAULT_LLM_API_KEY_ENV))
    timeout_seconds: float = 60.0
    require_api_key: bool = True

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "") if self.api_key_env else ""

    def validate(self) -> None:
        if not self.base_url.strip():
            raise LlmConfigError("LLM base_url is empty. Set MATERIALAI_LLM_BASE_URL or enter it in the App.")
        if not self.model.strip():
            raise LlmConfigError("LLM model is empty. Set MATERIALAI_LLM_MODEL or enter it in the App.")
        if self.require_api_key and not self.api_key:
            raise LlmConfigError(f"LLM API key is missing. Set environment variable {self.api_key_env}.")

    def to_public_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["api_key_configured"] = bool(self.api_key)
        payload.pop("require_api_key", None)
        return payload


@dataclass
class LlmTaskPlan:
    config: dict[str, Any]
    raw_text: str
    task_payload: dict[str, Any]
    warnings: list[str]


@dataclass
class LlmConnectionTest:
    ok: bool
    message: str
    config: dict[str, Any]
    task_payload: dict[str, Any] | None = None
    raw_text: str | None = None


def provider_preset(provider_key: str) -> dict[str, Any]:
    return dict(LLM_PROVIDER_PRESETS.get(provider_key, LLM_PROVIDER_PRESETS["custom"]))


def llm_config_from_env(env_path: Path = ENV_FILE) -> LlmChatConfig:
    values = read_env_file(env_path)
    for key, value in values.items():
        os.environ[key] = value
    provider_name = values.get("MATERIALAI_LLM_PROVIDER", os.environ.get("MATERIALAI_LLM_PROVIDER", "custom"))
    require_value = values.get(
        "MATERIALAI_LLM_REQUIRE_API_KEY",
        os.environ.get("MATERIALAI_LLM_REQUIRE_API_KEY", "true"),
    ).strip().lower()
    return LlmChatConfig(
        provider_name=provider_name,
        base_url=values.get("MATERIALAI_LLM_BASE_URL", os.environ.get("MATERIALAI_LLM_BASE_URL", "")),
        model=values.get("MATERIALAI_LLM_MODEL", os.environ.get("MATERIALAI_LLM_MODEL", "")),
        api_key_env=values.get(
            "MATERIALAI_LLM_API_KEY_ENV",
            os.environ.get("MATERIALAI_LLM_API_KEY_ENV", "MATERIALAI_LLM_API_KEY"),
        ),
        require_api_key=require_value not in {"0", "false", "no", "off"},
    )


def apply_llm_config(config: LlmChatConfig, api_key_value: str | None = None) -> None:
    os.environ["MATERIALAI_LLM_PROVIDER"] = config.provider_name
    os.environ["MATERIALAI_LLM_BASE_URL"] = config.base_url.strip()
    os.environ["MATERIALAI_LLM_MODEL"] = config.model.strip()
    os.environ["MATERIALAI_LLM_API_KEY_ENV"] = config.api_key_env.strip()
    os.environ["MATERIALAI_LLM_REQUIRE_API_KEY"] = "true" if config.require_api_key else "false"
    if api_key_value and config.api_key_env:
        os.environ[config.api_key_env] = api_key_value.strip()


def save_llm_config(config: LlmChatConfig, api_key_value: str | None = None, env_path: Path = ENV_FILE) -> Path:
    apply_llm_config(config, api_key_value=api_key_value)
    updates = {
        "MATERIALAI_LLM_PROVIDER": config.provider_name,
        "MATERIALAI_LLM_BASE_URL": config.base_url.strip(),
        "MATERIALAI_LLM_MODEL": config.model.strip(),
        "MATERIALAI_LLM_API_KEY_ENV": config.api_key_env.strip(),
        "MATERIALAI_LLM_REQUIRE_API_KEY": "true" if config.require_api_key else "false",
    }
    if api_key_value and config.api_key_env:
        updates[config.api_key_env] = api_key_value.strip()
    write_env_values(env_path, updates)
    return env_path


def test_llm_connection(
    config: LlmChatConfig,
    *,
    api_key_value: str | None = None,
    transport: Transport | None = None,
) -> LlmConnectionTest:
    apply_llm_config(config, api_key_value=api_key_value)
    try:
        plan = plan_task_with_llm(
            "用 J2 金属材料，E=200000 MPa，nu=0.3，屈服 60 MPa，训练材料模型，不调用 Abaqus。",
            config,
            transport=transport,
        )
    except Exception as exc:
        return LlmConnectionTest(ok=False, message=str(exc), config=config.to_public_dict())
    return LlmConnectionTest(
        ok=True,
        message="LLM 已返回可解析的 MaterialAI 任务 JSON。",
        config=config.to_public_dict(),
        task_payload=plan.task_payload,
        raw_text=plan.raw_text,
    )


def plan_task_with_llm(prompt: str, config: LlmChatConfig, transport: Transport | None = None) -> LlmTaskPlan:
    """Call an OpenAI-compatible chat endpoint and parse a task JSON response."""

    config.validate()
    messages = [
        {
            "role": "system",
            "content": (
                "你是材料本构、Abaqus 和有限元仿真的任务规划器。"
                "只输出 JSON，不输出 Markdown。JSON 必须能被 Python json.loads 解析。"
            ),
        },
        {
            "role": "user",
            "content": _task_prompt(prompt),
        },
    ]
    body = {
        "model": config.model,
        "messages": messages,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    endpoint = config.base_url.rstrip("/") + "/chat/completions"
    response = (transport or _post_json)(endpoint, headers, body, float(config.timeout_seconds))
    raw_text = _extract_chat_text(response)
    task_payload = _extract_json_payload(raw_text)
    warnings = _payload_warnings(task_payload)
    return LlmTaskPlan(
        config=config.to_public_dict(),
        raw_text=raw_text,
        task_payload=task_payload,
        warnings=warnings,
    )


def _llm_available(config: LlmChatConfig | None = None) -> bool:
    cfg = config or LlmChatConfig()
    if not cfg.base_url.strip() or not cfg.model.strip():
        return False
    if cfg.require_api_key and not cfg.api_key:
        return False
    return True


def _chat_completion(
    system_prompt: str,
    user_prompt: str,
    *,
    config: LlmChatConfig | None = None,
    transport: Transport | None = None,
    json_response: bool = False,
) -> str:
    cfg = config or LlmChatConfig()
    cfg.validate()
    body: dict[str, Any] = {
        "model": cfg.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }
    if json_response:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"
    endpoint = cfg.base_url.rstrip("/") + "/chat/completions"
    response = (transport or _post_json)(endpoint, headers, body, float(cfg.timeout_seconds))
    return _extract_chat_text(response)


def interpret_report(
    report_text: str,
    report_type: str = "material_model",
    *,
    config: LlmChatConfig | None = None,
    transport: Transport | None = None,
) -> str | None:
    """Generate an optional LLM interpretation for a Workbench report."""

    cfg = config or LlmChatConfig()
    if not _llm_available(cfg):
        return None
    prompts = {
        "material_model": "你是材料力学专家。请用2-3段中文解释模型质量、屈服面拟合是否合理，以及下一步改进建议。",
        "surrogate": "你是机器学习与有限元交叉方向专家。请用2-3段中文解释代理模型精度、样本量是否足够，以及改进建议。",
        "closed_loop": "你是仿真验证工程师。请用2-3段中文总结闭环完整性、关键断点和下一步验证重点。",
        "batch": "你是实验设计专家。请用2-3段中文总结批量参数趋势、异常样本和下一步扫描范围。",
    }
    system_prompt = prompts.get(report_type, prompts["material_model"])
    user_prompt = "以下是报告原文，请基于内容分析，不要编造不存在的结果：\n\n" + report_text[:5000]
    return _chat_completion(system_prompt, user_prompt, config=cfg, transport=transport)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LlmResponseError(f"LLM HTTP {exc.code}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise LlmResponseError(f"LLM request failed: {exc}") from exc


def _extract_chat_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content.strip()
    if isinstance(response.get("content"), str):
        return str(response["content"]).strip()
    raise LlmResponseError("LLM response does not contain choices[0].message.content.")


def _extract_json_payload(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = json.loads(_balanced_json_object(stripped))
    if not isinstance(payload, dict):
        raise LlmResponseError("LLM JSON payload must be an object.")
    return payload


def _balanced_json_object(text: str) -> str:
    start = text.find("{")
    if start < 0:
        raise LlmResponseError("LLM response does not contain a JSON object.")
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise LlmResponseError("LLM response contains an incomplete JSON object.")


def _payload_warnings(payload: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    task_type = str(payload.get("task_type", "")).strip()
    required_sections: dict[str, tuple[str, ...]] = {
        "material_training": ("material", "ml"),
        "material_training_with_abaqus_check": ("material", "ml", "abaqus"),
        "composite_plate_hole": ("composite",),
        "batch_parameter_sweep": ("batch",),
        "case_library_query": ("query",),
        "surrogate_training": ("surrogate",),
        "odb_extraction": ("odb",),
        "closed_loop_report": (),
    }
    required = required_sections.get(task_type, ("material", "ml", "abaqus"))
    for key in required:
        if key not in payload:
            warnings.append(f"LLM JSON missing `{key}` section; defaults will be used.")
    return warnings


def _task_prompt(prompt: str) -> str:
    return f'''Convert this natural language simulation request into a MaterialAI Workbench executable task JSON.
Output ONLY JSON, no markdown.

Supported task_type values (choose the BEST match):
1. material_training - train ML constitutive model
2. material_training_with_abaqus_check - train + Abaqus UMAT unit verification
3. composite_plate_hole - micro RVE + 3D plate-with-hole Abaqus model
4. batch_parameter_sweep - parameter scan over yield strengths
5. case_library_query - search archived simulation cases
6. surrogate_training - train RF/MLP/GBR surrogate from dataset
7. odb_extraction - extract ODB field statistics
8. closed_loop_report - generate end-to-end validation report

For material_training / material_training_with_abaqus_check:
{{"task_type": "...", "steps": [{{"action": "train_material"}}],
 "material": {{"material_type": "j2|hill|barlat", "name": "...", "youngs_modulus": 200000,
   "poisson_ratio": 0.3, "yield_strength": 60, "hill_ratios": [1,1,1,1,1,1],
   "barlat_alphas": [1,1,1,1,1,1,1,1], "barlat_exponent": 8}},
 "ml": {{"c_value": 1.0, "gamma": 1.0, "n_load_cases": 40, "n_sequence": 4,
   "test_size": 80, "calculate_curves": false}},
 "abaqus": {{"run_check": false, "max_load_cases": 1, "timeout_seconds": 1200}},
 "missing": [], "warnings": []}}

For composite_plate_hole:
{{"task_type": "composite_plate_hole", "steps": [{{"action": "generate_rve"}}, {{"action": "run_pbc"}}, {{"action": "solve_plate"}}],
 "composite": {{"name": "...", "fiber_volume_fraction": 0.55, "fiber_e": 230000, "fiber_nu": 0.2,
   "matrix_e": 3500, "matrix_nu": 0.35, "interface_efficiency": 0.92, "hole_radius": 5.0,
   "length": 120, "width": 40, "thickness": 2, "run_abaqus": false, "submit_job": false}},
 "missing": [], "warnings": []}}

For batch_parameter_sweep:
{{"task_type": "batch_parameter_sweep", "steps": [{{"action": "create_sweep"}}],
 "batch": {{"name": "...", "material_type": "j2", "yield_strengths": [50,60,70,80,90]}},
 "missing": [], "warnings": []}}

For surrogate_training:
{{"task_type": "surrogate_training", "steps": [{{"action": "train_models"}}],
 "surrogate": {{"dataset_dir": "...", "target_column": "latest_odb_max_mises",
   "models": ["random_forest", "mlp", "gbr"]}},
 "missing": [], "warnings": []}}

Always include "steps" array, "missing" array, and "warnings" array.
If the platform does not support a requested capability, explain in warnings.

Request: {prompt}'''
