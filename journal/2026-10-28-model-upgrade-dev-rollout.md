# Model upgrade — dev rollout (2026-10-28)

The owner requested the accepted evaluation choices be applied to the dev
pipeline. The dev Lambdas deploy from `dev`; production Lambdas deploy from
`main`, so this feature branch can be merged to `dev` for staging without
changing the deployed production revision.

## Runtime changes

- Set the orientation default to `claude-haiku-5-5` and use the evaluated
  request settings: `max_tokens=256`, thinking disabled, and Anthropic JSON
  schema output for the existing orientation response shape.
- Set the glare default to `gpt-image-2.5-sunburst`. Omit `input_fidelity`, as
  in the accepted Flare-versus-Sunburst evaluation. Keep one output per edit
  request and preserve the existing OpenCV fallback and retry behavior.
- Update runtime descriptions and pipeline documentation to name the selected
  models.

The model decisions refer to `orientation-object-180-20261028` and
`glare-flare-vs-sunburst-full-20261028`, recorded in the preceding evaluation
journals. The orientation acceptance includes a missed rotated-case threshold;
the glare comparison had one preference per crop, so dev observation remains
part of rollout review.

This change is scoped to the dev deployment until separately merged from `dev`
to `main`. The offline unit test suite was not run in this phase. The PR review
and CI results will be recorded after implementation checks.
