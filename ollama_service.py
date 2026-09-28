import json
import urllib.request
from typing import Callable, Generator


class OllamaService:
    """Ollama API client with lazy model management and streaming."""

    STRICT_SUFFIX = (
        "\n\nSTRICT FORMATTING DIRECTIVE:\n"
        "Return ONLY the final requested output. DO NOT include any conversational filler, greetings, confirmations "
        "('Okay', 'Sure', 'Here is', 'I will do that', 'Let me prepare'), introductory headers, extra suggestions, or closing remarks. "
        "Do not output <think> tags or reasoning steps."
    )

    # ── action prompt definitions ──────────────────────────────
    _ACTIONS = {
        "rewrite": (
            "You are a GRAMMAR REWRITE ENGINE — NOT a Q&A assistant.\n"
            "CRITICAL: The user text below is ALREADY THE ANSWER (a rough draft). Your ONLY job is to POLISH that exact text into proper sentences. DO NOT generate a new answer, DO NOT explain, DO NOT summarize the question.\n"
            "MODE: TEXT-TO-TEXT POLISHING (like Grammarly), NOT QUESTION-ANSWERING.\n"
            "TASK: Take the draft answer and fix grammar, spelling, punctuation, sentence structure, and flow while PRESERVING original meaning 100%.\n"
            "ANTI-PATTERNS (FORBIDDEN):\n"
            "- If draft is 'i go market yesterday shop close' -> CORRECT: 'I went to the market yesterday, but the shop was closed.' WRONG: 'The market is a place where... Here is information about markets...'\n"
            "- NEVER add new facts, never answer the underlying question, never add 'Here is the rewritten text:'\n"
            "RULES:\n"
            "- Fix grammar, punctuation, spelling, sentence structure, and flow ONLY\n"
            "- Keep same language as input\n"
            "- Keep all facts and intent identical — only language is fixed\n"
            "- If draft is already correct, return it with minimal edits\n"
            "- Output ONLY the final polished sentences — no preamble, no explanation\n"
            "FEW-SHOT:\n"
            "Input draft: 'me very tired today because work lot and no sleep'\n"
            "Output: 'I am very tired today because I worked a lot and did not get enough sleep.'\n"
            "Input draft: 'this product good but price high not worth buying if you have low budget'\n"
            "Output: 'This product is good, but its price is high. It may not be worth buying if you have a low budget.'"
        ),
        "enhance": (
            "Enhance and expand the following text with richer vocabulary, better structure, and more detail. "
            "Preserve the core idea but make it professional and compelling."
        ),
        "plan": (
            "You are an expert planner and solution architect. Your task is to take ANY objective/context and produce a COMPLETE DETAILED PLAN plus EXECUTABLE SCRIPT LOGIC.\n"
            "You MUST output TWO mandatory parts:\n\n"
            "=== PART 1: COMPLETE DETAILED PLAN (Markdown) ===\n"
            "Include: Objective restatement, Scope & Assumptions, Deliverables, Step-by-step phases with priorities (P0/P1/P2), Milestones & Timeline, Required resources/tools, Risks & Mitigations, Acceptance Criteria/Definition of Done, and Next Actions.\n"
            "Be thorough - no high-level vague steps. Each step must have: what to do, why, how, owner/role, and expected output.\n\n"
            "=== PART 2: SCRIPT LOGIC as AI-Agent Understandable Method ===\n"
            "Convert ALL scripts/code into AI-agent executable logic. Provide BOTH:\n"
            "A) Markdown Logic File (like `logic.md`): Pseudocode / workflow steps / file structure / execution order that any AI agent can follow without ambiguity.\n"
            "B) JSON Logic File (like `logic.json`): A structured JSON with { \"workflow\": [ { \"step\": 1, \"action\": \"...\", \"input\": \"...\", \"output\": \"...\", \"tool\": \"...\", \"depends_on\": [] } ], \"files\": [], \"env\": {} } format that an AI agent can parse and execute.\n"
            "Rules for PART 2:\n"
            "- NEVER output raw standalone code without its logic explanation; always wrap script as logic steps\n"
            "- If code is needed, provide it INSIDE the logic structure as `code_block` field in JSON and as fenced code inside Markdown, but the primary is the LOGIC METHOD\n"
            "- Ensure any non-technical agent can understand the execution method from your md+json alone\n"
            "- Keep JSON valid and Markdown well-structured with headings"
        ),
        "explain": (
            "You are a concise tutor. Explain the meaning, concept, or logic of the provided text clearly "
            "with simple terms and concise examples."
        ),
        "translate": (
            "Translate the provided text accurately. Preserve nuance and tone."
        ),
        "summarize": (
            "Summarize the key points of the provided text into clear, concise bullet points."
        ),
        "details": (
            "Provide detailed information, additional context, or deeper analysis on the provided topic."
        ),
        "writing_assist": (
            "You are a WRITING ASSISTANT — Grammarly-style inline helper.\n"
            "TASK: Fix grammar, spelling, punctuation, improve sentence clarity and fluency. Keep meaning identical. Output SHORT result — the improved sentence(s) only.\n"
            "RULES:\n"
            "- Correct grammar/spelling/punctuation\n"
            "- Improve flow and word choice but keep it concise — no expansion, no extra details\n"
            "- Preserve original intent and tone\n"
            "- Output ONLY the improved short sentence(s) — no explanation, no preamble\n"
            "- If already correct, return as-is\n"
            "FEW-SHOT:\n"
            "Input: 'pleases fidn the attached mail for your ref'\n"
            "Output: 'Please find the attached mail for your reference.'\n"
            "Input: 'i am write code for make website but not working'\n"
            "Output: 'I am writing code for a website, but it is not working.'"
        ),
    }

    def __init__(self, base_url: str = "http://localhost:11434",
                 default_model: str = "lfm2.5:ela",
                 keep_alive: str = "2m"):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.keep_alive = keep_alive
        self._selected_model = None
        self._resolve_model()

    # Cloud-only / remote models are advertised as installed but cannot run
    # locally via /api/generate — they return Template: N/A and produce no
    # results.  We exclude them so get_available_models() only returns models
    # that actually work with the local Ollama server.
    _CLOUD_MODEL_MARKERS = (":cloud", ":remote", "-cloud", "-remote")

    @classmethod
    def _is_cloud_model(cls, model_name: str) -> bool:
        """Return True for cloud-only models that are not locally runnable."""
        lower = model_name.lower()
        if any(marker in lower for marker in cls._CLOUD_MODEL_MARKERS):
            return True
        # Cloud models typically have no template / return Template: N/A
        # We also detect them at the /api/show level in get_available_models.
        return False

    def get_available_models(self) -> list[str]:
        """Fetch list of installed *local* models from Ollama.

        Cloud-only models (e.g. ``nemotron-3-ultra:cloud``) are excluded because
        they cannot be used via the local ``/api/generate`` endpoint — they have
        no Modelfile template and produce no results.
        """
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/tags",
                headers={"Content-Type": "application/json"},
                method="GET"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                raw_models = [m.get("name") for m in data if isinstance(m, dict)]
            elif isinstance(data, dict):
                raw_models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
            else:
                raw_models = []

            # Filter: remove embed models, cloud/remote models, and any model
            # whose /api/show reports no template (Template: N/A == not local).
            local_models = []
            for name in raw_models:
                if not name:
                    continue
                if "embed" in name.lower() or "bge" in name.lower():
                    continue
                if self._is_cloud_model(name):
                    continue
                # Verify the model has a usable local template via /api/show
                if self._has_local_template(name):
                    local_models.append(name)
                else:
                    # /api/show returned no template — likely a cloud/remote model
                    # that slipped through.  Exclude it to prevent "no results".
                    continue
            return local_models
        except Exception:
            pass
        return []

    def _has_local_template(self, model_name: str) -> bool:
        """Check whether *model_name* has a real Modelfile template (i.e. is a local model)."""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/show",
                data=json.dumps({"name": model_name}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                info = json.loads(resp.read().decode("utf-8"))
            template = info.get("template") or info.get("modelfile", "")
            # If template is missing/empty/N/A, the model is not a local GGUF model
            if not template or template.strip() in ("N/A", ""):
                return False
            return True
        except Exception:
            # If /api/show fails, be conservative: assume it's usable (don't
            # exclude by default, let the generation path report the error).
            return True

    def _resolve_model(self):
        """Ensure default_model exists in Ollama; fallback to an available model if not."""
        available = self.get_available_models()
        if not available:
            self._selected_model = self.default_model
            return

        # Check exact or prefix match
        if any(m == self.default_model or m.startswith(self.default_model.split(":")[0]) for m in available):
            self._selected_model = self.default_model
        else:
            # Fallback to first non-embed, non-cloud model (already filtered above)
            valid = [m for m in available if "embed" not in m.lower() and "bge" not in m.lower()]
            fallback = valid[0] if valid else available[0]
            print(f"Configurable model '{self.default_model}' not found in Ollama. Falling back to '{fallback}'.")
            self.default_model = fallback
            self._selected_model = fallback

    def ensure_model_loaded(self, model_name: str | None = None):
        """Set active model name (Ollama loads lazily on request)."""
        if not model_name:
            model_name = self.default_model
        self._selected_model = model_name

    def stream_generate(self, prompt: str, system_prompt: str = "",
                        model: str | None = None, temperature: float | None = None,
                        max_tokens: int | None = None) -> Generator[str, None, None]:
        """Stream a chat-style generation from Ollama. Yields response chunks.

        IMPORTANT: Many local Ollama models (e.g. spark, phi, lfm2.5 variants) ship
        with a Modelfile whose ``TEMPLATE`` is just ``{{ .Prompt }}`` — meaning the
        ``system`` field is **never injected** into the model's input.  To guarantee
        that our system instructions (rewrite-only, short-output, etc.) are actually
        seen by the model, we **prepend** the system prompt to the user prompt and
        also pass it via the ``system`` field (which works for well-behaved models).
        """
        selected_model = model or self.default_model
        self.ensure_model_loaded(selected_model)

        # Use deterministic low temperature for rewrite/writing_assist to avoid creative answering
        if temperature is None:
            # Auto-detect rewrite/writing modes by system prompt marker
            if "GRAMMAR REWRITE ENGINE" in system_prompt or "TEXT-TO-TEXT POLISHING" in system_prompt or "WRITING ASSISTANT" in system_prompt:
                temperature = 0.2
            elif "SHORT RESULT" in system_prompt:
                temperature = 0.3
            else:
                temperature = 0.6

        # ─────────────────────────────────────────────────────────────
        # FIX: Prepend system prompt to the prompt itself.
        # Many locally-pulled models have TEMPLATE {{ .Prompt }} which
        # ignores the 'system' parameter entirely.  By embedding the
        # instructions directly in the prompt we guarantee the model
        # receives them — this is what fixes "long answers" (system
        # prompt was being silently dropped) and "no results" for
        # models that don't know how to handle a bare prompt.
        # ─────────────────────────────────────────────────────────────
        if system_prompt:
            full_prompt = system_prompt + "\n\n" + prompt
        else:
            full_prompt = prompt

        # Determine a sensible max_tokens to prevent runaway long answers.
        # Rewrite/writing_assist should be very short; explain/summarize
        # moderate; everything else a reasonable cap.
        if max_tokens is None:
            if "GRAMMAR REWRITE ENGINE" in system_prompt or "TEXT-TO-TEXT POLISHING" in system_prompt or "WRITING ASSISTANT" in system_prompt or "SHORT RESULT" in system_prompt:
                max_tokens = 120          # short polish / fixing
            elif "PART 1" in system_prompt or "PART 2" in system_prompt:
                max_tokens = 2048         # plan mode needs full detail
            else:
                max_tokens = 256          # explain/summarize/translate/etc.

        payload = {
            "model": selected_model,
            "prompt": full_prompt,
            "system": system_prompt,   # still sent for well-behaved models
            "stream": True,
            "keep_alive": self.keep_alive,
            "think": False,            # disable thinking blocks — they bloat output and cause "long answers"
            "options": {
                "temperature": temperature,
                "top_p": 0.9 if temperature > 0.3 else 0.85,
                "repeat_penalty": 1.05,
                "num_predict": max_tokens,
            }
        }

        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                for line in response:
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    resp_text = chunk.get("response", "")
                    if resp_text:
                        yield resp_text
                    if chunk.get("done", False):
                        break
        except Exception as e:
            yield f"\n[Error connecting to Ollama: {str(e)}. Ensure 'ollama serve' is running and model '{selected_model}' is available. Note: cloud-only models (e.g. '*:cloud') cannot be used via local /api/generate.]"

    def get_action_prompt(self, action_type: str, text: str, target_lang: str = "Tamil") -> tuple[str, str]:
        """Return (system_prompt, user_text) for the given action."""
        if action_type == "translate":
            sys_prompt = (
                f"Translate the following text accurately into natural {target_lang}. "
                "Preserve nuance and tone." + self.STRICT_SUFFIX
            )
        elif action_type in ("expand", "enhance"):
            sys_prompt = (
                "Enhance and expand the following text with richer vocabulary, better structure, and more detail. "
                "Preserve the core idea but make it professional and compelling." + self.STRICT_SUFFIX
            )
        elif action_type == "rewrite":
            # Rewrite mode: user gives rough answer text, we return proper sentences only — STRICT TEXT-TO-TEXT
            sys_prompt = (
                self._ACTIONS["rewrite"] + self.STRICT_SUFFIX + (
                    "\n\nOVERRIDE: Ignore any other instruction about answering questions. You are ONLY a rewrite engine for this request."
                    "\nOUTPUT FORMAT: Return ONLY the polished sentences. No intro, no explanation, no 'Rewritten version:' header, no quotes."
                    "\nIf you add any explanation or new answer, you have FAILED the task."
                )
            )
            # Explicitly mark input as DRAFT ANSWER — not a question to answer
            text = (
                "DRAFT ANSWER TO POLISH (do NOT answer, only fix grammar/sentences):\n"
                "<<<DRAFT_START>>>\n"
                f"{text}\n"
                "<<<DRAFT_END>>>\n"
                "Instruction: Output ONLY the polished version of the text between DRAFT_START/END."
            )
            return sys_prompt, text
        elif action_type == "plan":
            # Plan mode: complete detailed plan + script as md/json logic for AI agent
            sys_prompt = self._ACTIONS["plan"] + self.STRICT_SUFFIX + (
                "\n\nOUTPUT FORMAT (MANDATORY - follow exactly):\n"
                "# PART 1: COMPLETE DETAILED PLAN\n"
                "## 1. Objective & Scope\n## 2. Deliverables\n## 3. Step-by-Step Plan (Phased, with P0/P1/P2)\n"
                "## 4. Milestones & Timeline\n## 5. Resources & Dependencies\n## 6. Risks & Mitigations\n## 7. Acceptance Criteria\n\n"
                "# PART 2: SCRIPT LOGIC - AI Agent Method\n"
                "## logic.md (Workflow in Markdown)\n```markdown\n[workflow steps + file tree + execution order]\n```\n"
                "## logic.json (Executable Workflow)\n```json\n{ \"workflow\": [...], \"files\": [...], \"env\": {} }\n```\n"
                "Do not skip PART 2. If no code is needed, still provide logic.json with workflow steps the agent can follow."
            )
            text = f"Objective/Context to plan:\n\"\"\"\n{text}\n\"\"\"\n\nGenerate the Complete Detailed Plan + Script Logic (md + json) now."
            return sys_prompt, text
        elif action_type == "writing_assist":
            # Writing assistance: short grammar fix / improved sentence, no thinking
            sys_prompt = (
                self._ACTIONS["writing_assist"] + self.STRICT_SUFFIX + (
                    "\n\nSHORT RESULT DIRECTIVE: Output ONLY 1-2 lines — the improved sentence(s). No explanation, no definition, no thinking.\n"
                    "OVERRIDE: Ignore plan/code formatting; this is concise writing fix only."
                )
            )
            text = (
                "TEXT TO FIX (grammar + improve, short result):\n"
                "<<<TEXT_START>>>\n"
                f"{text}\n"
                "<<<TEXT_END>>>\n"
                "Output ONLY the corrected short version."
            )
            return sys_prompt, text
        else:
            base_p = self._ACTIONS.get(action_type, "You are a helpful and concise Windows desktop assistant.")
            # Default: short result + no think (except plan/code/summarize handled above)
            # Writing-assistance style for generic prompts: concise improved sentence if input is sentence-like
            if action_type in ("rewrite", "writing_assist"):
                sys_prompt = base_p + self.STRICT_SUFFIX
            elif action_type in ("plan",):
                sys_prompt = base_p + self.STRICT_SUFFIX  # plan keeps full detail (exception)
            elif "Code Only" in base_p or action_type in ("summarize",):
                sys_prompt = base_p + self.STRICT_SUFFIX  # code/summarize are exceptions — keep their format
            else:
                # Generic ask: short result, no thinking
                sys_prompt = base_p + self.STRICT_SUFFIX + "\n\nSHORT RESULT: Keep answer concise (1-4 lines) if input is a sentence to correct; otherwise direct answer only."
            return sys_prompt, text

    def get_model_name(self) -> str:
        return self._selected_model or self.default_model

    def set_model(self, model_name: str):
        """Dynamically switch active model."""
        if model_name:
            self.default_model = model_name
            self._selected_model = model_name