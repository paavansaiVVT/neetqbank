"""
Model pricing lookup for Gemini API.

Prices are in USD per 1 million tokens.
Source: Google AI Studio pricing (Feb 2026).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Exchange rate — update periodically
USD_TO_INR = 86.50


@dataclass(frozen=True)
class ModelPricing:
    """Pricing per 1M tokens in USD."""
    input_per_million: float
    output_per_million: float


# Pricing table — USD per 1 million tokens
# Models listed: all models available in the QBank system
PRICING_TABLE: dict[str, ModelPricing] = {
    # Gemini 2.0 series
    "gemini-2.0-flash": ModelPricing(input_per_million=0.10, output_per_million=0.40),
    "gemini-2.0-flash-001": ModelPricing(input_per_million=0.10, output_per_million=0.40),
    "gemini-2.0-flash-lite": ModelPricing(input_per_million=0.075, output_per_million=0.30),

    # Gemini 2.5 series
    "gemini-2.5-flash": ModelPricing(input_per_million=0.30, output_per_million=2.50),
    "gemini-2.5-flash-lite": ModelPricing(input_per_million=0.15, output_per_million=0.60),
    "gemini-2.5-pro": ModelPricing(input_per_million=1.25, output_per_million=10.00),
    "gemini-2.5-pro-preview-05-06": ModelPricing(input_per_million=1.25, output_per_million=10.00),

    # Gemini 3 series (preview)
    "gemini-3-flash-preview": ModelPricing(input_per_million=0.50, output_per_million=3.00),
    "gemini-3-pro-preview": ModelPricing(input_per_million=2.00, output_per_million=12.00),

    # Legacy models (kept for backward compat)
    "gemini-1.5-pro": ModelPricing(input_per_million=1.25, output_per_million=5.00),
    "gemini-1.5-flash": ModelPricing(input_per_million=0.075, output_per_million=0.30),
}

# Fallback for unknown models — use a conservative mid-range estimate
_DEFAULT_PRICING = ModelPricing(input_per_million=0.50, output_per_million=3.00)


def get_model_pricing(model_name: str) -> ModelPricing:
    """Look up pricing for a model. Falls back to a safe default for unknown models."""
    # Try exact match first
    if model_name in PRICING_TABLE:
        return PRICING_TABLE[model_name]

    # Try prefix matching (e.g. "gemini-2.5-flash-preview-05-20" → "gemini-2.5-flash")
    for key in sorted(PRICING_TABLE.keys(), key=len, reverse=True):
        if model_name.startswith(key):
            return PRICING_TABLE[key]

    return _DEFAULT_PRICING


def calculate_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
) -> dict[str, float]:
    """
    Calculate cost for a generation run.
    
    Returns:
        Dict with input_cost, output_cost, total_cost (USD) and total_cost_inr.
    """
    pricing = get_model_pricing(model_name)
    input_cost = (input_tokens / 1_000_000) * pricing.input_per_million
    output_cost = (output_tokens / 1_000_000) * pricing.output_per_million
    total_cost = input_cost + output_cost

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(total_cost, 6),
        "total_cost_inr": round(total_cost * USD_TO_INR, 4),
    }


def usd_to_inr(usd: float) -> float:
    """Convert USD to INR."""
    return round(usd * USD_TO_INR, 4)
