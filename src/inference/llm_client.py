"""VN-HSGExam — Unified LLM Client v3 (4 models, free-tier only)"""
from __future__ import annotations
import json, re, time, os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional


MODELS = {
    "llama-3.1-8b":  {"provider": "cerebras", "api_id": "llama3.1-8b",   "type": "standard",  "rpm": 30},
    "qwen3-235b":    {"provider": "cerebras", "api_id": "qwen-3-235b-a22b-instruct-2507", "type": "reasoning", "rpm": 30},
    "gpt-oss-120b":  {"provider": "cerebras", "api_id": "gpt-oss-120b",  "type": "reasoning", "rpm": 30},
    "vistral-7b":    {"provider": "hf_local", "api_id": "Viet-Mistral/Vistral-7B-Chat", "type": "standard", "rpm": 1000},
}


@dataclass
class LLMResult:
    question_id: str
    model: str
    strategy: str
    prompt: str
    raw_output: str
    answer: Optional[str]
    answer_source: str
    tokens_in: int
    tokens_out: int
    reasoning_tokens: int
    latency_ms: float
    finish_reason: str
    attempts: int
    error: Optional[str]
    timestamp: float


class RateLimiter:
    def __init__(self):
        self._last_call = {}
    def wait(self, provider, rpm):
        if rpm >= 1000:
            return
        min_interval = 60.0 / rpm
        last = self._last_call.get(provider, 0)
        elapsed = time.time() - last
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_call[provider] = time.time()


# === Answer extraction ===
RE_DAPAN = re.compile(r"Đáp\s+án\s*[:\-]?\s*([ABCD])\b", re.IGNORECASE)
RE_FINAL_ANSWER = re.compile(r"(?:final\s+answer|answer)\s*[:\-]?\s*([ABCD])\b", re.IGNORECASE)
RE_LETTER_ONLY = re.compile(r"^\s*([ABCD])\s*[.):]?\s*$", re.MULTILINE)
RE_ANSWER = re.compile(r"\b([ABCD])\b")
RE_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text):
    return RE_THINK.sub("", text).strip()


def extract_answer(text):
    if not text:
        return None
    text = strip_think(text)
    # Priority 1: "Đáp án: X" — Vietnamese conclusion, last occurrence
    matches = list(RE_DAPAN.finditer(text))
    if matches:
        return matches[-1].group(1).upper()
    # Priority 2: English "Answer: X" / "Final answer: X"
    matches = list(RE_FINAL_ANSWER.finditer(text))
    if matches:
        return matches[-1].group(1).upper()
    # Priority 3: letter alone on a line
    m = RE_LETTER_ONLY.search(text)
    if m:
        return m.group(1)
    # Priority 4: last A/B/C/D in text
    matches = list(RE_ANSWER.finditer(text))
    if matches:
        return matches[-1].group(1)
    return None


def extract_content_or_reasoning(msg):
    content = (getattr(msg, "content", None) or "").strip()
    if content:
        return content, "content"
    reasoning = getattr(msg, "reasoning", None)
    if reasoning:
        return reasoning.strip(), "reasoning_only"
    return "", "empty"


# === Adapters ===
class CerebrasAdapter:
    def __init__(self, api_key):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url="https://api.cerebras.ai/v1")
    def call(self, model_id, prompt, max_tokens, temperature=0.0):
        t0 = time.time()
        resp = self.client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=temperature, timeout=60.0,
        )
        latency = (time.time() - t0) * 1000
        msg = resp.choices[0].message
        text, source = extract_content_or_reasoning(msg)
        usage = resp.usage
        rt = 0
        if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
            rt = getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0
        return {
            "text": text, "source": source,
            "tokens_in": usage.prompt_tokens, "tokens_out": usage.completion_tokens,
            "reasoning_tokens": rt, "latency_ms": latency,
            "finish_reason": resp.choices[0].finish_reason,
        }


class GroqAdapter:
    """Kept for fallback if needed."""
    def __init__(self, api_key):
        from groq import Groq
        self.client = Groq(api_key=api_key)
    def call(self, model_id, prompt, max_tokens, temperature=0.0):
        t0 = time.time()
        resp = self.client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens, temperature=temperature, timeout=60.0,
        )
        latency = (time.time() - t0) * 1000
        msg = resp.choices[0].message
        text, source = extract_content_or_reasoning(msg)
        usage = resp.usage
        rt = 0
        if hasattr(usage, "completion_tokens_details") and usage.completion_tokens_details:
            rt = getattr(usage.completion_tokens_details, "reasoning_tokens", 0) or 0
        return {
            "text": text, "source": source,
            "tokens_in": usage.prompt_tokens, "tokens_out": usage.completion_tokens,
            "reasoning_tokens": rt, "latency_ms": latency,
            "finish_reason": resp.choices[0].finish_reason,
        }


class HFLocalAdapter:
    """Vistral GGUF Q4 via llama.cpp CUDA. Fast inference on T4."""
    def __init__(self, gguf_repo="uonlp/Vistral-7B-Chat-gguf",
                 gguf_file="ggml-vistral-7B-chat-q4_1.gguf"):
        self.gguf_repo = gguf_repo
        self.gguf_file = gguf_file
        self.llm = None

    def _load(self, model_id=None):
        from huggingface_hub import hf_hub_download
        from llama_cpp import Llama
        print(f"[LlamaCpp] Loading {self.gguf_repo}/{self.gguf_file}...")
        gguf_path = hf_hub_download(repo_id=self.gguf_repo, filename=self.gguf_file)
        self.llm = Llama(
            model_path=gguf_path,
            n_gpu_layers=-1,
            n_ctx=4096,
            n_threads=4,
            verbose=False,
        )
        print(f"[LlamaCpp] Loaded with GPU offload.")

    def call(self, model_id, prompt, max_tokens, temperature=0.0):
        if self.llm is None:
            self._load()
        system_prompt = "Bạn là trợ lý AI tiếng Việt. Trả lời ngắn gọn và chính xác."
        t0 = time.time()
        output = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        latency = (time.time() - t0) * 1000
        text = output["choices"][0]["message"]["content"].strip()
        usage = output["usage"]
        return {
            "text": text, "source": "content",
            "tokens_in": usage["prompt_tokens"],
            "tokens_out": usage["completion_tokens"],
            "reasoning_tokens": 0,
            "latency_ms": latency,
            "finish_reason": output["choices"][0].get("finish_reason", "stop"),
        }

class UnifiedLLMClient:
    def __init__(self, keys, log_path):
        self.adapters = {}
        if "cerebras" in keys: self.adapters["cerebras"] = CerebrasAdapter(keys["cerebras"])
        if "groq" in keys: self.adapters["groq"] = GroqAdapter(keys["groq"])
        if keys.get("hf_local"): self.adapters["hf_local"] = HFLocalAdapter()
        self.limiter = RateLimiter()
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def already_done(self):
        done = set()
        if not self.log_path.exists():
            return done
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    done.add((r["question_id"], r["model"], r["strategy"]))
                except Exception:
                    continue
        return done

    def generate(self, question_id, model, strategy, prompt,
                 max_tokens=1024, max_retries=5, temperature=0.0):
        cfg = MODELS[model]
        provider = cfg["provider"]
        api_id = cfg["api_id"]
        if provider not in self.adapters:
            return self._fail(question_id, model, strategy, prompt, f"adapter {provider} not init")
        attempts = 0
        last_error = None
        for attempt in range(max_retries):
            attempts = attempt + 1
            self.limiter.wait(provider, cfg["rpm"])
            try:
                out = self.adapters[provider].call(api_id, prompt, max_tokens, temperature)
                answer = extract_answer(out["text"])
                source = out["source"]
                if answer is None and source != "empty":
                    source = "regex_fail"
                result = LLMResult(
                    question_id=question_id, model=model, strategy=strategy, prompt=prompt,
                    raw_output=out["text"], answer=answer, answer_source=source,
                    tokens_in=out["tokens_in"], tokens_out=out["tokens_out"],
                    reasoning_tokens=out["reasoning_tokens"],
                    latency_ms=out["latency_ms"], finish_reason=out["finish_reason"],
                    attempts=attempts, error=None, timestamp=time.time(),
                )
                self._flush(result)
                return result
            except Exception as e:
                last_error = str(e)
                wait = 2 ** attempt
                if attempt < max_retries - 1:
                    time.sleep(wait)
        return self._fail(question_id, model, strategy, prompt, last_error, attempts)

    def _fail(self, qid, model, strategy, prompt, err, attempts=0):
        result = LLMResult(
            question_id=qid, model=model, strategy=strategy, prompt=prompt,
            raw_output="", answer=None, answer_source="error",
            tokens_in=0, tokens_out=0, reasoning_tokens=0,
            latency_ms=0.0, finish_reason="error",
            attempts=attempts, error=err, timestamp=time.time(),
        )
        self._flush(result)
        return result

    def _flush(self, result):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")