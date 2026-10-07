"""Public roles mapped to the existing authentication schema."""

from enum import StrEnum


class Role(StrEnum):
    CLIENT = "EMPRESA_CLIENTE"
    STARTUP = "STARTUP"
    INVESTOR = "INVESTIDOR"


ROLE_NAMES = {Role.CLIENT: "CLIENT", Role.STARTUP: "STARTUP", Role.INVESTOR: "INVESTOR"}
REGISTRATION_ROLES = {name: role for role, name in ROLE_NAMES.items()}
