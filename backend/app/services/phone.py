import re

from app.core.errors import AppError

# A leading + is optional. Ten digits are treated as a US number. Spaces, dashes, dots, and parentheses are ignored.
_PHONE = re.compile(r"^[0-9]{10,15}$")
_SEPARATORS = re.compile(r"[\s().-]")


def normalize_phone(raw: str) -> str:
    digits = _SEPARATORS.sub("", raw.strip())
    if digits.startswith("+"):
        digits = digits[1:]
    elif len(digits) == 10:
        digits = f"1{digits}"
    if not _PHONE.fullmatch(digits):
        raise AppError(422, "invalid_phone", "Enter a phone number with 10 to 15 digits, such as +14155552671.")
    return f"+{digits}"
