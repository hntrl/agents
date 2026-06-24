---
name: cluster-items
description: Workflow for incrementally clustering a list of arbitrary items into themed groups, judged by subagents. Use when the user wants to cluster, group, theme, or categorize a collection of records (issues, tickets, feedback, docs, search results, log lines, anything) by semantic similarity rather than exact match. Trigger on phrases like "cluster these", "group these by theme", "find themes in", "bucket these items", "categorize this list".
module: ./index.ts
---

# Cluster

A reusable clustering engine driven by subagent judgment. You bring a list of
items; `ClusterSet` groups them into themed clusters incrementally, creating
new themes on demand and (optionally) merging overlapping ones. Each placement
decision is made by a subagent dispatched through the `task` global.

## When to use

- You have N records and want them grouped by *semantic theme*, not exact key.
- Themes are not known up front and should emerge from the data.

## Hard Rules

1. Use the `ClusterSet` class from `index.ts` as the clustering engine. Do not
   reimplement queueing/merging/threshold logic in interpreter code.
2. Import directly from this skill directory's `index.ts`, using its absolute
   path on disk. This SKILL.md lives in that directory, so the import target is
   `<dir-of-this-SKILL.md>/index.ts`. For example:
   `import { ClusterSet } from "<dir-of-this-SKILL.md>/index.ts";`
3. Do not read the skill source files and reconstruct the engine inline.
4. The engine calls the ambient `task` global directly to judge each placement,
   so it must exist in the interpreter runtime.
5. Schedule items with `scheduleMany(items)` — `schedule()` only enqueues and
   the engine drains the queue serially, so do not wrap it in concurrency. If
   you must do async work to *build* the items (fetching/condensing source
   records), bound that with the exported `mapWithConcurrency`; never fire an
   unbounded `Promise.all` over a large source list.
6. For internal skill modules, use explicit file extensions in relative imports
   (e.g. `./cluster.ts`).

If the import fails, stop and report the import failure rather than rebuilding
the pipeline ad hoc.

## The item shape

Map every record you want to cluster into this shape:

```ts
type ClusterItem = {
  id: number | string;            // stable identity within its type
  type?: string;                  // optional kind label, defaults to "item"
  text: string;                   // the content the classifier reasons over
  metadata?: Record<string, unknown>; // opaque; carried into the cluster reference
};
```

`text` is what drives clustering — pack whatever is salient into it (title +
short body + labels). `metadata` is never read by the engine; it rides along so
you can inspect or render results later without re-fetching.

## Minimal usage

```ts
// Import from this skill directory's index.ts using its absolute path on disk.
import { ClusterSet } from "<dir-of-this-SKILL.md>/index.ts";

// 1. Map your domain records -> ClusterItem[].
const items = records.map((r) => ({
  id: r.id,
  type: "feedback",
  text: `${r.title}\n${r.summary}`,
  metadata: { url: r.url },
}));

// 2. Create the set and schedule every item.
const clusterSet = new ClusterSet({ domainLabel: "feedback item" });
const assignments = await clusterSet.scheduleMany(items);

// 3. Await the set for a stable snapshot once all in-flight work settles.
const snapshot = await clusterSet;

// snapshot.clusters -> ClusterNode[] (each with name, brief, references[])
// assignments       -> per-item ClusterAssignment (clusterId, confidence, forgotten...)

// 4. Render a markdown report (run stats + a table per cluster).
const report = snapshot.toMarkdown();
```

`schedule()` only enqueues — it pushes the item onto an internal queue that the
engine drains serially (one classification at a time). So you do not bound
concurrency at the scheduling step; `scheduleMany(items)` (or `items.map(i =>
clusterSet.schedule(i))`) is all you need. `await clusterSet` returns a
`ClusterSetSnapshot` and resolves only after the queue has drained *and* no new
work was observed during that drain — so it is safe to schedule while earlier
items are still processing.

## Options

```ts
type ClusterSetOptions = {
  domainLabel?: string;             // phrasing for prompts, default "item"
  similarityThreshold?: number;     // min confidence to route/spawn, default 0.65
  allowNewClusters?: boolean;       // may new themes create clusters, default true
  initialClusters?: ClusterNode[];  // pre-seed clusters (use with allowNewClusters:false)
  reconcileWithClassifier?: boolean;// periodic brief-refresh + merge pass, default false
  reviewEvery?: number;             // items between review passes, default 10
  mergeThreshold?: number;          // min confidence to merge clusters, default 0.75
  maxClusterRefsInPrompt?: number;  // refs shown per cluster in prompts, default 8
  subagentType?: string;            // subagent dispatched via task(), default "general-purpose"
};
```

### Common configurations

- **Discover themes from scratch** (default): `new ClusterSet()`. New clusters
  are created whenever no existing theme clears `similarityThreshold`.
- **Fixed taxonomy**: pass `initialClusters` and `allowNewClusters: false`.
  Items that don't fit any seeded cluster above threshold become `forgotten`.
- **Self-cleaning runs**: `reconcileWithClassifier: true` to periodically
  refresh briefs and merge overlapping clusters every `reviewEvery` items.

## Behavior

1. Each scheduled item is judged against the current set of clusters by a
   subagent dispatched through `task`.
2. Assignment is judgment-only — there is no lexical fallback.
   - Confidence `>= similarityThreshold` routes to an existing theme, or
     spawns a new cluster from the proposed theme (when `allowNewClusters`).
   - Confidence `< similarityThreshold` (or unknown theme with creation
     disabled) marks the item `forgotten` rather than forcing a bad fit.
3. Clusters store compact `ClusterReference`s (id, type, text, metadata), not
   full copies, so state stays small as it grows.
4. Processing is serialized internally for deterministic, race-free state, even
   though you schedule concurrently.
5. With reconciliation on, every `reviewEvery` items the engine refreshes each
   cluster's brief and merges pairs above `mergeThreshold`.

## Result contract

- `await clusterSet` → `ClusterSetSnapshot`:
  - `clusters: ClusterNode[]` — each has `clusterId`, `name`, `brief`,
    `references[]`, `createdAt`, `updatedAt`.
  - `processedCount`, `forgottenCount`, `pendingCount`, `reviewRuns`.
  - `toMarkdown(): string` — renders a run-stats header plus one section +
    reference table (`type#id` | text) per cluster. Self-contained, no args.
- `clusterSet.schedule(item)` → `ClusterAssignment` for that item:
  - `clusterId`, `createdCluster`, `confidence`, `rationale`, `forgotten`,
    optional `error`.
- `clusterSet.snapshot()` — synchronous current view (does not wait for drain);
  also carries `toMarkdown()`.
- `clusterSet.getClusters()` — defensive copy of clusters only.

Call `snapshot.toMarkdown()` for a ready-made report, or read the snapshot's
plain data fields and render it yourself for full control.
