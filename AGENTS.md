# MUST
Keep the same coding style of the project when making edits and creating new features.

# THE OBJECTIVE
Implement, by step, a cli tool (great for cron scheduling for example) with an agentic pipeline that lets me create a whole digest from the latest twitts on the platform

# CODING PREFERENCES
These rules are general and portable.
The examples below use Python because the current repository is Python-first, but the preferences apply across languages and across backend, frontend, scripts, automation, and infrastructure work.

- Name things by their real job.
  You MUST use names that describe what the code actually does today.
  You MUST NOT use inflated names for simple modules.
  If something is only a model wrapper, call it `llm`, `model`, or another honest name.
  If something is not acting as an agent, you MUST NOT call it an agent.

  Wrong:
  ```python
  # agents.py
  class OpenAIDigestAgent:
      def run(self, *, prompt: str, payload: dict, schema: type[BaseModel]) -> BaseModel:
          ...
  ```

  Right:
  ```python
  # llm.py
  class DigestLLM:
      def run(self, *, prompt: str, payload: dict, schema: type[BaseModel]) -> BaseModel:
          ...
  ```

  Why: this component only wrapped model calls. It did not plan, use tools, or manage memory.

- Keep control flow obvious.
  You MUST make orchestration readable at first glance.
  A pipeline file SHOULD read top-to-bottom like the real runtime order.
  You SHOULD prefer direct step calls over hidden wrappers when the flow is simple.

  Wrong:
  ```python
  def run_digest_report(...):
      threads = _load(...)
      categorized = _run_categorization_step(threads)
      filtered = _run_filter_step(categorized)
      processed = _run_processing_step(filtered)
  ```

  Right:
  ```python
  from .steps.load_threads import run as load_threads
  from .steps.categorize_threads import run as categorize_threads
  from .steps.filter_threads import run as filter_threads
  from .steps.process_threads import run as process_threads
  from .steps.group_issues import run as group_issues
  from .steps.render_digest import run as render_digest

  def run_digest_report(...):
      threads = load_threads(...)
      categorized_threads = categorize_threads(...)
      filtered_threads = filter_threads(...)
      processed_threads = process_threads(...)
      issue_threads, issues = group_issues(...)
      digest_markdown = render_digest(...)
  ```

  Why: a reader should understand the feature by opening one file, not by chasing indirection.

- Do not keep wrappers that add no value.
  You MUST NOT add pass-through functions that only rename or forward a call.
  You MAY keep a wrapper only if it adds real behavior such as validation, logging, retries, transformation, or error handling.

  Wrong:
  ```python
  def _run_filter_step(*, llm, taxonomy, threads):
      return filter_threads.run(
          llm=llm,
          taxonomy=taxonomy,
          threads=threads,
      )
  ```

  Right:
  ```python
  from .steps.filter_threads import run as filter_threads

  filtered_threads = filter_threads(
      llm=digest_llm,
      taxonomy=taxonomy,
      threads=categorized_threads,
  )
  ```

  Why: extra wrappers create more names and more places to read without improving behavior.

- Split files by responsibility.
  You MUST keep orchestration, shared helpers, schemas, and concrete step behavior in separate modules when they serve different roles.
  If something is a real step, make it a real step module.
  You MUST NOT let one file become a junk drawer.

  Wrong:
  ```python
  # pipeline.py
  def load_taxonomy(...): ...
  def write_json(...): ...
  def virality_score(...): ...
  def render_digest(...): ...
  def run_digest_report(...): ...
  ```

  Right:
  ```python
  # helpers.py
  def load_taxonomy(...): ...
  def write_json(...): ...
  def virality_score(...): ...

  # steps/render_digest.py
  def run(...): ...

  # pipeline.py
  def run_digest_report(...): ...
  ```

  Why: the file boundaries should tell the truth about ownership.

- Keep shared schemas out of workflow files.
  Reusable data contracts MUST live in a neutral schema module.
  You MUST NOT bury shared Pydantic models inside pipeline code unless they are truly local.

  Wrong:
  ```python
  # pipeline.py
  class ThreadProcessResult(BaseModel):
      headline: str
      main_claim: str
      signal_score: int
  ```

  Right:
  ```python
  # schemas/digest.py
  class ThreadProcessResult(BaseModel):
      headline: str
      main_claim: str
      signal_score: int
  ```

  Why: schemas are shared contracts, not implementation details of one orchestrator.

- Name steps from the object being processed.
  You SHOULD use names that match the user's mental model.
  You MUST NOT name a whole step after only one sub-part of its output if that distorts the actual operation.

  Wrong:
  ```python
  # extract_signals.py
  def run(...): ...
  ```

  Right:
  ```python
  # process_threads.py
  def run(...): ...
  ```

  Why: the real operation was processing a thread, not merely extracting one field from it.

- Start from the real system contract.
  If an upstream artifact already exists, you SHOULD build from that artifact directly.
  You MUST NOT invent pre-pipeline stages unless the current problem clearly requires them.

  Wrong:
  ```python
  selected_entries = select_entries(...)
  candidates = assemble_candidates(selected_entries)
  units = build_units(candidates)
  threads = normalize_units(units)
  ```

  Right:
  ```python
  threads = load_threads(timeline_file=timeline_file)
  categorized_threads = categorize_threads(
      llm=digest_llm,
      taxonomy=taxonomy,
      threads=threads,
  )
  ```

  Why: the simpler design starts from the real input instead of manufacturing extra architecture.

- Add abstraction only when the code earns it.
  You SHOULD introduce protocols, registries, and runtime layers only after repeated pressure makes them useful.
  You MUST NOT add speculative abstractions to a still-simple feature.

  Wrong:
  ```python
  class BackendProtocol(Protocol):
      ...

  class AgentRegistry:
      ...

  class DigestRuntime:
      ...
  ```

  Right:
  ```python
  class DigestLLM:
      def run(self, *, prompt: str, payload: Any, schema: type[BaseModel]) -> BaseModel:
          ...

  def run_digest_report(...):
      ...
  ```

  Why: early abstraction often makes young code harder to read and easier to misname.

- Keep semantic behavior in the step, not in the transport.
  If a step owns the role, prompt, and output meaning, that step is where the semantic logic belongs.
  The LLM wrapper SHOULD stay thin and mechanical.

  Wrong:
  ```python
  class DigestLLM:
      def categorize_threads(...): ...
      def filter_threads(...): ...
      def process_threads(...): ...
      def group_issues(...): ...
  ```

  Right:
  ```python
  # steps/categorize_threads.py
  def run(*, llm, taxonomy, threads):
      for thread in threads:
          result = llm.run(
              prompt=CATEGORIZE_PROMPT,
              payload={"thread": thread, "taxonomy": taxonomy},
              schema=CategorizationResult,
          )

  # llm.py
  class DigestLLM:
      def run(self, *, prompt: str, payload: Any, schema: type[BaseModel]) -> BaseModel:
          ...
  ```

  Why: the step defines the meaning; the wrapper only transports the request to the model.

- Treat readability as architecture.
  You MUST treat readability as a design constraint.
  If a file is hard to scan, hard to trust, or hard to modify, you SHOULD treat that as an architectural problem.

  Wrong:
  ```python
  # pipeline.py
  def run_digest_report(...): ...
  def render_digest(...): ...
  def load_taxonomy(...): ...
  def slugify_issue(...): ...
  def virality_score(...): ...
  def write_json(...): ...
  ```

  Right:
  ```python
  # pipeline.py
  def run_digest_report(...): ...

  # helpers.py
  def load_taxonomy(...): ...
  def slugify_issue(...): ...
  def virality_score(...): ...
  def write_json(...): ...

  # steps/render_digest.py
  def run(...): ...
  ```

  Why: clearer ownership makes future edits safer.

# PREFERENCE CAPTURE WORKFLOW
- When I give feedback that reflects a broader coding preference, not just a one-off correction, you MUST treat it as a possible reusable rule.
- You MUST check for this especially around naming, file boundaries, abstraction level, control flow, schema placement, readability, test style, and documentation style.
- Before closing the task, you MUST ask whether I want that preference captured in the coding-preferences note.
- You MUST use one short and explicit question.
- You MUST NOT silently add the rule without my approval.
- You MUST NOT assume every correction deserves documentation.
- You MUST distinguish between a local fix and a general preference.

If I approve, you MUST capture the preference in this format:
1. General rule
2. Wrong example
3. Right example
4. Why the corrected version is preferred

You SHOULD keep the rule general.
You SHOULD keep repository-specific detail only inside the examples.
You SHOULD ask while the preference is still fresh.

Preferred question:
"This looks like a reusable coding preference, not just a local fix. Do you want me to add it to the coding-preferences note while it's fresh?"
