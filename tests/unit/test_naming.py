import re
import pytest
from src.sandbox.naming import SANDBOX_NAME_PATTERN, generate_sandbox_name, is_valid_sandbox_name


def test_generate_sandbox_name_format():
    """Generated sandbox names must strictly match ^sbx-[a-z0-9]{8,}$."""
    regex = re.compile(SANDBOX_NAME_PATTERN)
    for _ in range(50):
        name = generate_sandbox_name()
        assert regex.match(name), f"Name '{name}' does not match pattern {SANDBOX_NAME_PATTERN}"
        assert is_valid_sandbox_name(name)


def test_generate_sandbox_name_uniqueness():
    """Generated sandbox names must be distinct."""
    names = {generate_sandbox_name() for _ in range(100)}
    assert len(names) == 100


@pytest.mark.parametrize(
    "valid_name",
    [
        "sbx-12345678",
        "sbx-abcdef012345",
        "sbx-a1b2c3d4e5f6",
        "sbx-seeddemo1",
    ],
)
def test_valid_sandbox_names(valid_name):
    assert is_valid_sandbox_name(valid_name) is True


@pytest.mark.parametrize(
    "invalid_name",
    [
        "sbx-123",              # Too short (< 8 chars)
        "sbx-UPPERCASE1",       # Uppercase characters
        "sandbox-12345678",     # Bad prefix
        "sbx-invalid_underscore", # Underscore not allowed
        "sbx-with-dash",        # Dash not allowed after prefix
        "",                     # Empty
        None,                   # None
    ],
)
def test_invalid_sandbox_names(invalid_name):
    assert is_valid_sandbox_name(invalid_name) is False
