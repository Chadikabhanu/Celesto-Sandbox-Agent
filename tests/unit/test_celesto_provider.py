import pytest
from src.sandbox.celesto_adapter import CelestoProvider, CelestoSandbox
from src.sandbox.exceptions import ProviderConfigurationError
from src.sandbox.factory import get_sandbox_provider


def test_cloud_provider_missing_credentials(monkeypatch):
    """Celesto cloud provider produces a clear error when credentials are not supplied."""
    monkeypatch.delenv("CELESTO_API_KEY", raising=False)
    provider = CelestoProvider(provider="cloud")
    
    # Initialization is lazy, so creating the provider succeeds
    assert provider.provider_name == "celesto-cloud"

    # Creating sandbox without credentials raises clear ProviderConfigurationError
    sandbox = CelestoSandbox(
        sandbox_name="sbx-testcloud01",
        provider="cloud",
        api_key=None,
    )
    with pytest.raises(ProviderConfigurationError) as exc_info:
        sandbox._initialize_vm()
    assert "CELESTO_API_KEY environment variable is required" in str(exc_info.value)


def test_unsupported_provider_error(monkeypatch):
    """Unsupported provider names produce clear errors."""
    sandbox = CelestoSandbox(
        sandbox_name="sbx-testbad01",
        provider="invalid_hypervisor",
    )
    with pytest.raises(ProviderConfigurationError) as exc_info:
        sandbox._initialize_vm()
    assert "Unsupported CELESTO_PROVIDER" in str(exc_info.value)


def test_get_sandbox_provider_cloud(monkeypatch):
    """get_sandbox_provider correctly resolves 'cloud' provider."""
    monkeypatch.setenv("CELESTO_PROVIDER", "cloud")
    provider = get_sandbox_provider()
    assert provider.provider_name == "celesto-cloud"


def test_get_sandbox_provider_local(monkeypatch):
    """get_sandbox_provider correctly resolves 'local' provider."""
    monkeypatch.setenv("CELESTO_PROVIDER", "local")
    provider = get_sandbox_provider()
    assert provider.provider_name == "celesto-local"
