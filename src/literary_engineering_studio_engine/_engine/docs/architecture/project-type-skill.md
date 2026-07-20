# Project-Type Skill Architecture

## Decision

The project no longer treats the local Creative Director agent as the core product. Instead, the core product is a project-type skill for Codex, Claude, and similar tool-layer platforms.

## Why

Building a complete local director agent requires too much duplicated platform work:

- free-form conversation memory;
- planning and replanning;
- tool-call loops;
- subagent spawning;
- model provider routing;
- UI state;
- long-running task management;
- recovery and review.

Codex and Claude already provide much of this layer. The skill should teach those agents how to manage a literary engineering project instead of rebuilding the platform inside the repository.

## New Responsibility Split

Tool-layer platform:

- user conversation;
- project-director judgment;
- creative-director taste and tradeoffs;
- LLM generation;
- subagent delegation;
- iterative planning;
- file edits and review.

This repository:

- `SKILL.md` trigger and operating rules;
- `AGENTS.md` and `agentread.yaml` onboarding;
- artifact contracts;
- templates;
- schemas;
- source import and reverse-extraction contracts;
- style project and Style Skill mechanics;
- deterministic CLI helpers for formal route sidecars, manifests, and provenance gates;
- optional integration docs for LangGraph, Dify, and FastAPI.

## Downgraded Components

These remain useful but are no longer the main interface:

- `director-chat`;
- `/director/chat`;
- local frontend creative-director chat;
- local `http-chat` as default creative provider;
- built-in finite director tool loop.

Use them for demos, regression, or when the user explicitly requests local orchestration.

## Preserved Components

Keep these as core project value:

- work project file structure;
- candidate/review/promotion boundary;
- existing-work import into candidate project files;
- hidden character background story semantics;
- context packets and knowledge store;
- style compiler and Style Skill mount;
- prompt pack contracts;
- canon lint;
- scene composition and state patches;
- chapter/export/publish flows;
- tests and deterministic helper commands.

## Practical Usage

When using this skill, a platform agent should:

1. Read `SKILL.md`.
2. Read `AGENTS.md` and `agentread.yaml`.
3. Route the task to the smallest relevant reference.
4. Inspect the work project.
5. Act as director.
6. Use helper CLI only when it saves deterministic effort.
7. Return user-facing creative decisions, not internal plumbing.
