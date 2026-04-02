"""Workflow CRUD service with validation and graph export."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from nexagent.models.orchestrator import Orchestrator
from nexagent.models.sub_agent import SubAgent
from nexagent.models.workflow import Workflow
from nexagent.schemas.workflows import (
    ValidationResult,
    WorkflowCreate,
    WorkflowGraphEdge,
    WorkflowGraphExport,
    WorkflowGraphNode,
    WorkflowUpdate,
)


class WorkflowServiceError(Exception):
    pass


class WorkflowNotFoundError(WorkflowServiceError):
    pass


async def create_workflow(db: AsyncSession, data: WorkflowCreate) -> Workflow:
    """Create a new workflow."""
    if data.orchestrator_id:
        orch = await db.get(Orchestrator, data.orchestrator_id)
        if orch is None:
            raise WorkflowNotFoundError(f"Orchestrator {data.orchestrator_id} not found")

    wf = Workflow(
        name=data.name,
        description=data.description,
        orchestrator_id=data.orchestrator_id,
        graph_layout=data.graph_layout,
    )
    db.add(wf)
    await db.flush()
    await db.refresh(wf)
    return wf


async def get_workflow(db: AsyncSession, wf_id: uuid.UUID) -> Workflow:
    """Get a single workflow with its full orchestrator tree."""
    result = await db.execute(
        select(Workflow)
        .options(
            selectinload(Workflow.orchestrator)
            .selectinload(Orchestrator.sub_agents)
            .selectinload(SubAgent.tools)
        )
        .where(Workflow.id == wf_id)
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise WorkflowNotFoundError(f"Workflow {wf_id} not found")
    return wf


async def list_workflows(
    db: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    is_active: bool | None = None,
    search: str | None = None,
) -> tuple[list[Workflow], int]:
    """List workflows with optional filters."""
    query = select(Workflow).options(
        selectinload(Workflow.orchestrator)
    )
    count_query = select(func.count()).select_from(Workflow)

    if is_active is not None:
        query = query.where(Workflow.is_active == is_active)
        count_query = count_query.where(Workflow.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        query = query.where(Workflow.name.ilike(pattern))
        count_query = count_query.where(Workflow.name.ilike(pattern))

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Workflow.created_at.desc()).offset(offset).limit(limit)
    items = list((await db.execute(query)).scalars().unique().all())
    return items, total


async def update_workflow(db: AsyncSession, wf_id: uuid.UUID, data: WorkflowUpdate) -> Workflow:
    """Update an existing workflow."""
    wf = await get_workflow(db, wf_id)
    update_data = data.model_dump(exclude_unset=True)

    if "orchestrator_id" in update_data and update_data["orchestrator_id"] is not None:
        orch = await db.get(Orchestrator, update_data["orchestrator_id"])
        if orch is None:
            raise WorkflowNotFoundError(f"Orchestrator {update_data['orchestrator_id']} not found")

    for field, value in update_data.items():
        setattr(wf, field, value)

    await db.flush()
    await db.refresh(wf)
    return wf


async def delete_workflow(db: AsyncSession, wf_id: uuid.UUID) -> Workflow:
    """Soft-delete a workflow."""
    wf = await get_workflow(db, wf_id)
    wf.is_active = False
    await db.flush()
    await db.refresh(wf)
    return wf


async def validate_workflow(db: AsyncSession, wf_id: uuid.UUID) -> ValidationResult:
    """Validate that a workflow is complete and ready for execution."""
    wf = await get_workflow(db, wf_id)
    errors: list[str] = []

    if wf.orchestrator_id is None or wf.orchestrator is None:
        errors.append("Workflow has no orchestrator assigned")
        return ValidationResult(valid=False, errors=errors)

    orch = wf.orchestrator

    if not orch.is_active:
        errors.append(f"Orchestrator '{orch.name}' is inactive")

    if not orch.sub_agents:
        errors.append("Orchestrator has no sub-agents assigned")
    else:
        for agent in orch.sub_agents:
            if not agent.is_active:
                errors.append(f"Sub-agent '{agent.name}' is inactive")
            if not agent.model_name:
                errors.append(f"Sub-agent '{agent.name}' has no model configured")
            if not agent.provider:
                errors.append(f"Sub-agent '{agent.name}' has no provider configured")
            inactive_tools = [t for t in agent.tools if not t.is_active]
            for t in inactive_tools:
                errors.append(f"Sub-agent '{agent.name}' references inactive tool '{t.name}'")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


async def export_graph(db: AsyncSession, wf_id: uuid.UUID) -> WorkflowGraphExport:
    """Build a node/edge graph representation for the UI builder."""
    wf = await get_workflow(db, wf_id)
    nodes: list[WorkflowGraphNode] = []
    edges: list[WorkflowGraphEdge] = []

    layout = wf.graph_layout or {}

    if wf.orchestrator is None:
        return WorkflowGraphExport(workflow_id=wf.id, nodes=nodes, edges=edges)

    orch = wf.orchestrator
    orch_node_id = f"orch-{orch.id}"
    nodes.append(WorkflowGraphNode(
        id=orch_node_id,
        type="orchestrator",
        label=orch.name,
        position=layout.get(orch_node_id),
    ))

    for agent in orch.sub_agents:
        agent_node_id = f"agent-{agent.id}"
        nodes.append(WorkflowGraphNode(
            id=agent_node_id,
            type="sub_agent",
            label=agent.name,
            position=layout.get(agent_node_id),
        ))
        edges.append(WorkflowGraphEdge(
            source=orch_node_id,
            target=agent_node_id,
            label="delegates",
        ))

        for tool in agent.tools:
            tool_node_id = f"tool-{tool.id}-{agent.id}"
            nodes.append(WorkflowGraphNode(
                id=tool_node_id,
                type="tool",
                label=tool.display_name,
                position=layout.get(tool_node_id),
            ))
            edges.append(WorkflowGraphEdge(
                source=agent_node_id,
                target=tool_node_id,
                label="uses",
            ))

    return WorkflowGraphExport(workflow_id=wf.id, nodes=nodes, edges=edges)
