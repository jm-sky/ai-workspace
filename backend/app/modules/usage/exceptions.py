"""Usage metering exceptions."""


class UsageError(Exception):
    """Base usage error."""


class UsageLimitExceededError(UsageError):
    """Tenant exceeded included platform usage for the billing period."""

    def __init__(self, message: str = "Monthly AI usage limit exceeded", *, code: str = "usage_limit_exceeded"):
        super().__init__(message)
        self.code = code
