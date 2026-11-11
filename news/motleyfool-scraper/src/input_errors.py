"""Bad input ends the run as SUCCEEDED with the reason, not as FAILED.

A FAILED run counts against the actor's success rate in the Store whether the
fault was ours or the caller's, and most FAILED runs on this portfolio were a
missing or malformed field. `raise input_error("...")` logs the reason, puts it
on the run as its final status message and exits with code 0 and no data, so
nothing is charged. Site-side failures (blocks, layout changes) still raise
ordinary exceptions and still fail the run, so real breakage stays visible.

`InputError` subclasses `SystemExit`: the Apify SDK (>= 4) keeps a SystemExit's
exit code, and `except Exception` blocks along the way do not swallow it.
"""

from apify import Actor


class InputError(SystemExit):
    def __init__(self, message: str) -> None:
        super().__init__(0)
        self.message = message

    def __str__(self) -> str:
        return self.message


def input_error(message: str) -> InputError:
    message = f"Input error: {message}"
    Actor.log.error(message)
    Actor.status_message = message
    return InputError(message)
