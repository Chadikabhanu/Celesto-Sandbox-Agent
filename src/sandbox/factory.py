import os
import logging
from src.config import settings
from src.sandbox.celesto_adapter import CelestoProvider
from src.sandbox.exceptions import ProviderConfigurationError
from src.sandbox.fake_adapter import FakeCelestoProvider
from src.sandbox.interface import SandboxProvider

logger = logging.getLogger(__name__)


def get_sandbox_provider(provider_type: str | None = None) -> SandboxProvider:
    """Return configured sandbox provider lazily.

    Supports:
    - 'cloud': Celesto Cloud hosted microVMs
    - 'local': Celesto local hypervisor (KVM/QEMU)
    - 'fake' / 'mock': Deterministic in-memory test fake
    """
    raw_provider = (
        provider_type
        or os.environ.get("CELESTO_PROVIDER")
        or settings.CELESTO_PROVIDER
        or "mock"
    ).lower()

    if raw_provider in ("fake", "mock"):
        return FakeCelestoProvider()
    elif raw_provider == "cloud":
        return CelestoProvider(provider="cloud")
    elif raw_provider == "local":
        return CelestoProvider(provider="local")
    else:
        raise ProviderConfigurationError(
            f"Unsupported sandbox provider '{raw_provider}'. Supported values are 'cloud', 'local', 'mock'."
        )
