"""Auto-generate the capability map for an orchestrator."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.schemas.orchestrators import CapabilityMap, CapabilityMapEntry
from nexagent.services.orchestrator_service import get_orchestrator


async def build_capability_map(db: AsyncSession, orchestrator_id: uuid.UUID) -> CapabilityMap:
    """Build a structured capability description from the orchestrator's sub-agent tree.

    Returns both a JSON structure and a natural-language summary suitable
    for injection into an LLM system prompt.
    """
    orch = await get_orchestrator(db, orchestrator_id)
    entries: list[CapabilityMapEntry] = []

    for agent in orch.sub_agents:
        entries.append(CapabilityMapEntry(
            sub_agent_id=agent.id,
            sub_agent_name=agent.name,
            role_description=agent.role_description,
            provider=agent.provider,
            model_name=agent.model_name,
            tools=[t.name for t in agent.tools],
        ))

    # Build natural-language summary
    if not entries:
        summary = f"Orchestrator '{orch.name}' has no sub-agents configured."
    else:
        lines = [f"Orchestrator '{orch.name}' (strategy: {orch.strategy}) has {len(entries)} sub-agent(s):"]
        for entry in entries:
            tool_list = ", ".join(entry.tools) if entry.tools else "no tools"
            lines.append(f"  - {entry.sub_agent_name}: {entry.role_description} (tools: {tool_list})")
        summary = "\n".join(lines)

    return CapabilityMap(
        orchestrator_id=orch.id,
        orchestrator_name=orch.name,
        strategy=orch.strategy,
        entries=entries,
        summary=summary,
    )
