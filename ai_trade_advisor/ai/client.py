from __future__ import annotations

import json
import re
from typing import Any

import requests

from ai_trade_advisor.config import AdvisorConfig


SYSTEM_PROMPT = """你是加密货币日内交易顾问，精通 SMC/ICT、流动性清洗与订单簿微观结构。
输入是结构化特征文本（非 K 线图）。请综合多维信号给出概率化建议。
只返回一个 JSON 对象，不要 markdown 代码块。"""


def call_llm(cfg: AdvisorConfig, user_prompt: str) -> str:
    if not cfg.ai_api_key:
        raise RuntimeError("未配置 AI_API_KEY / OPENAI_API_KEY")

    url = cfg.ai_api_base.rstrip("/") + "/chat/completions"
    payload = {
        "model": cfg.ai_model,
        "temperature": cfg.temperature,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {cfg.ai_api_key}",
        "Content-Type": "application/json",
    }
    resp = requests.post(url, json=payload, headers=headers, timeout=90)
    resp.raise_for_status()
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def parse_advice_json(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
