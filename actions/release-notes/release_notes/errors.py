class NotEligibleError(Exception):
    """The notes cannot be written for this release, so it keeps the text release-please writes."""


class NotesUnchangedError(Exception):
    """The open release pull request already carries the notes of these commits."""

    def __init__(self, pull_request: dict) -> None:
        super().__init__(f"#{pull_request['number']} already carries these notes")
        self.pull_request = pull_request


class InvalidNotesConfigurationError(Exception):
    """The notes configuration of the project cannot be used."""


class RejectedNotesError(Exception):
    """The model returned notes that must not reach a release."""
