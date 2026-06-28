"""LLM synthesis (spec §4 stage 5 / §5.3): grounded, structured generation only.
Citations API hard-binds quotes to source char spans; a pre-publish verifier
spot-checks. Models: claude-sonnet-4-6 / claude-opus-4-8 (verify ids in docs).
See docs/design/synthesis-and-trust.md.
"""
