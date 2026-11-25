# BALAI OS — Codex Project Bridge

This project uses `.agent/` as its only full BALAI OS source. User-global
`~/.codex/skills/workflow-prompts/` may contain thin BALAI workflow dispatchers for visible
Codex commands, but never a second BALAI workflow, skill, persona, or protocol
body.

- For BALAI policy, read `.agent/global_instructions.md` when the task needs it.
- For a BALAI skill, read the exact relevant `.agent/skills/**/SKILL.md` source.
- If the user invokes `/name` or asks for a BALAI workflow, load and follow
  `.agent/workflows/<name>.md`. A global dispatcher is only a visible Codex
  command pointer: read that exact project file directly without running a
  resolver script. Never fall back to a global workflow body.
- For software, product, design, architecture, planning, or implementation
  requests, treat `clarify`, `clarification`, `/clarify`, and `/interview` as a
  request to load `.agent/workflows/clarify.md`. Also load it before proceeding
  when a material ambiguity, contradiction, or unapproved hidden scope would
  change the implementation boundary. Do not route ordinary explanation or
  writing requests through it merely because they use the word “clarify.”
- Read supporting personas, protocols, decisions, or adapters directly from
  `.agent/` only when they are relevant to the task.

This bridge deliberately contains no copied workflow, skill, persona, or
protocol body. Keep `.agent/` canonical.
