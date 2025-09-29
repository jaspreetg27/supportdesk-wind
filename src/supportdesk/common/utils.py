"""Utility functions for validation and normalization."""

import re

from supportdesk.config import settings

# Slug validation pattern: alphanumeric + hyphens, no leading/trailing hyphens
SLUG_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# E.164 phone number pattern
PHONE_PATTERN = re.compile(r"^\+?[1-9]\d{1,14}$")


def normalize_slug(slug: str) -> str:
    """Normalize a slug to lowercase and validate format."""
    normalized = slug.strip().lower()
    return normalized


def validate_slug(slug: str) -> str:
    """Validate and normalize a slug."""
    normalized = normalize_slug(slug)

    if not normalized:
        raise ValueError("Slug cannot be empty")

    if len(normalized) < 3:
        raise ValueError("Slug must be at least 3 characters long")

    if len(normalized) > 50:
        raise ValueError("Slug must be at most 50 characters long")

    if not SLUG_PATTERN.match(normalized):
        raise ValueError(
            "Slug must contain only lowercase letters, numbers, and hyphens. "
            "Cannot start or end with a hyphen."
        )

    # Check against reserved slugs
    reserved_slugs = settings.reserved_slugs_set
    if normalized in reserved_slugs:
        raise ValueError(f"Slug '{normalized}' is reserved and cannot be used")

    return normalized


def validate_phone(phone: str) -> str:
    """Validate phone number in E.164 format."""
    if not phone:
        return phone

    phone = phone.strip()
    if not PHONE_PATTERN.match(phone):
        raise ValueError(
            "Phone number must be in E.164 format (e.g., +1234567890). "
            "Must start with + or digit, followed by 1-14 digits."
        )

    return phone


def get_reserved_slugs() -> set[str]:
    """Get the set of reserved slugs from configuration."""
    return settings.reserved_slugs_set
