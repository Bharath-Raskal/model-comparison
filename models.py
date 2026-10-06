"""One small adapter per provider. Each takes the shared Request and returns a Result.

Adding a provider = one class with classify(req) and one entry in models.json.
"""
import json
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

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


def parse_label(text, categories):
    """The reply must be exactly one category name (case, quotes and a trailing period forgiven)."""
    cleaned = text.strip().strip("`'\".").strip().lower()
    return cleaned if cleaned in categories else f"invalid: {text.strip()[:300]}"


class BedrockClaude:
    """Claude on Amazon Bedrock through the Anthropic SDK's Bedrock client.

    Uses the classic bedrock-runtime endpoint with a cross-region inference profile id
    (us.anthropic...): the newer Mantle endpoint returned "model does not exist" in this account.
    Auth comes from the normal AWS chain (AWS_PROFILE / SSO), region from cfg or AWS_REGION.
    """

    live = True

    def __init__(self, cfg):
        from anthropic import AnthropicBedrock  # imported here so tests need no SDK

        self.model = cfg["model_id"]
        self.effort = cfg.get("effort", "low")
        region = cfg.get("region") or os.environ.get("AWS_REGION", "us-west-2")
        self.client = AnthropicBedrock(aws_region=region, timeout=TIMEOUT_SECONDS, max_retries=2)

    def classify(self, req):
        # Classic Bedrock rejects output_config.format, so the prompt asks for the bare category
        # name and anything else is scored as "not a category".
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=req.system,
            messages=[{"role": "user", "content": req.user}],
            output_config={"effort": self.effort},
        )
        usage = dict(input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens)
        # No refusal fallback on purpose: a fallback would answer with a different model and
        # blur the comparison. A refusal is scored as a miss and counted separately.
        if resp.stop_reason == "refusal":
            return Result("refused", stop="refusal", **usage)
        if resp.stop_reason == "max_tokens":
            return Result("truncated", stop="max_tokens", **usage)
        text = "".join(b.text for b in resp.content if b.type == "text")
        return Result(parse_label(text, req.categories), stop=resp.stop_reason, **usage)


class SystemOneModel:
    """A decision model behind TypeSafe's System One API (POST /v1/systemone).

    Gets the same information as the LLMs, each part in its own slot (docs.typesafe.ai/primitives/choice):
    the email is the state, the question is the instructions, and the categories with their
    descriptions are the Choice criteria. Stateless per call; no setup on the provider side.
    """

    live = True
    url = ""

    def __init__(self, cfg):
        self.model = cfg["model_id"]
        self.key = None
        self.timeout = cfg.get("timeout_s", TIMEOUT_SECONDS)  # a local model on a laptop CPU needs longer

    def classify(self, req):
        body = {
            "state": req.user,
            "model": self.model,
            "questions": {"category": {"type": "choice", "instructions": req.question, "criteria": req.criteria}},
        }
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        http_req = urllib.request.Request(self.url, data=json.dumps(body).encode("utf-8"), method="POST", headers=headers)
        with urllib.request.urlopen(http_req, timeout=self.timeout) as resp:
            data = json.load(resp)
        answer = data["answers"]["category"]
        usage = data.get("usage", {})
        return Result(answer["choice"], confidence=answer.get("confidence"),
                      input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
                      stop=data.get("model", ""))


class Jev(SystemOneModel):
    """TypeSafe Jev, hosted. Key from TYPESAFE_API_KEY (.env)."""

    url = "https://api.typesafe.ai/v1/systemone"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.key = os.environ.get("TYPESAFE_API_KEY")
        if not self.key:
            raise RuntimeError("Set TYPESAFE_API_KEY in .env first")


class StrandsDecider(SystemOneModel):
    """Strands Decider 2B, open source, served on this machine by `strands-decider serve`, which
    speaks the same System One API as Jev. Free per call; start the server first (README)."""

    live = False
    url = os.environ.get("DECIDER_URL", "http://127.0.0.1:8000/v1/systemone")


PROVIDERS = {"bedrock": BedrockClaude, "strands-decider": StrandsDecider, "jev": Jev}


def make_model(cfg):
    return PROVIDERS[cfg["provider"]](cfg)
