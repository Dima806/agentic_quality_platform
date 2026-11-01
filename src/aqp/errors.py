"""Exception hierarchy for the platform."""

from __future__ import annotations


class AQPError(Exception):
    """Base class for all platform errors."""


class FeatureValidationError(AQPError):
    """A ``.feature`` file is missing or is not valid Gherkin."""


class ConfigurationError(AQPError):
    """The configuration is incomplete (e.g. the API key is not set)."""


class BrowserError(AQPError):
    """A browser tool call failed in a way the run cannot recover from."""


class InfrastructureError(AQPError):
    """The environment is broken (e.g. the browser won't start).

    A step that hits this is marked ``blocked``, not ``failed`` — the app was
    never actually exercised. See the failure-class table in the PRD (§6).
    """
