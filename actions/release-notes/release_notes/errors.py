class NotEligibleError(Exception):
    """The pull request cannot be rewritten, so it keeps the text release-please wrote."""


class RejectedNotesError(Exception):
    """The model returned notes that must not reach a release."""


class StalePullRequestError(Exception):
    """The pull request moved after the notes were written; a newer run owns it."""
