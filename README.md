# PR1ME Shorts Automation

Enterprise-grade AI automation pipeline for generating engineering-focused YouTube Shorts for PR1M3 Labs.

## Overview

This repository contains the PR1ME Prompt Framework: a staged prompt library and shared specification layer for producing engineering-focused YouTube Shorts. The framework is organized around single-responsibility prompts, shared pipeline terminology, strict JSON contracts, and deterministic handoffs between production stages.

## Repository Structure

- `prompts/` - stage prompts for topic generation, scripting, review, visual planning, media preparation, publishing, analytics, and versioning.
- `PIPELINE_SPEC.md` - shared pipeline definitions, artifact terminology, status values, and handoff conventions.
- `PROMPT_STYLE_GUIDE.md` - shared prompt document structure, JSON conventions, examples, and validation conventions.
- `assets/` - local asset workspace.
- `config/` - configuration workspace.
- `workflows/` - workflow workspace.
- `output/` - generated output workspace.
- `temp/` - temporary workspace.

## License

MIT
