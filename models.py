"""One small adapter per provider. Each takes the shared Request and returns a Result.

Adding a provider = one class with classify(req) and one entry in models.json.
"""
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from request import answer_schema

_LIMITS = json.loads((Path(__file__).parent / "guardrails.json").read_text(encoding="utf-8"))
MAX_OUTPUT_TOKENS = _LIMITS["max_output_tokens_per_email"]  # per-call ceiling; thinking counts toward it
TIMEOUT_SECONDS = 60                                         # per-call timeout


@dataclass
class Result:
    label: str                 # a category name, or "refused" / "truncated" / "error"
    confidence: float = None   # decision models report one; LLMs do not
    input_tokens: int = 0
    output_tokens: int = 0
    stop: str = ""


class FakeModel:
    """Keyword rules, no network. Used by the tests and to try the pipeline for free."""

    live = False
    RULES = [
        ("billing", r"invoice|refund|charge|billing|receipt|downgrade|cancel|seats|renewal|vat|currency"),
        ("customer_support", r"error|can't|cannot|not working|stopped|crash|how do i|fix|failed|missing"),
        ("partner_vendor", r"partner|agency|resell|recruit|our api|sponsor|portfolio|catalog|proposal"),
        ("new_lead", r"pricing|demo|trial|quote|plan|interested|evaluat"),
    ]

    def __init__(self, cfg):
        pass

    def classify(self, req):
        text = req.user.lower()
        for label, pattern in self.RULES:
            if re.search(pattern, text):
                return Result(label, stop="rule")
        return Result("not_crm", stop="default")


class BedrockClaude:
    """Claude on Amazon Bedrock through the Anthropic SDK's Mantle client.

    Auth comes from the normal AWS chain (AWS_PROFILE / SSO), region from cfg or AWS_REGION.
    """

    live = True

    def __init__(self, cfg):
        from anthropic import AnthropicBedrockMantle  # imported here so tests need no SDK

        self.model = cfg["model_id"]
        self.effort = cfg.get("effort", "low")
        region = cfg.get("region") or os.environ.get("AWS_REGION", "us-east-1")
        self.client = AnthropicBedrockMantle(aws_region=region, timeout=TIMEOUT_SECONDS, max_retries=2)

    def classify(self, req):
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": answer_schema(req.categories)},
            },
        )
        usage = dict(input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens)
        # No refusal fallback on purpose: a fallback would answer with a different model and
        # blur the comparison. A refusal is scored as a miss and counted separately.
        if resp.stop_reason == "refusal":
            return Result("refused", stop="refusal", **usage)
        if resp.stop_reason == "max_tokens":
            return Result("truncated", stop="max_tokens", **usage)
        text = next(b.text for b in resp.content if b.type == "text")
        return Result(json.loads(text)["category"], stop=resp.stop_reason, **usage)


class StrandsDecider:
    """Strands Decider 2B, an open-source decision model that runs on this machine.

    Calls the strands-decider CLI (pip install strands-decider). It picks one of the options and
    reports a confidence. Runs locally, so there is no token bill.
    """

    live = False
    CHOICE_LINE = re.compile(r"choice_0\s*->\s*(\S+)\s*\(confidence\s*([\d.]+)\)")

    def __init__(self, cfg):
        self.model = cfg["model_id"]

    def classify(self, req):
        state = f"{req.system}\n\nEmail:\n{req.user}"
        choice = f"{req.question}={','.join(req.categories)}"
        out = subprocess.run(
            ["strands-decider", "ask", self.model, "--state", state, "--choice", choice],
            capture_output=True, text=True, encoding="utf-8", timeout=TIMEOUT_SECONDS,
        )
        match = self.CHOICE_LINE.search(out.stdout)
        if out.returncode != 0 or not match:
            return Result("error", stop=(out.stderr or out.stdout)[-200:])
        return Result(match.group(1), confidence=float(match.group(2)), stop="decided")


class Jev:
    """TypeSafe Jev, a hosted decision model. Key from TYPESAFE_API_KEY.

    Not wired yet: the request shape needs TypeSafe's API docs, which come with the early-access key.
    """

    live = True

    def __init__(self, cfg):
        if not os.environ.get("TYPESAFE_API_KEY"):
            raise RuntimeError("Set TYPESAFE_API_KEY first")
        raise NotImplementedError("Jev adapter pending TypeSafe API docs")

    def classify(self, req):
        raise NotImplementedError


PROVIDERS = {"fake": FakeModel, "bedrock": BedrockClaude, "strands-decider": StrandsDecider, "jev": Jev}


def make_model(cfg):
    return PROVIDERS[cfg["provider"]](cfg)
