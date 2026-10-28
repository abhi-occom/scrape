"""Backward-compatible entry point: agent.executor and agent.routes both
import `translate` from here. The real implementation now lives in
agent/translators/ (Phase 2's pluggable Claude/Gemini/rule-based backends)
— this module just re-exports it so nothing else had to change when Phase 2
was added.
"""
from agent.translators import translate

__all__ = ['translate']
