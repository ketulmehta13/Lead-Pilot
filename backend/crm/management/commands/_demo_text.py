"""Realistic sales notes for demo data, so AI summaries and Ask LeadPilot have real content."""

from __future__ import annotations

import random

PRODUCTS = ["the CRM", "the analytics add-on", "the WhatsApp integration", "the API plan"]
INTEGRATIONS = ["Tally", "Zoho Books", "Shopify", "Razorpay", "Google Workspace", "WhatsApp"]
COMPETITORS = ["Freshworks", "Zoho CRM", "HubSpot", "LeadSquared"]
ROLES = ["CFO", "operations head", "founder", "IT manager", "sales director"]

CALL = [
    "Discussed pricing for {seats} seats; {first} asked whether annual billing gets a discount.",
    "{first} confirmed budget is approved up to Rs {budget} lakh for this quarter.",
    "Walked through the {integration} integration; they need invoices to sync automatically.",
    "{first} mentioned they are also evaluating {competitor} and will decide by {when}.",
    "Main concern is onboarding time for their {team}-person team; wants a two-week rollout.",
    "They asked for a case study from a {industry} customer before the {role} signs off.",
]
EMAIL = [
    "Sent the proposal for {seats} seats with the {product} bundle.",
    "Shared the security questionnaire answers and data-residency details.",
    "Followed up on the trial; {first} says the team likes the pipeline view.",
    "Sent revised pricing after they pushed back on the per-seat cost.",
    "Shared onboarding plan and asked for a kickoff date.",
]
MEETING = [
    "Product demo for {first} and the {role}. They liked lead scoring and the Kanban board.",
    "Quarterly review: usage is up, but they want better reporting for regional managers.",
    "On-site meeting in {city}; agreed next step is a pilot with {pilot} users.",
    "Negotiation call: {first} asked for a {discount}% discount for a 2-year commitment.",
    "Kick-off meeting: agreed timelines, owners and a weekly check-in every {weekday}.",
]
NOTE = [
    "{first} is the decision maker; the {role} controls budget.",
    "Risk: they had a bad experience with {competitor} support and are cautious.",
    "Renewal is due in {when}; account is healthy but price-sensitive.",
    "Needs {integration} integration before they can go live.",
]
FOLLOW_UPS = [
    "Next step: send the revised quote by {when}.",
    "Action: book a call with their {role} next week.",
    "Follow up with a {industry} case study.",
    "To do: share the {integration} setup guide and confirm go-live date.",
    "Next step: schedule a demo for the wider team.",
]
LEAD_NOTES = [
    "Came in via {source}. Interested in {product}; team of about {team} people.",
    "Asked about {integration} integration and pricing for {seats} seats.",
    "Currently using spreadsheets; frustrated with {competitor} pricing.",
    "Wants to start a pilot this quarter; budget around Rs {budget} lakh.",
]
WHEN = ["Friday", "end of the month", "next week", "the 15th", "Monday"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday"]


def _fill(template: str, first: str, city: str, industry: str) -> str:
    return template.format(
        first=first,
        seats=random.choice([5, 10, 15, 25, 40, 60]),
        budget=random.choice([2, 3, 5, 8, 12, 20]),
        integration=random.choice(INTEGRATIONS),
        competitor=random.choice(COMPETITORS),
        when=random.choice(WHEN),
        team=random.choice([8, 12, 20, 35, 50]),
        industry=industry,
        role=random.choice(ROLES),
        product=random.choice(PRODUCTS),
        city=city,
        pilot=random.choice([5, 10, 15]),
        discount=random.choice([5, 10, 12, 15]),
        weekday=random.choice(WEEKDAYS),
        source=random.choice(["the website", "a referral", "a LinkedIn ad", "a trade show"]),
    )


def activity_notes(kind: str, first: str, city: str, industry: str) -> str:
    pool = {"call": CALL, "email": EMAIL, "meeting": MEETING, "note": NOTE}[kind]
    sentences = random.sample(pool, k=min(len(pool), random.randint(2, 3)))
    if kind != "note" or random.random() < 0.4:
        sentences.append(random.choice(FOLLOW_UPS))
    return " ".join(_fill(s, first, city, industry) for s in sentences)


def lead_notes(first: str, city: str, industry: str) -> str:
    sentences = random.sample(LEAD_NOTES, k=2)
    return " ".join(_fill(s, first, city, industry) for s in sentences)
