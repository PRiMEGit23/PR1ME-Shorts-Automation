# PR1M3 Labs Pipeline Specification

This document centralizes shared pipeline definitions used by the prompt library. Stage prompts may still define stage-specific input and output contracts; when a shared term appears in a prompt, use the definitions below unless that prompt explicitly narrows the contract.

## Channel

- **Channel name:** PR1M3 Labs.
- **Platform format:** YouTube Shorts.
- **Subject area:** 3D printing, additive manufacturing, and practical engineering.
- **Default video shape:** vertical 9:16.
- **Default Shorts resolution:** 1080 x 1920.
- **Default Short duration budget:** 35-45 seconds where a prompt references the channel duration contract.

## Shared Principles

- **Single responsibility:** each stage performs only its named pipeline role.
- **Determinism:** the same inputs should produce the same output.
- **Approved-input only:** downstream stages consume upstream-approved artifacts and do not invent missing media, metadata, or content.
- **Fail closed:** malformed input, missing required artifacts, or failed validation returns a structured failure object instead of a guessed result.
- **Traceability:** outputs keep stable identifiers such as `job_id`, `video_id`, `artifact`, file paths, shot IDs, and predecessor versions when those fields are present.

## Common Scalar Names

- `job_id`: stable identifier for one pipeline job or batch.
- `run_id`: stable identifier for one orchestrated pipeline run.
- `video_id`: platform identifier for one published video.
- `file`: exact file path for a single artifact.
- `path`: exact file path or directory path, depending on the local contract.
- `duration_seconds`: duration in seconds.
- `start_second` / `end_second`: timeline offsets in seconds.
- `start_frame` / `end_frame`: timeline offsets in integer frames.
- `fps`: frames per second.
- `width` / `height`: pixel dimensions.
- `volume`: normalized gain/volume value when a prompt defines volume semantics.
- `checks`: list of validation check identifiers.

## Shared Status Values

- `ok`: validation or stage execution passed.
- `failed`: validation or stage execution failed.
- `skipped`: an orchestrated stage was disabled and did not run.
- `blocked`: a downstream stage could not run because an upstream dependency failed.
- `pending`: an orchestrated stage has not started.
- `in_progress`: an orchestrated stage is running.

## Shared Failure Shape

Unless a prompt declares a narrower failure schema, failures use:

```
{ "status": "failed", "reason": string }
```

Prompts may add fields such as `stage`, `missing`, or `checks` when the local contract requires them.

## Shared Validation Shape

Unless a prompt declares a narrower validation schema, successful structured outputs include:

```
{ "validation": { "status": "ok", "checks": [string] } }
```

Prompts that can return partial or rejected results may allow:

```
{ "validation": { "status": "ok" | "failed", "checks": [string] } }
```

## Media Descriptors

### File Descriptor

```
{ "file": string }
```

Use an exact pipeline path. Do not synthesize a path that is absent from the local input contract or upstream manifest.

### Timed Media Descriptor

```
{ "file": string, "start_second": number, "end_second": number }
```

Use seconds for authoring and handoff contracts unless a prompt explicitly requires frame numbers.

### Frame Media Descriptor

```
{ "file": string, "start_frame": number, "end_frame": number }
```

Use integer frame numbers after an fps has been declared.

### Resolution Descriptor

```
{ "width": number, "height": number }
```

For Shorts deliverables, the default target is `{ "width": 1080, "height": 1920 }`.

### Validation Descriptor

```
{ "status": "ok" | "failed", "checks": [string] }
```

Use `ok` only when the local prompt's required checks pass.

## Shared Stage Order

The canonical pipeline order is:

1. Topic
2. Script
3. Fact Check
4. Visual
5. Thumbnail
6. Metadata
7. ComfyUI
8. Voice
9. Audio
10. Motion Graphics
11. Assembly
12. Render
13. Publish

## Asset Categories

The shared asset categories are:

- `broll`
- `music`
- `sfx`
- `font`
- `logo`
- `overlay`

## Renderer And Platform Terms

- **Shorts resolution:** 1080 x 1920 unless the local target contract says otherwise.
- **Frame rate:** represented as `fps`.
- **Codec/container:** represented with local fields such as `codec`, `container`, and `audio_codec`.
- **File ceiling:** represented with `max_file_bytes` or `ceiling_bytes`.
- **Duration ceiling:** represented with `max_duration_seconds` or the channel duration budget.

## Versioning Terms

- `current_version`: semantic version currently assigned to an artifact.
- `version`: newly computed semantic version.
- `previous_version`: version replaced by the new record.
- `change_type`: one of `major`, `minor`, or `patch`.

## Backward Compatibility

This specification documents shared meanings only. It does not rename existing prompt fields, change local schemas, or change stage behavior by itself.
