---
name: eval-creator
description: "Create new eval suites for the deepagentsjs monorepo. Handles dataset design, test case creation, scoring strategies, and LangSmith integration. Use when the user asks to: (1) create an eval, (2) add an eval suite, (3) write evals for a feature, (4) benchmark agent behavior, (5) add evaluation tests, (6) create a test dataset, or (7) implement an eval from a paper/benchmark. Trigger on phrases like 'create eval', 'add eval', 'write evals', 'benchmark', 'evaluation suite', 'eval dataset', or 'implement X benchmark'."
---

# Eval Creator

Create new eval suites for the `deepagentsjs` monorepo. This skill covers
the full lifecycle: designing the dataset, structuring the workspace package,
writing test cases, choosing scoring strategies, and integrating with LangSmith
for experiment tracking.

## Prerequisites

Before starting, read the existing eval infrastructure:

```
internal/eval-harness/README.md   — harness architecture
evals/README.md                   — how to run evals, conventions
```

## Architecture Overview

```
internal/eval-harness/          The harness package (@deepagents/evals)
├── src/index.ts                EvalRunner interface, registry, matchers
├── src/deepagent.ts            DeepAgent runner implementation
└── src/setup.ts                Registers all model runners

evals/                          Each subdirectory is an independent eval suite
├── basic/                      System prompt, simple reasoning
├── files/                      File operations (read, write, edit, grep, glob)
├── subagents/                  Subagent delegation via task tool
└── <your-new-eval>/            ← you create this
```

Each eval suite is a standalone pnpm workspace package. Vitest runs the
tests, `langsmith/vitest` tracks results as LangSmith experiments, and
`@deepagents/evals` provides the runner and matchers.

## Workflow

### Step 1 — Understand the eval requirements

Before writing any code, clarify:

1. **What capability is being evaluated?** (e.g. multi-turn memory, tool
   selection accuracy, instruction following, code generation quality)
2. **Where do test cases come from?**
   - Hand-authored inline (simple cases)
   - Generated programmatically (combinatorial, templated)
   - External dataset (JSON/JSONL file, API, paper benchmark)
3. **How should results be scored?**
   - Trajectory shape (step count, tool call count) — use built-in matchers
   - Text content matching — use `toHaveFinalTextContaining` or `getFinalText`
   - File output validation — inspect `result.files`
   - Custom evaluator (LLM-as-judge, semantic similarity) — use `ls.logFeedback`
   - External scoring function — use `ls.wrapEvaluator`
4. **Does the agent need custom configuration per test?**
   - Custom system prompt → `runner.extend({ systemPrompt })`
   - Custom tools → `runner.extend({ tools })`
   - Custom subagents → `runner.extend({ subagents })`
   - Seed files → `runner.run({ initialFiles })`

### Step 2 — Create the workspace package

Create a new directory under `evals/`:

```
evals/<eval-name>/
├── package.json
├── vitest.config.ts
├── index.test.ts
└── README.md
```

#### `package.json`

```json
{
  "name": "@deepagents/eval-<eval-name>",
  "private": true,
  "type": "module",
  "scripts": {
    "test:eval": "vitest run"
  },
  "dependencies": {
    "@deepagents/evals": "workspace:*",
    "deepagents": "workspace:*",
    "langsmith": "^0.5.4",
    "vitest": "^4.0.18"
  }
}
```

Add extra dependencies as needed (e.g. `zod` for tool schemas, `langchain`
for `tool()` helper, dataset loaders, etc.).

#### `vitest.config.ts`

Always use this exact template:

```ts
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: false,
    testTimeout: 120_000,
    hookTimeout: 60_000,
    teardownTimeout: 60_000,
    include: ["**/*.test.ts"],
    setupFiles: ["@deepagents/evals/setup"],
    reporters: ["default", "langsmith/vitest/reporter"],
  },
});
```

Key points:
- `setupFiles: ["@deepagents/evals/setup"]` registers all model runners
  before tests run.
- `reporters: ["langsmith/vitest/reporter"]` streams results to LangSmith.
- `testTimeout: 120_000` — agent calls are slow; 2 minutes per test is the default.
  Increase for complex multi-turn evals.

#### `README.md`

One-liner description of what the eval suite covers.

```md
# <eval-name>

<Brief description of what this suite evaluates and why.>
```

If the eval is based on a published benchmark, include attribution:

```md
Based on [Paper/Benchmark Name](https://link) by Author et al., YYYY.
```

### Step 3 — Write the test file

#### Basic structure

```ts
import * as ls from "langsmith/vitest";
import { expect } from "vitest";
import { getDefaultRunner } from "@deepagents/evals";

const runner = getDefaultRunner();

ls.describe(
  runner.name,
  () => {
    // test cases go here
  },
  { projectName: "deepagents-js-<eval-name>", upsert: true },
);
```

**Conventions:**
- `ls.describe` name = `runner.name` (e.g. `"sonnet-4-5"`). This becomes
  the LangSmith dataset name.
- `projectName` = `"deepagents-js-<eval-name>"`. This is the LangSmith
  tracing project. Use `upsert: true` so it creates-or-reuses.
- One `ls.describe` block per test file.

#### Inline test cases

For hand-authored cases where inputs are known at write time:

```ts
ls.test(
  "descriptive test name",
  {
    inputs: { query: "the user message" },
    referenceOutputs: { expectedText: "expected substring" },
  },
  async ({ inputs, referenceOutputs }) => {
    const result = await runner.run({ query: inputs.query });

    expect(result).toHaveAgentSteps(2);
    expect(result).toHaveToolCallRequests(1);
    expect(result).toHaveFinalTextContaining(
      referenceOutputs!.expectedText,
    );
  },
);
```

`inputs` and `referenceOutputs` are stored in LangSmith as the dataset
example. The test function receives them as arguments.

#### Data-driven test cases with `ls.test.each`

For datasets with many examples, use `ls.test.each`:

```ts
const dataset = [
  {
    inputs: { query: "What is 2+2?" },
    referenceOutputs: { answer: "4" },
  },
  {
    inputs: { query: "What is 3*3?" },
    referenceOutputs: { answer: "9" },
  },
];

ls.test.each(dataset)(
  "arithmetic: %s",
  async ({ inputs, referenceOutputs }) => {
    const result = await runner.run({ query: inputs.query });
    expect(result).toHaveFinalTextContaining(referenceOutputs!.answer);
  },
);
```

#### Loading external datasets

For benchmarks from papers or large datasets, load from a JSON/JSONL file:

```ts
import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const raw = JSON.parse(
  readFileSync(resolve(__dirname, "dataset.json"), "utf-8"),
);

// Transform into ls.test.each format
const dataset = raw.map((item: any) => ({
  inputs: { query: item.instruction },
  referenceOutputs: { expected: item.expected_output },
}));

ls.test.each(dataset)(
  "benchmark case",
  async ({ inputs, referenceOutputs }) => {
    const result = await runner.run({ query: inputs.query });
    // ... assertions
  },
);
```

For very large datasets, consider slicing or sampling:

```ts
// Run only first 50 cases (or use EVAL_SAMPLE_SIZE env var)
const sampleSize = parseInt(process.env.EVAL_SAMPLE_SIZE ?? "50");
const sampled = dataset.slice(0, sampleSize);
ls.test.each(sampled)("case", async ({ inputs }) => { /* ... */ });
```

#### Loading from a vitest setup file

For datasets that need async loading (API calls, database reads), use a
vitest setup file specific to the eval:

```ts
// evals/<eval-name>/vitest.setup.ts
import { readFile } from "node:fs/promises";

// Make dataset available globally
const raw = await readFile(new URL("./dataset.json", import.meta.url), "utf-8");
(globalThis as any).__EVAL_DATASET__ = JSON.parse(raw);
```

Then reference in `vitest.config.ts`:

```ts
export default defineConfig({
  test: {
    // ...
    setupFiles: [
      "@deepagents/evals/setup",     // registers runners
      "./vitest.setup.ts",            // loads dataset
    ],
  },
});
```

And consume in the test file:

```ts
const dataset = (globalThis as any).__EVAL_DATASET__ as Array<{
  instruction: string;
  expected: string;
}>;

const cases = dataset.map((d) => ({
  inputs: { query: d.instruction },
  referenceOutputs: { expected: d.expected },
}));

ls.test.each(cases)("case", async ({ inputs, referenceOutputs }) => {
  // ...
});
```

### Step 4 — Configure the agent per test

#### Using `runner.extend()` for agent configuration

`extend()` creates a derived runner with configuration overrides baked in.
Use it when a test needs a different agent configuration than the default.
`run()` only takes invocation params (`query`, `initialFiles`).

```ts
// Custom system prompt
const result = await runner
  .extend({ systemPrompt: "You are a Python expert." })
  .run({ query: "Write a fibonacci function." });

// Custom tools
import { tool } from "langchain";
import { z } from "zod/v4";

const calculator = tool(
  async ({ expression }) => String(eval(expression)),
  {
    name: "calculator",
    description: "Evaluate a math expression",
    schema: z.object({ expression: z.string() }),
  },
);

const result = await runner
  .extend({ tools: [calculator] })
  .run({ query: "What is 127 * 389?" });

// Custom subagents
const result = await runner
  .extend({
    subagents: [{
      name: "researcher",
      description: "Research a topic",
      systemPrompt: "You are a research agent.",
      tools: [searchTool],
    }],
  })
  .run({ query: "Research quantum computing." });
```

#### Seed files via `initialFiles`

Pre-populate the agent's file system:

```ts
const result = await runner.run({
  query: "Read /data.csv and summarise the results.",
  initialFiles: {
    "/data.csv": "name,score\nalice,95\nbob,87\ncharlie,92\n",
  },
});
```

### Step 5 — Score and assert

#### Built-in trajectory matchers

These matchers also log LangSmith feedback automatically:

| Matcher | Description |
| --- | --- |
| `toHaveAgentSteps(n)` | Exact step count |
| `toHaveToolCallRequests(n)` | Total tool-call count |
| `toHaveToolCallInStep(step, match)` | Tool call in step (1-indexed) matches `{ name, argsContains?, argsEquals? }` |
| `toHaveFinalTextContaining(text, caseInsensitive?)` | Final response contains text |

```ts
expect(result).toHaveAgentSteps(2);
expect(result).toHaveToolCallRequests(1);
expect(result).toHaveToolCallInStep(1, {
  name: "write_file",
  argsContains: { file_path: "/output.md" },
});
expect(result).toHaveFinalTextContaining("done", true);
```

#### `getFinalText` for custom assertions

```ts
import { getFinalText } from "@deepagents/evals";

const text = getFinalText(result);
expect(text).toMatch(/\d+/); // contains a number
```

#### File output assertions

```ts
// Check file exists and contains expected content
expect(result.files["/output.json"]).toBeDefined();
const parsed = JSON.parse(result.files["/output.json"]);
expect(parsed.status).toBe("success");
```

#### Manual LangSmith feedback

For scores that don't map to pass/fail assertions:

```ts
import * as ls from "langsmith/vitest";

// Numeric score
ls.logFeedback({ key: "relevance", score: 0.9 });

// Boolean score
ls.logFeedback({ key: "contains_answer", score: 1 });

// With comment
ls.logFeedback({
  key: "quality",
  score: 0.7,
  comment: "Answer is correct but verbose",
});
```

#### LLM-as-judge evaluators

For subjective quality assessment, use `ls.wrapEvaluator` to run an
LLM judge. The evaluator runs are traced separately to avoid polluting
the agent trace.

```ts
import * as ls from "langsmith/vitest";
import { ChatAnthropic } from "@langchain/anthropic";

const judge = new ChatAnthropic({ model: "claude-sonnet-4-5-20250929" });

const evaluateHelpfulness = ls.wrapEvaluator(
  async ({ inputs, outputs, referenceOutputs }) => {
    const response = await judge.invoke([
      {
        role: "system",
        content:
          "Rate the helpfulness of the response on a scale of 0-1. " +
          "Return JSON: { score: number, comment: string }",
      },
      {
        role: "user",
        content: `Question: ${inputs.query}\nExpected: ${referenceOutputs.expected}\nActual: ${outputs.answer}`,
      },
    ]);
    const parsed = JSON.parse(response.content as string);
    return {
      key: "helpfulness",
      score: parsed.score,
      comment: parsed.comment,
    };
  },
);

ls.test("helpful response", { inputs: { query: "..." } }, async ({ inputs }) => {
  const result = await runner.run({ query: inputs.query });
  const answer = getFinalText(result);

  // This automatically logs feedback to LangSmith
  await evaluateHelpfulness({
    inputs: { query: inputs.query },
    outputs: { answer },
    referenceOutputs: { expected: "..." },
  });
});
```

#### The `evaluatedBy` matcher chain

For inline evaluator assertions:

```ts
import * as ls from "langsmith/vitest";

ls.test("quality check", { inputs: { query: "..." } }, async ({ inputs }) => {
  const result = await runner.run({ query: inputs.query });
  const answer = getFinalText(result);

  // Chains: run evaluator, then assert on score
  await ls.expect({ answer }).evaluatedBy(myEvaluator).toBeGreaterThan(0.5);
});
```

### Step 6 — Complex eval patterns

#### Multi-turn conversations

For evals that require multiple exchanges, invoke the agent multiple times
on the same thread. Use a checkpointer in `extend()`:

```ts
import { MemorySaver } from "@langchain/langgraph";

const checkpointer = new MemorySaver();
const conversational = runner.extend({ checkpointer });

// Turn 1
const r1 = await conversational.run({ query: "My name is Alice." });
// Turn 2 (same thread — the runner uses a fresh thread_id per run(),
// so for multi-turn you need a custom runner or invoke directly)
```

> **Note:** The default `DeepAgentEvalRunner` creates a new `thread_id`
> per `run()` call. For multi-turn evals requiring persistent state across
> turns, you may need to implement a custom `EvalRunner` or invoke the
> agent directly.

#### Benchmark attribution

When implementing an eval based on a published benchmark, always include
proper attribution in both the README and inline comments:

```md
<!-- README.md -->
# memory-bench

Long-term memory retrieval evaluation.

Based on [MemoryAgentBench](https://arxiv.org/abs/XXXX.XXXXX) by Author et al., YYYY.
Licensed under [LICENSE]. Dataset source: [URL].
```

```ts
// index.test.ts
// Eval based on MemoryAgentBench (Author et al., YYYY)
// https://arxiv.org/abs/XXXX.XXXXX
// Dataset: https://github.com/...
```

#### Parameterised difficulty levels

Use `split` to tag test cases by difficulty in LangSmith:

```ts
ls.test(
  "easy case",
  {
    inputs: { query: "What is 2+2?" },
    referenceOutputs: { answer: "4" },
    split: "easy",
  },
  async ({ inputs }) => { /* ... */ },
);

ls.test(
  "hard case",
  {
    inputs: { query: "Prove Fermat's Last Theorem." },
    split: "hard",
  },
  async ({ inputs }) => { /* ... */ },
);
```

Or with `ls.test.each`:

```ts
const cases = [
  { inputs: { query: "..." }, referenceOutputs: { answer: "..." }, split: "easy" },
  { inputs: { query: "..." }, referenceOutputs: { answer: "..." }, split: "hard" },
];

ls.test.each(cases)("case", async ({ inputs }) => { /* ... */ });
```

#### Repetitions for statistical significance

Run each test case multiple times to measure variance:

```ts
ls.test(
  "flaky test",
  {
    inputs: { query: "Be creative." },
    config: { repetitions: 5 },
  },
  async ({ inputs, testMetadata }) => {
    console.log(`Repetition ${testMetadata.repetition} of 5`);
    const result = await runner.run({ query: inputs.query });
    // ...
  },
);
```

### Step 7 — Finalise

1. **Run `pnpm install`** from the repo root to link the new workspace.

2. **Verify the eval runs:**

   ```bash
   EVAL_RUNNER=sonnet-4-5 pnpm --filter @deepagents/eval-<name> test:eval
   ```

3. **Check LangSmith** — verify the dataset, experiment, and feedback
   appear correctly at https://smith.langchain.com.

4. **Add to CI** (optional) — the root `pnpm test:eval` already picks up
   all `evals/*` packages via the workspace filter.

## Reference

### Harness exports (`@deepagents/evals`)

| Export | Description |
| --- | --- |
| `getDefaultRunner()` | Returns the runner for `EVAL_RUNNER` env var (cached) |
| `resolveRunner(name)` | Look up a runner by name |
| `registerRunner(runner)` | Register an `EvalRunner` instance |
| `parseTrajectory(messages, files?)` | Parse LangGraph output into `AgentTrajectory` |
| `getFinalText(trajectory)` | Extract text from the last step |
| `AgentStep` | Interface: `{ index, action: AIMessage, observations: ToolMessage[] }` |
| `AgentTrajectory` | Interface: `{ steps: AgentStep[], files: Record<string, string> }` |
| `RunAgentParams` | Interface: `{ query: string, initialFiles?: Record<string, string> }` |
| `EvalRunner` | Interface: `{ name, run(params), extend(overrides) }` |

### Deepagent runner exports (`@deepagents/evals/deepagent`)

| Export | Description |
| --- | --- |
| `registerDeepAgentRunner(name, factory)` | Register a runner backed by `createDeepAgent` |

### Available runners (from `@deepagents/evals/setup`)

| Name | Model |
| --- | --- |
| `sonnet-4-5` | `claude-sonnet-4-5-20250929` |
| `sonnet-4-5-thinking` | `claude-sonnet-4-5-20250929` with extended thinking |
| `opus-4-6` | `claude-opus-4-6` |
| `gpt-4.1` | `gpt-4.1` |
| `gpt-4.1-mini` | `gpt-4.1-mini` |
| `o3-mini` | `o3-mini` |

### `langsmith/vitest` API

| Function | Description |
| --- | --- |
| `ls.describe(name, fn, config?)` | Define a test suite (= LangSmith dataset). `config.projectName` sets the tracing project. `config.upsert` reuses existing datasets. |
| `ls.test(name, params, fn, timeout?)` | Define a test case (= LangSmith example). `params.inputs` and `params.referenceOutputs` are stored in the dataset. |
| `ls.test.each(table)(name, fn)` | Data-driven tests. Each item in `table` has `{ inputs, referenceOutputs?, split?, metadata? }`. |
| `ls.logFeedback({ key, score, comment? })` | Log a feedback metric for the current test. Appears in LangSmith experiment results. |
| `ls.logOutputs(output)` | Log output for the current test. Overridden if the test function returns a value. |
| `ls.wrapEvaluator(fn)` | Wrap an evaluator function with tracing. Auto-logs `{ key, score }` as feedback. |
| `ls.expect(outputs).evaluatedBy(evaluator)` | Chain: run evaluator on outputs, then assert on the returned score. |

### `CreateDeepAgentParams` (for `runner.extend()`)

The overrides accepted by `extend()` correspond to `CreateDeepAgentParams`
from `deepagents`:

| Field | Type | Description |
| --- | --- | --- |
| `systemPrompt` | `string \| SystemMessage` | Custom system prompt |
| `tools` | `StructuredTool[]` | Tools the agent can use |
| `subagents` | `SubAgent[]` | Subagent specifications for `task` tool |
| `middleware` | `AgentMiddleware[]` | Custom middleware |
| `responseFormat` | `SupportedResponseFormat` | Structured output schema |
| `checkpointer` | `BaseCheckpointSaver \| boolean` | State persistence |
| `store` | `BaseStore` | Long-term memory store |
| `backend` | `BackendProtocol \| Function` | Custom file system backend |
| `memory` | `string[]` | AGENTS.md memory file paths |

### Environment variables

| Variable | Description |
| --- | --- |
| `EVAL_RUNNER` | **Required.** Runner name (e.g. `sonnet-4-5`). |
| `LANGSMITH_API_KEY` | LangSmith API key for experiment tracking. |
| `LANGSMITH_PROJECT` | Override the tracing project (usually set via `projectName` in `ls.describe`). |
| `LANGSMITH_TEST_TRACKING` | Set to `"false"` to disable LangSmith tracking for local-only runs. |
| `ANTHROPIC_API_KEY` | Required for Anthropic runners. |
| `OPENAI_API_KEY` | Required for OpenAI runners. |
