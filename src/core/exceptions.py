class BiotechAnalystError(Exception):
    """Base exception for all Biotech Analyst CLI errors."""
    pass


class ConfigError(BiotechAnalystError):
    """Raised when there is an issue loading or saving configurations."""
    pass


class ConfigNotFoundError(ConfigError):
    """Raised when the configuration file does not exist."""
    pass


class WorkspaceError(BiotechAnalystError):
    """Raised when folder operations or target setups fail."""
    pass


class PipelineError(BiotechAnalystError):
    """Raised when external data fetch or compilation pipeline stages fail."""
    pass
