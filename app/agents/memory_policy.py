import re
from dataclasses import dataclass

MAX_MEMORY_VALUE_CHARS = 500

ATTRIBUTE_ALIASES = {
    "name": ("name", "profile"),
    "preferred name": ("preferred_name", "profile"),
    "language": ("preferred_language", "preference"),
    "preferred language": ("preferred_language", "preference"),
    "timezone": ("timezone", "profile"),
    "time zone": ("timezone", "profile"),
    "role": ("role", "work_context"),
    "department": ("department", "work_context"),
    "location": ("location", "profile"),
    "preference": ("preference", "preference"),
    "favorite color": ("favorite_color", "preference"),
}
MEMORY_LABELS = {
    key: attribute for attribute, (key, _memory_type) in ATTRIBUTE_ALIASES.items()
}
SENSITIVE_PATTERN = re.compile(
    r"\b(password|passcode|pin|otp|one[- ]time password|access token|"
    r"refresh token|api key|secret key|private key|credit card|debit card|"
    r"cvv|social security|ssn|aadhaar|aadhar|pan number)\b",
    re.IGNORECASE,
)
INSTRUCTION_PATTERN = re.compile(
    r"\b(ignore|override|bypass)\b.{0,40}\b(instruction|prompt|policy|rule)s?\b|"
    r"\b(system prompt|developer message|act as)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MemoryCommand:
    action: str
    key: str | None = None
    value: str | None = None
    memory_type: str | None = None
    error: str | None = None


def _normalize_attribute(attribute: str) -> tuple[str, str] | None:
    normalized = " ".join(attribute.casefold().strip().split())
    return ATTRIBUTE_ALIASES.get(normalized)


def normalize_recall_key(attribute: str) -> str | None:
    normalized = _normalize_attribute(attribute.rstrip("?.! "))
    return normalized[0] if normalized else None


def parse_memory_command(query: str) -> MemoryCommand | None:
    normalized = " ".join(query.strip().split())
    lowered = normalized.casefold().rstrip("?.!")

    if re.fullmatch(
        r"(?:what do you remember about me|list (?:my )?(?:saved )?memories)",
        lowered,
    ):
        return MemoryCommand("list")

    if re.fullmatch(
        r"(?:forget|delete|clear) (?:everything|all)(?: about me| my memories)?",
        lowered,
    ):
        return MemoryCommand("forget_all")

    forget_match = re.fullmatch(
        r"(?:forget|delete|remove) (?:about )?my (.+)",
        lowered,
    )
    if forget_match:
        resolved = _normalize_attribute(forget_match.group(1))
        if resolved is None:
            return MemoryCommand("reject", error="That memory type is not supported.")
        return MemoryCommand("forget", key=resolved[0], memory_type=resolved[1])

    store_match = re.fullmatch(
        r"(?:please )?remember (?:that )?my (.+?) (?:is|was) (.+)",
        normalized,
        re.IGNORECASE,
    )
    if store_match is None:
        store_match = re.fullmatch(
            r"(?:update|change) my (.+?) to (.+)",
            normalized,
            re.IGNORECASE,
        )
    if store_match:
        if SENSITIVE_PATTERN.search(normalized):
            return MemoryCommand(
                "reject",
                error="I cannot store sensitive credentials or identification data.",
            )
        if INSTRUCTION_PATTERN.search(store_match.group(2)):
            return MemoryCommand(
                "reject",
                error="I cannot store instructions as personal memory.",
            )
        resolved = _normalize_attribute(store_match.group(1))
        if resolved is None:
            return MemoryCommand("reject", error="That memory type is not supported.")
        value = store_match.group(2).strip().rstrip(".")
        if not value or len(value) > MAX_MEMORY_VALUE_CHARS:
            return MemoryCommand("reject", error="That memory value is invalid.")
        return MemoryCommand(
            "store",
            key=resolved[0],
            value=value,
            memory_type=resolved[1],
        )

    if re.match(
        r"^(?:please )?(?:remember|update|change|forget|delete|clear)\b", lowered
    ):
        return MemoryCommand("reject", error="That memory request is not supported.")
    return None
