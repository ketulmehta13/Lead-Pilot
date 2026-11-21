"""The agent loop.

    goal + tool schemas -> LLM -> tool calls
      read call  -> run now, log an AgentStep, feed the result back
      write call -> log an AgentStep(requires_approval) and PAUSE the run (awaiting_approval)
    approve -> run the tool;  reject -> tell the model it was rejected (it skips and continues)
    -> loop until the model answers without tools, or MAX_STEPS tool calls.

Every tool call is an AgentStep. The LLM conversation is stored on the run so it can resume
after approvals. All results for one model turn are sent back together (required by both the
OpenAI-style and Claude APIs).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from genai import llm
from genai.prompts import render
from genai.services import LLMOutputError

from . import tools
from .models import AgentRun, AgentStep

logger = logging.getLogger(__name__)

MAX_STEPS = 10
MAX_RESULT_CHARS = 4000
REJECTED = {
    "rejected": True,
    "message": "The user rejected this action. Do not retry it; continue with the rest of the goal.",
}


class AgentStateError(Exception):
    """An action that doesn't fit the run's current state (e.g. approving twice)."""


def start_run(user: User, goal: str) -> AgentRun:
    system = render(
        "agent_system",
        user_name=user.get_full_name() or user.username,
        role=user.get_role_display(),
        today=timezone.localdate().strftime("%d %b %Y"),
        max_steps=MAX_STEPS,
    )
    return AgentRun.objects.create(
        user=user,
        goal=goal,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": goal}],
    )


# --- The loop -------------------------------------------------------------------------------


def advance(run_id: int) -> AgentRun:
    """Run the loop until the run finishes or pauses for approval."""
    with transaction.atomic():
        run = AgentRun.objects.select_for_update().get(pk=run_id)
        if run.status not in AgentRun.ACTIVE:
            return run  # already paused/finished (e.g. a duplicate task)
        run.status = AgentRun.Status.RUNNING
        run.save(update_fields=["status", "updated_at"])

    try:
        while True:
            used = run.steps.count()
            if used >= MAX_STEPS:
                return _finish(run, _limit_summary(run))
            response = _call_model(run)
            run.messages.append(response.as_message())
            if not response.tool_calls:
                return _finish(run, response.content.strip() or "Done.")

            pending = False
            for n, call in enumerate(response.tool_calls):
                if used + n >= MAX_STEPS:
                    continue  # over the limit: not run, not logged (see _append_results)
                tool = tools.TOOLS.get(call.name)
                note = response.content if n == 0 else ""
                if tool is not None and tool.write:
                    _record(run, call, note, status=AgentStep.Status.PENDING_APPROVAL,
                            requires_approval=True)  # fmt: skip
                    pending = True
                else:
                    output = _execute(run.user, call.name, call.arguments)
                    status = AgentStep.Status.FAILED if "error" in output else AgentStep.Status.DONE
                    _record(run, call, note, output=output, status=status)

            if pending:
                run.status = AgentRun.Status.AWAITING_APPROVAL
                run.save(update_fields=["messages", "status", "updated_at"])
                return run
            _append_results(run, response.tool_calls)
            run.save(update_fields=["messages", "updated_at"])
    except (llm.LLMError, LLMOutputError) as exc:
        logger.warning("Agent run %s failed: %s", run.pk, exc)
        run.status, run.error, run.finished_at = AgentRun.Status.FAILED, str(exc), timezone.now()
        run.save(update_fields=["status", "error", "finished_at", "messages", "updated_at"])
        return run


def decide(step_id: int, user: User, approve: bool) -> AgentRun:
    """Approve (run the tool) or reject a pending write step; resume when none are pending."""
    with transaction.atomic():
        step = AgentStep.objects.select_for_update().select_related("run").get(pk=step_id)
        run = AgentRun.objects.select_for_update().get(pk=step.run_id)
        if step.status != AgentStep.Status.PENDING_APPROVAL:
            raise AgentStateError("This step has already been decided.")
        if run.status != AgentRun.Status.AWAITING_APPROVAL:
            raise AgentStateError("This run is not waiting for approval.")
        if approve:
            step.tool_output = _execute(run.user, step.tool_name, step.tool_input)
            step.status = (
                AgentStep.Status.FAILED if "error" in step.tool_output else AgentStep.Status.DONE
            )
        else:
            step.tool_output = REJECTED
            step.status = AgentStep.Status.REJECTED
        step.approved, step.decided_by, step.decided_at = approve, user, timezone.now()
        step.save()

        if run.steps.filter(status=AgentStep.Status.PENDING_APPROVAL).exists():
            return run  # other calls from the same turn still need a decision
        last_calls = run.messages[-1].get("tool_calls", [])
        _append_results(run, [llm.ToolCall(c["id"], c["name"], c["arguments"]) for c in last_calls])
        run.status = AgentRun.Status.PLANNING
        run.save(update_fields=["messages", "status", "updated_at"])
    return run


# --- helpers --------------------------------------------------------------------------------


def _call_model(run: AgentRun) -> llm.LLMResponse:
    if llm.provider_name() == "mock" and not _scripted_mock_active():
        return offline_planner(run)
    return llm.chat(run.messages, tools=tools.schemas(), purpose="agent", user=run.user)


def _scripted_mock_active() -> bool:
    """genai.testing.scripted_llm swaps the mock adapter; then tests drive the agent."""
    return llm._ADAPTERS["mock"].__name__ != "_mock"


def _execute(user: User, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        return tools.run_tool(user, name, arguments)
    except (llm.LLMError, LLMOutputError) as exc:  # e.g. draft_email's LLM call failed
        return {"error": f"AI step failed: {exc}"}


def _record(run, call, note, *, output=None, status, requires_approval=False) -> AgentStep:
    return AgentStep.objects.create(
        run=run,
        order=run.steps.count() + 1,
        tool_name=call.name[:60],
        tool_call_id=call.id[:120],
        tool_input=call.arguments,
        tool_output=output,
        note=(note or "")[:2000],
        requires_approval=requires_approval,
        status=status,
    )


def _append_results(run: AgentRun, calls: list[llm.ToolCall]) -> None:
    """One tool message per call of the last assistant turn, in the same order."""
    steps = {s.tool_call_id: s for s in run.steps.filter(tool_call_id__in=[c.id for c in calls])}
    for call in calls:
        step = steps.get(call.id)
        output = (
            step.tool_output
            if step
            else {"error": f"Not executed: the {MAX_STEPS}-step limit was reached."}
        )
        text = json.dumps(output, default=str)
        if len(text) > MAX_RESULT_CHARS:
            text = text[:MAX_RESULT_CHARS] + "... (truncated)"
        message = {"role": "tool", "tool_call_id": call.id, "content": text}
        if step is None or step.status in (AgentStep.Status.FAILED, AgentStep.Status.REJECTED):
            message["is_error"] = True
        run.messages.append(message)


def _finish(run: AgentRun, summary: str) -> AgentRun:
    run.status, run.final_summary, run.finished_at = (
        AgentRun.Status.DONE,
        summary,
        timezone.now(),
    )
    run.save(update_fields=["status", "final_summary", "finished_at", "messages", "updated_at"])
    return run


def _limit_summary(run: AgentRun) -> str:
    done = run.steps.filter(status=AgentStep.Status.DONE).count()
    return (
        f"Stopped after reaching the {MAX_STEPS}-step limit ({done} steps completed). "
        "Review the steps above and start a narrower goal for anything left."
    )


# --- Offline planner (no LLM configured) ---------------------------------------------------


def offline_planner(run: AgentRun) -> llm.LLMResponse:
    """A small scripted planner used only when no LLM key is set, so the approval flow can
    still be demonstrated. It handles "find (hot) leads not contacted in N days, draft
    follow-ups and create tasks"; anything else gets an honest explanation."""
    goal = run.goal.lower()
    steps = list(run.steps.order_by("order"))
    label = next((w for w in ("hot", "warm", "cold") if w in goal), None)
    days_match = re.search(r"(\d{1,3})\s*days?", goal)
    if "lead" not in goal:
        return llm.LLMResponse(
            content="[offline mode] Without an LLM API key I can only run the demo goal "
            "'Find hot leads not contacted in 7 days, draft follow-ups and create tasks'. "
            "Set GROQ_API_KEY to use the real agent.",
            model="offline-planner",
        )
    if not steps:
        args = {"limit": 3}
        if label:
            args["label"] = label
        if days_match:
            args["not_contacted_days"] = int(days_match.group(1))
        return _plan("Plan: find matching leads, draft a follow-up and a task for each.",
                     [("search_leads", args)])  # fmt: skip
    found = steps[0].tool_output or {}
    leads = found.get("leads", [])[:3]
    if len(steps) == 1:
        if not leads:
            return llm.LLMResponse(content="No matching leads found, so nothing to do.",
                                   model="offline-planner")  # fmt: skip
        calls = []
        for lead in leads:
            calls.append(("draft_email", {"contact_id": lead["contact_id"],
                                          "goal": "follow up and propose a short call"}))  # fmt: skip
            calls.append(("create_task", {"title": f"Follow up with {lead['contact']}",
                                           "contact_id": lead["contact_id"], "due_in_days": 1,
                                           "priority": "high"}))  # fmt: skip
        return _plan(f"Found {len(leads)} leads. Drafting follow-ups and proposing tasks.", calls)
    created = [s for s in steps if s.tool_name == "create_task" and s.status == "done"]
    rejected = [s for s in steps if s.status == "rejected"]
    return llm.LLMResponse(
        content=(
            f"[offline demo] Reviewed {len(leads)} leads, drafted {len(leads)} follow-up emails "
            f"(not sent), created {len(created)} task{'s' if len(created) != 1 else ''}"
            + (f", skipped {len(rejected)} you rejected" if rejected else "")
            + ". Open each draft in the step list to copy it."
        ),
        model="offline-planner",
    )


def _plan(note: str, calls: list[tuple[str, dict[str, Any]]]) -> llm.LLMResponse:
    import uuid

    return llm.LLMResponse(
        content=note,
        tool_calls=[llm.ToolCall(f"offline_{uuid.uuid4().hex[:10]}", n, a) for n, a in calls],
        model="offline-planner",
    )
