Safe word: "context drift" -> Stop, acknowledge the violation, propose fix.
Project-specific AI instructions are canonical for repo behavior. This file is a thin bootstrap plus hard-stop overrides.
Edit authorization is mandatory: no file edits until the user gives explicit approval in a prior turn. A proposal turn must end with a question or waiting statement. No file edit tool may be called in the same turn as a proposal.
Never use closure language ("locked", "finalized", "confirmed") — use plain declarative statements only.
Commits execute ON COMMAND only. Trigger phrase: "commit per protocol". Never run git commit or git push without that exact phrase in the user's message.
