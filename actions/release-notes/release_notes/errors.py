class NotEligibleError(Exception):
    """The pull request cannot be rewritten, so it keeps the text release-please wrote."""


class InvalidNotesConfigurationError(Exception):
    """The notes configuration of the project cannot be used."""


class RejectedNotesError(Exception):
    """The model returned notes that must not reach a release."""


class StalePullRequestError(Exception):
    """The pull request moved after the notes were written; a newer run owns it."""
