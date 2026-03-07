# Agentic Digest Brainstorm

## Decisions

- Goal: build a cron-friendly CLI pipeline that turns downloaded X tweets into a high-signal markdown digest that reads like a magazine issue.
- V1 output: markdown only.
- Later ideas, explicitly deferred: convert the markdown issue to LaTeX and/or send it by email on a schedule.
- Traceability is required from the start: each digest section should point back to the underlying tweet and thread URLs.
- We are taking baby steps: no Langfuse yet, but the design should leave room for tracing later.
- Keep the pipeline simple: separate steps with file handoffs instead of one shared graph state.
- Each step can still be agentic on its own.
- Categorization should come before filtering.
- Filtering is policy-driven: for example, items categorized as low-value noise such as "unnecessary AI slop" can be dropped after categorization.
- We chose a wide-net approach first: categorize broadly, then filter more carefully.
- Category taxonomy should be fixed and editable rather than fully emergent.
- The main analysis unit is not a single tweet but a thread or conversation unit.
- A self-thread such as `1/5` through `5/5` should be treated like one logical tweet.
- If a thread is valuable, the final digest can still highlight one or more individual tweets inside it.
- Replies matter as context: include replies the thread author answers to.
- Standout external replies also matter: include the most important outside replies.
- Standout replies should be selected with a proportional virality threshold across the reply set, for example `p95`, rather than a fixed hard number.
- Virality should use all available engagement signals: likes, retweets, replies, quotes, and views.
- The reporting window should be hybrid and configurable.
- The hybrid default idea is: process fresh tweets since the last run, while also revisiting threads previously marked as heated.
- Heated-thread tracking should persist lightweight memory across runs so the next run can detect how the conversation moved.
- Heated detection should combine both activity/momentum and disagreement/polarization.
- Heated detection behavior should be configurable, including prompt behavior and structured output shape.
- Use the LLM for anything that is not directly trackable from numbers alone.
- Numeric/mechanical operations can stay deterministic, for example reply percentile thresholds and engagement math.
- Thread assembly should also use the LLM, not only rigid deterministic rules.
- A practical boundary is still useful: code can gather candidate context cheaply, and the LLM decides the final narrative/conversation unit.

## Still Open

- Final editorial structure of the markdown issue is still open.
- Exact top-level category list is still open.
- Exact persistence format for intermediate step outputs is still open.
- Exact model/provider choice for the Python pipeline is still open.
