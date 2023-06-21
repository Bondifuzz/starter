from ..base.errors import SpecError


class AgentSpecError(SpecError):
    pass


class AgentSpecLoadError(AgentSpecError):
    pass


class AgentSpecValidationError(AgentSpecError):
    def __init__(self, msg: str) -> None:
        err = "Validation of agent specification failed"
        super().__init__(f"{err}. {msg}")


class AgentSpecParseError(AgentSpecError):
    def __init__(self, msg: str) -> None:
        err = "Failed to parse agent specification"
        super().__init__(f"{err}. {msg}")
