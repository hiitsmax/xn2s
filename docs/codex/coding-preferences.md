# Coding Preferences

This note captures general coding preferences as reusable principles.

The rules are meant to stay broad and portable. The examples are intentionally concrete and come from one real refactor session so the preferences stay grounded in actual code decisions.

## Name Things By Their Real Responsibility

Names should describe what a module, class, or function truly does, not what we wish it might become later.

### Wrong

```python
# agents.py
class OpenAIDigestAgent:
    def run(self, *, prompt: str, payload: dict, schema: type[BaseModel]) -> BaseModel:
        ...
```

### Right

```python
# llm.py
class DigestLLM:
    def run(self, *, prompt: str, payload: dict, schema: type[BaseModel]) -> BaseModel:
        ...
```

### Why

The original class was not planning, using tools, keeping memory, or choosing actions. It was simply wrapping model calls and returning structured output. Calling it `DigestLLM` tells the truth and prevents fake architecture from leaking into the codebase.

## Make Control Flow Obvious At First Read

A pipeline should read like the actual runtime sequence. A reader should be able to understand the whole flow by opening one file and scanning top to bottom.

### Wrong

```python
def run_digest_report(...):
    threads = _load(...)
    categorized = _run_categorization_step(threads)
    filtered = _run_filter_step(categorized)
    processed = _run_processing_step(filtered)
```

### Right

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

### Why

The second version makes the execution story visible immediately. The file becomes an orchestrator instead of a puzzle, and the reader does not need to chase wrappers to discover what really happens.

## Avoid Indirection That Adds No Meaning

If a wrapper function does nothing except forward arguments, it is usually noise.

### Wrong

```python
def _run_filter_step(*, llm, taxonomy, threads):
    return filter_threads.run(
        llm=llm,
        taxonomy=taxonomy,
        threads=threads,
    )
```

### Right

```python
from .steps.filter_threads import run as filter_threads


filtered_threads = filter_threads(
    llm=digest_llm,
    taxonomy=taxonomy,
    threads=categorized_threads,
)
```

### Why

The wrapper introduced another name, another jump, and another place to read without adding behavior, safety, logging, validation, or transformation. Direct composition is better when the wrapper contributes nothing.

## Split Files By Real Responsibility

Files should be organized by what kind of work they own, not by generic habits or accidental accumulation.

### Wrong

```python
# pipeline.py
def load_taxonomy(...): ...
def write_json(...): ...
def virality_score(...): ...
def render_digest(...): ...
def run_digest_report(...): ...
```

### Right

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

### Why

The corrected split makes each file honest about its role. `pipeline.py` orchestrates, `helpers.py` supports shared mechanics, and `render_digest.py` is a first-class step in the pipeline rather than a hidden side function.

## Keep Shared Data Contracts Separate From Workflow Logic

Data shapes should live in a neutral place when they are reused across multiple layers of behavior.

### Wrong

```python
# pipeline.py
class ThreadProcessResult(BaseModel):
    headline: str
    main_claim: str
    signal_score: int
```

### Right

```python
# schemas/digest.py
class ThreadProcessResult(BaseModel):
    headline: str
    main_claim: str
    signal_score: int
```

### Why

Schemas are contracts. They should not be buried inside one orchestrator file as if they belonged only to that workflow. Putting them in a dedicated schema module makes their role clearer and reduces coupling between behavior and structure.

## Name Operations From The Object Being Processed

Step names should reflect what is being operated on from the user’s point of view.

### Wrong

```python
# extract_signals.py
def run(...): ...
```

### Right

```python
# process_threads.py
def run(...): ...
```

### Why

The actual operation is processing a thread and returning a structured thread-level result. Signal extraction may be part of that result, but it is not the whole operation. The better name keeps the pipeline aligned with the object the user actually thinks about.

## Start From The Real Input Contract

Build from the artifact the system already has instead of inventing extra preparation layers too early.

### Wrong

```python
selected_entries = select_entries(...)
candidates = assemble_candidates(selected_entries)
units = build_units(candidates)
threads = normalize_units(units)
```

### Right

```python
threads = load_threads(timeline_file=timeline_file)
categorized_threads = categorize_threads(
    llm=digest_llm,
    taxonomy=taxonomy,
    threads=threads,
)
```

### Why

The simpler version begins from the actual artifact already produced upstream. It removes pre-pipeline complexity that makes the system harder to follow before that complexity has earned its place.

## Add Abstraction Only After The Problem Exists

Abstraction should respond to recurring pressure in the code, not speculative future needs.

### Wrong

```python
class BackendProtocol(Protocol):
    ...


class AgentRegistry:
    ...


class DigestRuntime:
    ...
```

### Right

```python
class DigestLLM:
    def run(self, *, prompt: str, payload: Any, schema: type[BaseModel]) -> BaseModel:
        ...


def run_digest_report(...):
    ...
```

### Why

The smaller design is easier to change while the feature is still young. Extra layers may look sophisticated, but they slow down reading, naming, and refactoring when the underlying workflow is still simple and unstable.

## Put Semantic Intelligence Where It Actually Lives

When a system uses an LLM, the role and reasoning should live in the modules that define the step behavior, not in the transport layer.

### Wrong

```python
class DigestLLM:
    def categorize_threads(...): ...
    def filter_threads(...): ...
    def process_threads(...): ...
    def group_issues(...): ...
```

### Right

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

### Why

The step file owns the semantic role, the prompt, and the output meaning. The LLM wrapper should remain a thin interface for structured model calls. This keeps intelligence in the step and mechanics in the transport.

## Treat Readability As Architecture

Readability is not a cosmetic concern. It determines how safely the code can evolve.

### Wrong

```python
# pipeline.py
def run_digest_report(...): ...
def render_digest(...): ...
def load_taxonomy(...): ...
def slugify_issue(...): ...
def virality_score(...): ...
def write_json(...): ...
```

### Right

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

### Why

When a file says too many things at once, it becomes harder to change without fear. Separating orchestration, shared helpers, and concrete steps is an architectural improvement because it reduces cognitive load and makes future edits more predictable.
