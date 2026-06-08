"""Film crew exceptions."""


class GatePause(Exception):
    """Raised when a review gate asks the user to pause and review.

    Attributes:
        gate_name (str): the name of the gate that fired
        job_id (str): the job being processed
        manifest (dict): the current manifest at the moment of pause
        reason (str): human-readable guidance for what to review
    """

    def __init__(self, gate_name, job_id, manifest, reason=None):
        self.gate_name = gate_name
        self.job_id = job_id
        self.manifest = manifest
        self.reason = reason or f"Review gate '{gate_name}' fired for job {job_id}."
        super().__init__(self.reason)


class CrewFailure(Exception):
    """Raised when a crew member fails and the pipeline should abort cleanly."""

    def __init__(self, role, job_id, original_error, partial_manifest=None):
        self.role = role
        self.job_id = job_id
        self.original_error = original_error
        self.partial_manifest = partial_manifest or {}
        msg = f"[{role}] failed for job {job_id}: {original_error}"
        super().__init__(msg)
