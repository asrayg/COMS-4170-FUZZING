"""Graylayer fuzzing harness.

Modules:
  config      – env + constants
  hooks       – schemathesis/hypothesis hooks (auth, rate limit, checks)
  reporting   – failure collection + summary tables/plots
  negatives   – hand-crafted malformed inputs for boundary testing
  differential – cross-endpoint invariants (e.g. bids < asks)
  stateful    – linked-operation flows
"""
__version__ = "1.0.0"
