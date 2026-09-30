# Rules for every agent on this repo

Read this before the task. It is short on purpose.

- Never recall a library, signature, enum or figure. Grep the source or the
  stubs, then cite `path:line`. A claim without a hit is UNVERIFIED and says so.
- Three words, used exactly: MEASURED means a script ran and the number is
  from it. SPIKE means a script should run before the claim is trusted.
  UNVERIFIED means neither happened.
- Read the whole body of every symbol you rule on, not the signature.
- Do not read anything under `.agents/`.
- Output is a table or a list with one line per item, in the order given.
  No summary paragraph. Notes after the table for things that are not items.
- Never summarize a document on its way out. Each paragraph gets a named
  destination or an explicit delete.
- Do not start the app. It is probably running.
- The audio device for tests is the one whose description contains
  "USB Audio Device". The PDP device is the app's and stays enumerated
  whether or not anything is attached to it.
