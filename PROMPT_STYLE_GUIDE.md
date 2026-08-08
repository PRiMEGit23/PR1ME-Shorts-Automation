# Prompt Style Guide

This guide centralizes the document conventions shared by the prompt library. Individual prompts should reference this guide instead of repeating identical formatting and validation rules, while retaining their stage-specific contracts.

## Canonical Structure

Prompt files use this 12-section order:

1. `# NN Prompt Name`
2. `## Single Responsibility`
3. `## 1. System Role`
4. `## 2. Objective`
5. `## 3. Core Principles`
6. `## 4. Input Contract`
7. `## 5. Processing Rules`
8. `## 6. Specialized Rules`
9. `## 7. Strict Constraints`
10. `## 8. Output Format`
11. `## 9. Examples`
12. `## 10. Failure Conditions`
13. `## 11. Silent Validation`
14. `## 12. Final Instruction`

When a prompt needs named subsections under a numbered section, use lower-level headings or bold labels without duplicating the numbered heading.

## Shared References Section

Each stage prompt may include this optional section after `## Single Responsibility` and before `## 1. System Role`:

```
## Shared References

- Use `../PIPELINE_SPEC.md` for shared channel, pipeline, artifact, status, validation, media, and naming definitions.
- Use `../PROMPT_STYLE_GUIDE.md` for document structure, JSON, examples, failure, and silent-validation conventions.
- This prompt keeps only stage-specific behavior below. If a local rule conflicts with a shared convention, the local rule narrows the shared convention for this stage.
```

## JSON Conventions

- Receive exactly one JSON object unless the local prompt explicitly says otherwise.
- Return exactly one JSON object.
- Do not return markdown, commentary, or prose outside the JSON object.
- Use explicit field names and stable primitive types.
- Use `null` for known-but-unavailable nullable values.
- Do not invent fields that are not present in the local contract or shared specification.
- Keep examples parseable as JSON-like prompt schemas or concrete JSON examples.

## Validation Conventions

- A successful output includes a `validation` object when the local output schema defines one.
- `validation.status` is `ok` only when all required checks pass.
- `checks` contains short machine-readable check identifiers.
- Failing checks return the local failure object instead of a success object with failed validation, unless the prompt explicitly supports partial results.
- Silent validation checklists are internal and must not be emitted.

## Failure Conventions

- Use the shared failure shape from `PIPELINE_SPEC.md` unless the local prompt declares added fields.
- Failure reasons should be exact enough for an automated orchestrator or debugger to route the error.
- Missing input, malformed input, invalid enum values, missing required artifacts, and impossible output structures fail closed.

## Example Conventions

- Examples must not introduce behavior beyond the local contract.
- A valid input example should satisfy every required input field.
- A valid output example should satisfy the declared output schema.
- An invalid output example should fail for the reasons listed in its explanation.
- Example IDs, paths, and timestamps should remain internally traceable between input and output.

## Formatting Conventions

- Use concise headings and bullet lists.
- Use fenced code blocks for schemas and examples.
- Use backticks for field names, enum values, and literal JSON keys.
- Keep stage-specific rules in the stage prompt; keep shared terminology in `PIPELINE_SPEC.md`.

## Backward Compatibility

This guide is documentation-only. Adding references to it should not change prompt behavior unless a prompt explicitly says the shared guide overrides a local rule.
