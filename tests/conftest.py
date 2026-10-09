"""Keep unit tests independent from a locally installed Ollama Python package."""
import sys
import types


try:
    import ollama  # noqa: F401
except ImportError:
    module = types.ModuleType("ollama")

    class UnavailableClient:
        def __init__(self, host: str):
            raise RuntimeError("Ollama is not installed in this test environment.")

    module.Client = UnavailableClient  # type: ignore[attr-defined]
    sys.modules["ollama"] = module
