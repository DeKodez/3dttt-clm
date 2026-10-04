"""Agent registry — resolves names to constructors."""

from arena.agents.base import Agent
from arena.agents.baselines import RandomAgent, TacticalAgent
from arena.agents.clm_agent import CLMAgent
from arena.agents.jev_agent import JevAgent

AGENT_CLASSES = {
    "random": RandomAgent,
    "tactical": TacticalAgent,
    "jev": JevAgent,
    "clm": CLMAgent,
}

AGENT_NAMES = sorted(AGENT_CLASSES)


def build_agent(name: str, **kwargs) -> Agent:
    """Instantiate a registered agent by name."""
    if name not in AGENT_CLASSES:
        raise ValueError(
            f"unknown agent {name!r}; available: {', '.join(AGENT_NAMES)}"
        )
    return AGENT_CLASSES[name](**kwargs)
