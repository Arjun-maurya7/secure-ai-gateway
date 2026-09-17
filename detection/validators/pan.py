import re


PAN_VALIDATION_PATTERN = re.compile(
    r"^[A-Z]{3}[ABCFGHLJPT][A-Z][0-9]{4}[A-Z]$"
)


def is_valid_pan(pan: str) -> bool:
    return PAN_VALIDATION_PATTERN.fullmatch(pan) is not None