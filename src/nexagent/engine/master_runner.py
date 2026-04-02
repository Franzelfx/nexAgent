"""Master runner — builds and executes the orchestration LangGraph per workflow."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.engine.capability_map import build_capability_map
from nexagent.engine.lane_manager import execute_delegations
from nexagent.models.orchestrator import Orchestrator
from nexagent.models.sub_agent import SubAgent
from nexagent.models.workflow import Workflow
from nexagent.services.crypto import decrypt_api_key
from nexagent.services import execution_service as tracker
from nexagent.state.orchestration import DelegationTask, OrchestrationState

logger = logging.getLogger(__name__)


def _build_master_llm(orch: Orchestrator) -> Any:
    """Build the LLM for the master orchestrator."""
    api_key = ""
    if orch.api_key_encrypted:
        api_key = decrypt_api_key(orch.api_key_encrypted)

    kwargs: dict[str, Any] = {
        "model": orch.model_name,
        "temperature": orch.temperature,
    }
    if orch.max_tokens:
        kwargs["max_tokens"] = orch.max_tokens

    provider = orch.provider.lower()
    if provider == "anthropic":
        if api_key:
            kwargs["api_key"] = api_key
        return ChatAnthropic(**kwargs)
    else:
        if api_key:
            kwargs["api_key"] = api_key
        config = orch.config or {}
        if config.get("base_url"):
            kwargs["base_url"] = config["base_url"]
        return ChatOpenAI(**kwargs)


PLAN_SYSTEM_PROMPT = """You are a master orchestrator. Your job is to analyze the user's task and delegate sub-tasks to your available sub-agents.

{capability_summary}

Respond with a JSON array of delegations. Each delegation has:
- "sub_agent_name": name of the sub-agent to delegate to
- "sub_task": description of what this sub-agent should do

Only delegate to sub-agents listed in the capability map above. If you can answer directly without delegation, return an empty array [].

Respond ONLY with the JSON array, no other text."""


SYNTHESIZE_SYSTEM_PROMPT = """You are a master orchestrator synthesizing results from your sub-agents.

Original task: {task_input}

Sub-agent results:
{results_summary}

Provide a coherent, comprehensive answer that combines the sub-agent findings. If any sub-agent failed, note that but still provide the best possible answer from available results."""


async def run_workflow(
    db: AsyncSession,
    workflow: Workflow,
    task_input: str,
    execution_id: uuid.UUID | None = None,
) -> OrchestrationState:
    """Execute a workflow: plan → delegate → collect → synthesize loop.

    Args:
        db: Active async DB session.
        workflow: The workflow to execute (must have orchestrator loaded).
        task_input: The user's instruction.
        execution_id: Optional execution ID for persistence tracking.

    Returns:
        Final OrchestrationState with results.
    """
    orch = workflow.orchestrator
    if orch is None:
        return OrchestrationState(
            workflow_id=workflow.id,
            task_input=task_input,
            status="failed",
            error="Workflow has no orchestrator assigned",
        )

    # Build capability map
    cap_map = await build_capability_map(db, orch.id)
    agents_by_name: dict[str, SubAgent] = {a.name: a for a in orch.sub_agents}
    agents_by_id: dict[str, SubAgent] = {str(a.id): a for a in orch.sub_agents}

    state = OrchestrationState(
        execution_id=execution_id,
        workflow_id=workflow.id,
        task_input=task_input,
        max_iterations=orch.max_iterations,
        capability_summary=cap_map.summary,
        status="running",
    )

    master_llm = _build_master_llm(orch)

    # Tracking: create execution and master lane if persistence enabled
    master_lane_id: uuid.UUID | None = None
    if execution_id:
        await tracker.start_execution(db, execution_id)
        master_lane = await tracker.create_lane(
            db, execution_id, 0, "master", orch.id, orch.name,
        )
        master_lane_id = master_lane.id
        await tracker.start_lane(db, master_lane_id)
        master_step_idx = 0

    for iteration in range(orch.max_iterations):
        state.iteration_count = iteration + 1

        # ── PLAN ──
        plan_prompt = PLAN_SYSTEM_PROMPT.format(capability_summary=cap_map.summary)
        plan_messages = [
            SystemMessage(content=plan_prompt),
            HumanMessage(content=task_input),
        ]
        if state.lane_results:
            # Include previous results for re-planning
            prev = "\n".join(
                f"- {r.get('agent', '?')}: {r.get('result', 'no result')}"
                for r in state.lane_results
            )
            plan_messages.append(
                HumanMessage(content=f"Previous results:\n{prev}\n\nDo you need more delegations, or can you synthesize?")
            )

        try:
            plan_response: AIMessage = await master_llm.ainvoke(plan_messages)
        except Exception as e:
            state.status = "failed"
            state.error = f"Master LLM planning error: {e}"
            break

        plan_text = plan_response.content or "[]"
        state.plan = plan_text

        # Track planning step
        if execution_id and master_lane_id:
            master_step_idx += 1
            await tracker.record_step(
                db, master_lane_id, master_step_idx, "llm_call",
                input_data={"prompt": "plan delegation"},
                output_data={"plan": plan_text},
                model_used=orch.model_name,
            )

        # Parse delegations
        try:
            raw = plan_text.strip()
            # Handle markdown code fences
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1]) if len(lines) > 2 else "[]"
            delegations_data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            delegations_data = []

        if not delegations_data:
            # No delegations needed — synthesize directly
            break

        # ── DELEGATE ──
        new_delegations: list[DelegationTask] = []
        for d in delegations_data:
            agent_name = d.get("sub_agent_name", "")
            agent = agents_by_name.get(agent_name)
            if agent is None:
                logger.warning("Plan references unknown agent '%s', skipping", agent_name)
                continue
            new_delegations.append(DelegationTask(
                sub_agent_id=agent.id,
                sub_agent_name=agent.name,
                sub_task=d.get("sub_task", ""),
            ))

        if not new_delegations:
            break

        # Track delegation step
        if execution_id and master_lane_id:
            master_step_idx += 1
            await tracker.record_step(
                db, master_lane_id, master_step_idx, "delegation",
                input_data={"delegations": [
                    {"agent": d.sub_agent_name, "task": d.sub_task}
                    for d in new_delegations
                ]},
            )

        # Create lanes for each delegated sub-agent
        if execution_id:
            for i, d in enumerate(new_delegations):
                lane_idx = len(state.lane_results) + i + 1  # master is 0
                lane = await tracker.create_lane(
                    db, execution_id, lane_idx, "sub_agent", d.sub_agent_id, d.sub_agent_name,
                )
                await tracker.start_lane(db, lane.id)

        # ── EXECUTE ──
        completed = await execute_delegations(
            new_delegations, agents_by_id, strategy=orch.strategy,
        )

        # ── COLLECT ──
        new_results: list[dict[str, Any]] = []
        for d in completed:
            new_results.append({
                "agent": d.sub_agent_name,
                "task": d.sub_task,
                "result": d.result or "",
                "status": d.status,
                "tokens_used": d.tokens_used,
                "duration_ms": d.duration_ms,
            })

        # Record sub-agent results in tracker
        if execution_id:
            for i, d in enumerate(completed):
                lane_idx = len(state.lane_results) + i + 1
                # Find the lane — it was created above
                from sqlalchemy import select as sa_select
                from nexagent.models.execution_lane import ExecutionLane
                result = await db.execute(
                    sa_select(ExecutionLane).where(
                        ExecutionLane.execution_id == execution_id,
                        ExecutionLane.lane_index == lane_idx,
                    )
                )
                lane_row = result.scalar_one_or_none()
                if lane_row:
                    await tracker.record_step(
                        db, lane_row.id, 1, "llm_call",
                        input_data={"sub_task": d.sub_task},
                        output_data={"result": d.result or ""},
                        tokens_prompt=d.tokens_used // 2 if d.tokens_used else None,
                        tokens_completion=d.tokens_used - (d.tokens_used // 2) if d.tokens_used else None,
                        duration_ms=d.duration_ms,
                        status=d.status,
                        error_message=d.error,
                    )
                    for j, tc in enumerate(d.tool_calls_log):
                        await tracker.record_step(
                            db, lane_row.id, j + 2, "tool_call",
                            input_data=tc,
                            status="completed",
                        )
                    await tracker.complete_lane(
                        db, lane_row.id,
                        status="completed" if d.status == "completed" else "failed",
                    )

        state = state.model_copy(update={
            "delegations": state.delegations + completed,
            "lane_results": state.lane_results + new_results,
        })

    # ── SYNTHESIZE ──
    if state.lane_results:
        results_summary = "\n".join(
            f"- {r['agent']} ({r['status']}): {r['result'][:500]}"
            for r in state.lane_results
        )
        synth_prompt = SYNTHESIZE_SYSTEM_PROMPT.format(
            task_input=task_input,
            results_summary=results_summary,
        )
        try:
            synth_response: AIMessage = await master_llm.ainvoke([
                SystemMessage(content=synth_prompt),
                HumanMessage(content="Please synthesize the results above into a final answer."),
            ])
            state.final_output = synth_response.content or ""
        except Exception as e:
            state.final_output = f"Synthesis error: {e}"
            state.error = str(e)

        # Track synthesis step
        if execution_id and master_lane_id:
            master_step_idx += 1
            await tracker.record_step(
                db, master_lane_id, master_step_idx, "synthesis",
                input_data={"results_count": len(state.lane_results)},
                output_data={"final_output": state.final_output[:1000]},
                model_used=orch.model_name,
            )
    else:
        # No delegations happened — use plan as direct answer
        state.final_output = state.plan

    if not state.error:
        state.status = "completed"

    # Finalize tracking
    if execution_id and master_lane_id:
        await tracker.complete_lane(db, master_lane_id)
        await tracker.complete_execution(
            db, execution_id,
            final_output=state.final_output,
            status=state.status,
            error_message=state.error or None,
        )

    return state
