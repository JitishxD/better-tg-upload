class CliError(Exception):
    """User-facing CLI error."""


class TransferError(CliError):
    """Error during file transfer."""


class MediaError(CliError):
    """Error processing media files."""


class AuthError(CliError):
    """Authentication/session error."""
