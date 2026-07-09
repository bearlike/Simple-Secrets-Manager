"""ssm-reload: recreate containers when SSM config secrets change.

Externally isolated service. It depends ONLY on the SSM public HTTP API
and a local container runtime (Docker in v1). It never imports the SSM
backend (``ssm_server.api``/``ssm_server.engines``/``ssm_server.access``),
never touches Mongo, and keeps no durable state of its own: everything it
needs lives on the SSM API and on the managed containers' labels.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
