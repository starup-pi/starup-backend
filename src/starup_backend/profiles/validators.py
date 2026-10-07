"""Brazilian document normalization, including alphanumeric CNPJ."""

import re

from django.core.exceptions import ValidationError


def normalize_document(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9./\- ]+", value):
        raise ValidationError("Documento inválido.")
    return re.sub(r"[./\- ]", "", value)


def validate_cpf(value: str) -> None:
    if not re.fullmatch(r"[0-9]{11}", value) or len(set(value)) == 1:
        raise ValidationError("CPF inválido.")
    digits = [int(char) for char in value]
    for size in (9, 10):
        result = sum(digits[index] * (size + 1 - index) for index in range(size))
        expected = (result * 10) % 11
        if digits[size] != (0 if expected == 10 else expected):
            raise ValidationError("CPF inválido.")


def validate_cnpj(value: str) -> None:
    if not re.fullmatch(r"[A-Z0-9]{12}[0-9]{2}", value) or len(set(value)) == 1:
        raise ValidationError("CNPJ inválido.")
    values = [ord(char) - 48 for char in value]
    for size, weights in (
        (12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
        (13, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]),
    ):
        remainder = sum(a * b for a, b in zip(values[:size], weights)) % 11
        expected = 0 if remainder < 2 else 11 - remainder
        if values[size] != expected:
            raise ValidationError("CNPJ inválido.")


def validate_document(value: str) -> None:
    if len(value) == 11:
        validate_cpf(value)
    else:
        validate_cnpj(value)
