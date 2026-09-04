class AgentNotConfiguredError(Exception):
    """Raised when no runtime Agent provider has been configured."""


class AgentServiceError(Exception):
    """Raised for controlled failures from a configured Agent provider."""


def chat(message, conversation_id=None):
    """Provider-agnostic Agent boundary reserved for a future implementation."""
    raise AgentNotConfiguredError
