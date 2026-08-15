# Model Director — Compatibility Matrix (Phase 10)

Every cell below is generated from the registry's capability records via
`compatibility_matrix()` — the registry is the single source of truth,
and `check_model` enforces it before anything reaches an adapter. "yes"
means the model supports at least one value of that parameter family;
"no" means the model does not support the family at all (the selectors
clamp to "none" and the compatibility checker reports a violation if a
proposed plan ever asks for it).

| model | animation_backends | aspect_ratios | controlnet | depth | ip_adapter | refiners | resolutions | samplers | schedulers | segmentation | upscalers | vaes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| flux-dev | no | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| flux-schnell | no | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| sdxl | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| juggernaut-xl | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| realvis-xl | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| qwen-image | no | yes | no | no | yes | yes | yes | yes | yes | no | yes | yes |
| gpt-image | no | yes | no | no | no | yes | yes | yes | yes | no | yes | yes |
| hiredream | no | yes | no | no | yes | yes | yes | yes | yes | no | yes | yes |
| wan-2-2 | yes | yes | yes | yes | no | yes | yes | yes | yes | no | yes | yes |
| ltx-video | yes | yes | no | no | no | yes | yes | yes | yes | no | no | yes |
| hunyuan-video | yes | yes | yes | no | no | yes | yes | yes | yes | no | no | yes |
| cogvideox | yes | yes | no | no | no | yes | yes | yes | yes | no | no | yes |
| animatediff | yes | yes | yes | yes | yes | yes | yes | yes | yes | no | no | yes |

## Reading the matrix

- **Image models** carry no animation backend of their own (the video
  model supplies it); **video models** carry no upscaler/refiner by
  definition.
- **ControlNet** is the main conditioning differentiator: the FLUX family
  and the SDXL family (sdxl, juggernaut-xl, realvis-xl) support canny /
  depth / lineart conditioning; qwen-image, gpt-image and hiredream are
  text-to-image models with no ControlNet.
- **IPAdapter** (style transfer) is available on every family except
  gpt-image and the video models — the Model Director activates it only
  for hero scenes, and only when the chosen model supports it.
- **Segmentation (SAM)** and **SDXL refiner** are SDXL-family-only.
- **Depth** strategies are supported by the FLUX / SDXL families, WAN and
  AnimateDiff.
- Every model supports 9:16 vertical; the SDXL family additionally
  supports 1:1 and 4:5, WAN supports 16:9.

The matrix is enforced at selection time: `_compile_plan` runs
`check_model` on every proposed parameter set and hard-fails on any
violation, so no incompatible plan can ever reach a backend adapter.
