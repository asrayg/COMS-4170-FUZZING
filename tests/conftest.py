"""Pytest fixtures + hook registration.

Importing fuzz.hooks registers all schemathesis hooks and custom checks
globally for the pytest session.
"""
from __future__ import annotations

import pytest

from fuzz import hooks  # noqa: F401 — imported for side effects (hook registration)
from fuzz.reporting import Reporter


@pytest.fixture(scope="session")
def gateway_reporter() -> Reporter:
    r = Reporter("gateway_findings")
    yield r
    r.flush()


@pytest.fixture(scope="session")
def differential_reporter() -> Reporter:
    r = Reporter("differential_findings")
    yield r
    r.flush()


@pytest.fixture(scope="session")
def stateful_reporter() -> Reporter:
    r = Reporter("stateful_findings")
    yield r
    r.flush()


@pytest.fixture(scope="session")
def negative_reporter() -> Reporter:
    r = Reporter("negative_findings")
    yield r
    r.flush()
