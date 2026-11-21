"""Agent loop with a mocked LLM: approvals, rejections, step limit, safety."""

import json

import pytest
from django.utils import timezone

from agent import agent, tools
from agent.models import AgentRun, AgentStep
from crm import services as crm_services
from crm.models import Deal, Lead, Task
from genai.llm import LLMError, LLMResponse, ToolCall
from genai.testing import scripted_llm

pytestmark = pytest.mark.django_db

GOAL = "Find hot leads not contacted in 7 days, draft follow-ups and create tasks"
EMAIL = json.dumps({"subject": "Quick follow-up", "body": "Hi Asha, ..."})


def calls(*pairs, text=""):
    return LLMResponse(
        content=text,
        tool_calls=[ToolCall(f"call_{n}_{name}", name, args) for n, (name, args) in
                    enumerate(pairs)],
    )  # fmt: skip


def final(text="All done."):
    return LLMResponse(content=text)


@pytest.fixture
def hot_lead(rep, contact_of):
    contact = contact_of(rep)
    lead = Lead.objects.create(owner=rep, contact=contact, source="referral")
    Lead.objects.filter(pk=lead.pk).update(score=91, score_label="hot", last_contacted_at=None)
    return Lead.objects.get(pk=lead.pk)


def start(client, goal=GOAL):
    response = client.post("/api/agent/runs/", {"goal": goal}, format="json")
    assert response.status_code == 201, response.json()
    return response.json()["id"]


def get(client, run_id):
    return client.get(f"/api/agent/runs/{run_id}/").json()


def test_hot_leads_goal_pauses_before_creating_tasks(
    client_for, rep, hot_lead, django_capture_on_commit_callbacks
):
    client = client_for(rep)
    script = [
        calls(("search_leads", {"label": "hot", "not_contacted_days": 7}),
              text="Plan: find hot leads, draft follow-ups, then create tasks."),
        calls(("draft_email", {"contact_id": hot_lead.contact_id, "goal": "follow up"}),
              ("create_task", {"title": "Follow up with Asha", "contact_id": hot_lead.contact_id,
                               "due_in_days": 1, "priority": "high"})),
        EMAIL,  # the LLM call made inside the draft_email tool
        final("Drafted 1 follow-up and created 1 task."),
    ]  # fmt: skip
    with scripted_llm(script), django_capture_on_commit_callbacks(execute=True):
        run_id = start(client)

    run = get(client, run_id)
    assert run["status"] == "awaiting_approval"
    names = [(s["tool_name"], s["status"]) for s in run["steps"]]
    assert names == [
        ("search_leads", "done"),
        ("draft_email", "done"),
        ("create_task", "pending_approval"),
    ]
    assert run["steps"][0]["tool_output"]["leads"][0]["lead_id"] == hot_lead.id
    assert run["steps"][1]["tool_output"]["subject"] == "Quick follow-up"
    assert run["steps"][2]["requires_approval"] is True
    assert not Task.objects.exists()  # the write tool did NOT run

    pending = run["steps"][2]["id"]
    with scripted_llm(script[3:]), django_capture_on_commit_callbacks(execute=True):
        response = client.post(f"/api/agent/steps/{pending}/approve/")
    assert response.status_code == 200
    task = Task.objects.get()
    assert task.created_by_agent and task.contact_id == hot_lead.contact_id
    assert task.due_date == timezone.localdate() + timezone.timedelta(days=1)

    run = get(client, run_id)
    assert run["status"] == "done"
    assert run["final_summary"] == "Drafted 1 follow-up and created 1 task."
    assert run["steps"][2]["approved"] is True


def test_rejecting_a_step_skips_it_and_the_agent_continues(
    client_for, rep, hot_lead, django_capture_on_commit_callbacks
):
    deal = crm_services.create_deal(owner=rep, contact=hot_lead.contact, title="D", value=10)
    client = client_for(rep)
    with scripted_llm([
        calls(("update_deal_stage", {"deal_id": deal.id, "stage": "won"}),
              ("create_task", {"title": "Send thank-you note"})),
    ]), django_capture_on_commit_callbacks(execute=True):  # fmt: skip
        run_id = start(client, "Mark the deal won and add a thank-you task")
    steps = get(client, run_id)["steps"]
    stage_step, task_step = steps[0]["id"], steps[1]["id"]

    seen = []

    def capture(text):
        seen.append(text)
        return final(text)

    # Reject the deal move, approve the task; only then does the run resume.
    client.post(f"/api/agent/steps/{stage_step}/reject/")
    assert get(client, run_id)["status"] == "awaiting_approval"
    with scripted_llm([final("Created the task; you rejected moving the deal.")]) as llm_calls, \
            django_capture_on_commit_callbacks(execute=True):  # fmt: skip
        client.post(f"/api/agent/steps/{task_step}/approve/")
    run = get(client, run_id)
    assert run["status"] == "done"
    deal.refresh_from_db()
    assert deal.stage == "new"  # rejected: never executed
    assert Task.objects.filter(title="Send thank-you note").exists()
    # The model was told about the rejection and continued.
    tool_messages = [m for m in llm_calls[0]["messages"] if m["role"] == "tool"]
    assert json.loads(tool_messages[0]["content"])["rejected"] is True
    assert tool_messages[0].get("is_error") is True
    assert run["steps"][0]["status"] == "rejected" and run["steps"][0]["approved"] is False


def test_step_limit_of_10_holds(client_for, rep, django_capture_on_commit_callbacks):
    endless = [calls(("search_leads", {"limit": 1})) for _ in range(12)]
    with scripted_llm(endless) as llm_calls, django_capture_on_commit_callbacks(execute=True):
        run_id = start(client_for(rep), "Keep searching leads forever please")
    run = get(client_for(rep), run_id)
    assert run["status"] == "done"
    assert len(run["steps"]) == agent.MAX_STEPS == 10
    assert "10-step limit" in run["final_summary"]
    assert len(llm_calls) == 10


def test_calls_beyond_the_limit_in_one_turn_are_not_run(
    client_for, rep, django_capture_on_commit_callbacks
):
    many = calls(*[("create_task", {"title": f"T{i}"}) for i in range(12)])
    with scripted_llm([many]), django_capture_on_commit_callbacks(execute=True):
        run_id = start(client_for(rep), "Create twelve tasks for me")
    run = get(client_for(rep), run_id)
    assert len(run["steps"]) == 10
    assert all(s["status"] == "pending_approval" for s in run["steps"])
    assert not Task.objects.exists()


def test_write_tools_never_run_without_approval():
    writes = {n for n, t in tools.TOOLS.items() if t.write}
    assert writes >= {"create_task", "update_deal_stage"}
    assert not any("delete" in n or "refund" in n for n in tools.TOOLS)


def test_unknown_tool_and_bad_ids_come_back_as_errors(
    client_for, rep, other_rep, contact_of, django_capture_on_commit_callbacks
):
    theirs = contact_of(other_rep)
    with scripted_llm([
        calls(("delete_everything", {}), ("get_contact_history", {"contact_id": theirs.id})),
        final("Could not access those."),
    ]), django_capture_on_commit_callbacks(execute=True):  # fmt: skip
        run_id = start(client_for(rep), "Tell me about that other contact")
    steps = get(client_for(rep), run_id)["steps"]
    assert "Unknown tool" in steps[0]["tool_output"]["error"]
    assert "not found" in steps[1]["tool_output"]["error"]  # scoped to the rep's own data
    assert [s["status"] for s in steps] == ["failed", "failed"]


def test_llm_outage_fails_the_run_cleanly(client_for, rep, django_capture_on_commit_callbacks):
    with (
        scripted_llm([LLMError("groq HTTP 503")]),
        django_capture_on_commit_callbacks(execute=True),
    ):
        run_id = start(client_for(rep), "Find my hot leads")
    run = get(client_for(rep), run_id)
    assert run["status"] == "failed" and "503" in run["error"]


def test_only_owner_can_decide_and_only_once(
    client_for, rep, other_rep, django_capture_on_commit_callbacks
):
    with scripted_llm([calls(("create_task", {"title": "X"}))]), \
            django_capture_on_commit_callbacks(execute=True):  # fmt: skip
        run_id = start(client_for(rep), "Create a task called X")
    step_id = AgentStep.objects.get(run_id=run_id).id
    assert client_for(other_rep).post(f"/api/agent/steps/{step_id}/approve/").status_code == 404
    with scripted_llm([final()]), django_capture_on_commit_callbacks(execute=True):
        assert client_for(rep).post(f"/api/agent/steps/{step_id}/approve/").status_code == 200
    again = client_for(rep).post(f"/api/agent/steps/{step_id}/approve/")
    assert again.status_code == 400 and "already been decided" in again.json()["error"]["message"]


def test_support_cannot_use_the_agent(client_for, support_user):
    assert (
        client_for(support_user)
        .post("/api/agent/runs/", {"goal": "do things"}, format="json")
        .status_code
        == 403
    )


def test_runs_are_private(client_for, rep, other_rep):
    run = AgentRun.objects.create(user=other_rep, goal="secret")
    assert client_for(rep).get(f"/api/agent/runs/{run.id}/").status_code == 404
    assert client_for(rep).get("/api/agent/runs/").json()["count"] == 0


def test_offline_planner_demo_flow(client_for, rep, hot_lead, django_capture_on_commit_callbacks):
    """Without an LLM key the scripted demo planner still shows search -> drafts -> approval."""
    with django_capture_on_commit_callbacks(execute=True):
        run_id = start(client_for(rep))
    run = get(client_for(rep), run_id)
    assert run["status"] == "awaiting_approval"
    assert [s["tool_name"] for s in run["steps"]] == ["search_leads", "draft_email", "create_task"]
    step_id = run["steps"][2]["id"]
    with django_capture_on_commit_callbacks(execute=True):
        client_for(rep).post(f"/api/agent/steps/{step_id}/approve/")
    run = get(client_for(rep), run_id)
    assert run["status"] == "done" and "[offline demo]" in run["final_summary"]
    assert Task.objects.filter(created_by_agent=True).count() == 1


def test_deal_stage_tool_validates_stage(rep, contact_of):
    deal = crm_services.create_deal(owner=rep, contact=contact_of(rep), title="D", value=1)
    out = tools.run_tool(rep, "update_deal_stage", {"deal_id": deal.id, "stage": "maybe"})
    assert "Unknown stage" in out["error"]
    assert tools.run_tool(rep, "update_deal_stage", {"deal_id": deal.id})["error"].startswith(
        "Missing"
    )
    assert Deal.objects.get(pk=deal.pk).stage == "new"
