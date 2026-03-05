---
marp: true
paginate: true
---

# QVest Reading Momentum POC
Agentic Library Concierge + Tools

- Personalized recommendations from lending history
- Explainable, librarian-friendly outputs
- Lightweight, demo-ready architecture

---

## Problem

- Librarians need fast, trustworthy reading recommendations
- Student profiles are incomplete or outdated
- Inventory, holds, and feedback live in different places
- Hard to explain "why" a book was suggested

---

## What This POC Shows

- Co-borrowing recommender with transparent reasons
- Agentic workflow that combines tools + context
- Optional LLM layer for tone and summarization
- Live UI for concierge, onboarding, holds, gaps, feedback

---

## Demo Story

- Select a student and request recommendations
- Run onboarding from reading history
- Ask for availability and place a hold
- Capture feedback and see the loop improve picks
- Inspect the trace to show how the answer was formed

---

## System Overview

- FastAPI backend, static frontend
- CSV-based catalog, students, loans
- Deterministic recommender + optional LLM
- Agent tools for availability, history, onboarding, holds

---

## Agentic + Tools Architecture

![Agentic Tools Architecture](assets/agentic-tools-architecture.png)

---

## Agent Engine Highlights

- Intent policy and tool routing
- Shared context builder for consistent outputs
- Safety guardrails: no fabrication, privacy-aware
- Observability logs for every run

---

## Tools Layer

- Availability tool
- Reading history tool
- Onboarding from history tool
- Student snapshot tool
- Series/author continuation tool
- Hold placement tool

---

## Recommender + Explanations

- Co-borrowing similarity signals
- Clear, human-readable reasons
- Optional LLM to tailor tone and summary
- No black box rankings in the demo

---

## Observability + Trace UI

- Event list with filters
- Full trace detail per request
- Intents, tools called, filters, counts
- Helps build trust with librarians and partners

---

## Why This Works for Pilot

- Runs locally, easy to demo
- Deterministic core with optional LLM
- Transparent explanations for decision-makers
- Clear upgrade path to production

---

## Roadmap

- Add evaluations and scripted demo flows
- Expand recommendation signals
- Integrate live catalog data
- Add multi-school dashboards
- Harden guardrails and policy controls

---

## Ask

- Approve pilot scope and success metrics
- Identify 2 schools for early rollout
- Align on data access and privacy constraints

---

## Q&A

Thank you.
