/**
 * Domain-agnostic, queue-driven clustering engine.
 *
 * Architecture overview:
 * - `ClusterSet` accepts items incrementally through `schedule(...)`.
 * - Processing is single-flight: one queue consumer loop (`pump`) mutates state.
 * - Each item is assigned strictly by classifier output (no lexical fallback).
 * - Clusters store only compact references to source items, not full copies.
 * - Optionally, every N processed items, a periodic review pass refreshes
 *   briefs and merges high-overlap clusters.
 *
 * Concurrency model:
 * - Scheduling is "fire-and-forget" from the caller's perspective.
 * - Internal processing remains deterministic (one item assigned at a time).
 * - `ClusterSet` is `PromiseLike`, so callers can `await clusterSet` to wait for
 *   all in-flight and newly-added work to settle.
 *
 * Tool integration:
 * - Primary cluster placement is judged by a subagent dispatched through the
 *   ambient `task` global, defaulting to the `general-purpose` subagent type.
 * - Optional periodic review and merge planning use the same dispatch.
 *
 * This engine is generic. It does not know about GitHub, issues, or any other
 * domain. You feed it `ClusterItem`s — each is just an identity plus the text
 * to cluster on plus arbitrary metadata — and it groups them into themed
 * clusters. To cluster a new domain, map your records into `ClusterItem` shape
 * and schedule them; nothing else needs to change.
 */

/**
 * A single item to be clustered.
 *
 * This is the only shape the engine cares about:
 * - `id` + `type` form the stable identity (type defaults to "item").
 * - `text` is the content the classifier reasons over to choose a theme.
 *   Pack whatever is salient (title + body summary + labels) into it.
 * - `metadata` is opaque to the engine; it is carried into the cluster
 *   reference so you can "double click" later without re-fetching.
 */
export type ClusterItem = {
  id: number | string;
  type?: string;
  text: string;
  metadata?: Record<string, unknown>;
};

/**
 * Minimal immutable reference shape persisted inside a cluster.
 *
 * Keeps cluster state compact and stable even if upstream item schemas evolve.
 * References are sufficient for later inspection through additional tool calls.
 */
export type ClusterReference = {
  id: number | string;
  type: string;
  text: string;
  metadata: Record<string, unknown>;
};

/**
 * Runtime cluster object maintained by `ClusterSet`.
 *
 * Notes:
 * - `brief` is mutable and refreshed during periodic review.
 * - `references` grows as new items are assigned.
 * - timestamps use epoch milliseconds from `Date.now`.
 */
export type ClusterNode = {
  clusterId: string;
  name: string;
  brief: string;
  references: ClusterReference[];
  createdAt: number;
  updatedAt: number;
};

/**
 * Normalized classifier routing decision.
 *
 * Carries classifier-selected theme metadata and an optional resolved cluster.
 */
export type ClusterDecision = {
  clusterId: string | null;
  slug: string;
  name: string;
  brief: string;
  confidence: number;
  rationale: string;
};

/**
 * Result returned to callers for each scheduled item.
 *
 * Intentionally operational (what happened) rather than semantic (whether the
 * clustering was "correct").
 */
export type ClusterAssignment = {
  itemId: number | string;
  itemType: string;
  clusterId: string | null;
  createdCluster: boolean;
  confidence: number;
  rationale: string;
  forgotten: boolean;
  error?: string;
};

/**
 * Snapshot view returned by `ClusterSet#snapshot()` and by awaiting the set.
 */
export type ClusterSetSnapshot = {
  processedCount: number;
  forgottenCount: number;
  pendingCount: number;
  reviewRuns: number;
  clusters: ClusterNode[];
  /**
   * Renders the snapshot as markdown: a run-stats header followed by one
   * section + reference table per cluster. Self-contained; takes no arguments.
   */
  toMarkdown: () => string;
};

/**
 * Ambient `task` dispatcher provided by the interpreter runtime.
 *
 * The engine calls this directly (as a bare global) to judge each placement,
 * folding its internal prompt into `description` and passing the JSON schema as
 * `responseSchema`. The subagent is expected to return a value matching the
 * schema (a parsed object or a JSON string matching it).
 */
declare function task(input: {
  description: string;
  subagentType: string;
  responseSchema?: Record<string, unknown>;
}): Promise<unknown>;

/**
 * Configuration surface for `ClusterSet`.
 */
export type ClusterSetOptions = {
  /**
   * What kind of thing is being clustered, used only to phrase classifier
   * prompts (e.g. "support ticket", "product theme"). Defaults to "item".
   */
  domainLabel?: string;
  /**
   * Number of processed items between review/merge passes.
   * Defaults to 10. Only used when `reconcileWithClassifier` is true.
   */
  reviewEvery?: number;
  /**
   * Minimum confidence required to accept classifier theme routing.
   * Clamped to [0,1]. Defaults to 0.65.
   */
  similarityThreshold?: number;
  /**
   * Minimum merge confidence required during periodic review.
   * Clamped to [0,1]. Defaults to 0.75.
   * Only used when `reconcileWithClassifier` is true.
   */
  mergeThreshold?: number;
  /**
   * Cap on references embedded in classifier/review prompts per cluster.
   * Defaults to 8.
   */
  maxClusterRefsInPrompt?: number;
  /**
   * Subagent type to dispatch through the `task` global for classification.
   * Defaults to "general-purpose".
   */
  subagentType?: string;
  /**
   * Enable classifier-based periodic cluster review/merge.
   * Defaults to false.
   */
  reconcileWithClassifier?: boolean;
  /**
   * Optional pre-seeded clusters. Useful when auto-creation is disabled.
   */
  initialClusters?: ClusterNode[];
  /**
   * Whether new clusters may be created from classifier theme output.
   * Defaults to true.
   */
  allowNewClusters?: boolean;
};

type QueueEntry = {
  item: ClusterItem;
  resolve: (value: ClusterAssignment) => void;
};

type MergePlan = {
  merges: Array<{
    fromClusterId: string;
    intoClusterId: string;
    confidence: number;
    rationale: string;
  }>;
};

const DEFAULT_DOMAIN_LABEL = "item";
const DEFAULT_REVIEW_EVERY = 10;
const DEFAULT_SIMILARITY_THRESHOLD = 0.65;
const DEFAULT_MERGE_THRESHOLD = 0.75;
const DEFAULT_MAX_CLUSTER_REFS_IN_PROMPT = 8;
const DEFAULT_RECONCILE_WITH_CLASSIFIER = false;

const CLASSIFIER_JSON_SCHEMA = {
  name: "cluster_theme_decision",
  schema: {
    type: "object",
    additionalProperties: false,
    required: ["slug", "name", "brief", "confidence", "rationale"],
    properties: {
      slug: { type: "string", minLength: 1, maxLength: 80 },
      name: { type: "string", minLength: 1, maxLength: 160 },
      brief: { type: "string", minLength: 1, maxLength: 500 },
      confidence: { type: "number", minimum: 0, maximum: 1 },
      rationale: { type: "string", minLength: 1, maxLength: 500 },
    },
  },
  strict: true,
} as const;

const CLUSTER_BRIEF_JSON_SCHEMA = {
  name: "cluster_brief",
  schema: {
    type: "object",
    additionalProperties: false,
    required: ["brief"],
    properties: {
      brief: { type: "string", minLength: 1, maxLength: 500 },
    },
  },
  strict: true,
} as const;

const CLUSTER_MERGE_PLAN_JSON_SCHEMA = {
  name: "cluster_merge_plan",
  schema: {
    type: "object",
    additionalProperties: false,
    required: ["merges"],
    properties: {
      merges: {
        type: "array",
        items: {
          type: "object",
          additionalProperties: false,
          required: ["fromClusterId", "intoClusterId", "confidence", "rationale"],
          properties: {
            fromClusterId: { type: "string", minLength: 1, maxLength: 200 },
            intoClusterId: { type: "string", minLength: 1, maxLength: 200 },
            confidence: { type: "number", minimum: 0, maximum: 1 },
            rationale: { type: "string", minLength: 1, maxLength: 500 },
          },
        },
      },
    },
  },
  strict: true,
} as const;

/**
 * Escapes a cell value so it is safe inside a markdown table.
 */
function escapeCell(value: string): string {
  return value.replace(/\|/g, "\\|").replace(/\n+/g, " ").trim();
}

/**
 * Renders snapshot data as markdown: a run-stats header followed by one section
 * + reference table per cluster. Pure function over the snapshot's plain data.
 */
function renderSnapshotMarkdown(data: {
  processedCount: number;
  forgottenCount: number;
  pendingCount: number;
  reviewRuns: number;
  clusters: ClusterNode[];
}): string {
  const lines: string[] = [];
  lines.push("# Cluster Report");
  lines.push("");
  lines.push(`- Clusters: ${data.clusters.length}`);
  lines.push(`- Processed items: ${data.processedCount}`);
  lines.push(`- Forgotten items: ${data.forgottenCount}`);
  lines.push(`- Pending items: ${data.pendingCount}`);
  lines.push(`- Review runs: ${data.reviewRuns}`);
  lines.push("");

  for (const cluster of data.clusters) {
    lines.push(`## ${cluster.name}`);
    lines.push("");
    lines.push(`- Cluster ID: \`${cluster.clusterId}\``);
    lines.push(`- Brief: ${cluster.brief ? escapeCell(cluster.brief) : "_No brief_"}`);
    lines.push(`- Items: ${cluster.references.length}`);
    lines.push("");
    lines.push("| Item | Context |");
    lines.push("| --- | --- |");
    for (const ref of cluster.references) {
      lines.push(`| ${ref.type}#${ref.id} | ${escapeCell(ref.text)} |`);
    }
    lines.push("");
  }

  return lines.join("\n").trimEnd() + "\n";
}

/**
 * Dynamic promise aggregator that stays awaitable while new promises are added.
 *
 * Why this exists:
 * - Native `Promise.all([...])` snapshots a fixed list.
 * - `ClusterSet` needs "open set" semantics where work may be scheduled while
 *   previous work is still running.
 *
 * Stability condition:
 * - `then(...)` resolves only after one full await cycle observes no new
 *   additions (`version` unchanged).
 */
export class PromiseSet implements PromiseLike<void> {
  private current: Promise<void> = Promise.resolve();
  private version = 0;

  /**
   * Adds a promise to the active set.
   *
   * The chain is extended so any current or future awaiter waits on this work.
   */
  add(promise: PromiseLike<unknown>): void {
    this.version += 1;
    const next = Promise.all([this.current, Promise.resolve(promise)]).then(
      () => undefined
    );
    this.current = next;
  }

  private async awaitStable(): Promise<void> {
    let seenVersion = this.version;
    while (true) {
      await this.current;
      if (seenVersion === this.version) {
        return;
      }
      seenVersion = this.version;
    }
  }

  /**
   * PromiseLike implementation that resolves when the set becomes stable.
   */
  then<TResult1 = void, TResult2 = never>(
    onfulfilled?:
      | ((value: void) => TResult1 | PromiseLike<TResult1>)
      | null,
    onrejected?:
      | ((reason: any) => TResult2 | PromiseLike<TResult2>)
      | null
  ): Promise<TResult1 | TResult2> {
    return this.awaitStable().then(
      onfulfilled ?? undefined,
      onrejected ?? undefined
    );
  }
}

/**
 * Stateful clustering queue that supports incremental scheduling and deferred await.
 *
 * Core guarantees:
 * - Assignment loop is serialized to avoid racey cluster mutations.
 * - New items can be scheduled while processing is ongoing.
 * - Cluster creation policy is controlled by `allowNewClusters`.
 * - Unassignable items are explicitly marked as forgotten.
 * - Awaiting the instance waits for the queue to drain *and* for any newly
 *   scheduled work observed during that drain.
 */
export class ClusterSet implements PromiseLike<ClusterSetSnapshot> {
  private readonly domainLabel: string;
  private readonly reviewEvery: number;
  private readonly similarityThreshold: number;
  private readonly mergeThreshold: number;
  private readonly maxClusterRefsInPrompt: number;
  private readonly reconcileWithClassifier: boolean;
  private readonly allowNewClusters: boolean;
  private readonly subagentType: string;

  private readonly queue: QueueEntry[] = [];
  private readonly pending = new PromiseSet();
  private readonly clusterMap = new Map<string, ClusterNode>();
  private processing = false;
  private processedCount = 0;
  private forgottenCount = 0;
  private reviewRuns = 0;

  /**
   * @param options Tuning controls for clustering behavior.
   */
  constructor(options: ClusterSetOptions = {}) {
    this.domainLabel = (options.domainLabel ?? DEFAULT_DOMAIN_LABEL).trim() || DEFAULT_DOMAIN_LABEL;
    this.reviewEvery = Math.max(1, options.reviewEvery ?? DEFAULT_REVIEW_EVERY);
    this.similarityThreshold = Math.max(
      0,
      Math.min(1, options.similarityThreshold ?? DEFAULT_SIMILARITY_THRESHOLD)
    );
    this.mergeThreshold = Math.max(
      0,
      Math.min(1, options.mergeThreshold ?? DEFAULT_MERGE_THRESHOLD)
    );
    this.maxClusterRefsInPrompt = Math.max(
      1,
      options.maxClusterRefsInPrompt ?? DEFAULT_MAX_CLUSTER_REFS_IN_PROMPT
    );
    this.reconcileWithClassifier =
      options.reconcileWithClassifier ?? DEFAULT_RECONCILE_WITH_CLASSIFIER;
    this.allowNewClusters = options.allowNewClusters ?? true;
    this.subagentType = (options.subagentType ?? "general-purpose").trim() || "general-purpose";
    if (Array.isArray(options.initialClusters)) {
      for (const cluster of options.initialClusters) {
        this.clusterMap.set(cluster.clusterId, {
          ...cluster,
          references: [...cluster.references],
        });
      }
    }
  }

  /**
   * Adds or replaces a cluster definition in the active set.
   *
   * Primary mechanism to seed clusters when auto-creation is disabled.
   */
  upsertCluster(cluster: ClusterNode): void {
    this.clusterMap.set(cluster.clusterId, {
      ...cluster,
      references: [...cluster.references],
    });
  }

  /**
   * Enqueues one item for asynchronous clustering.
   *
   * Processing starts automatically if not already running.
   *
   * @param item Item to assign.
   * @returns Per-item assignment promise.
   */
  schedule(item: ClusterItem): Promise<ClusterAssignment> {
    const work = new Promise<ClusterAssignment>((resolve) => {
      this.queue.push({ item, resolve });
      void this.pump();
    });

    this.pending.add(work.then(() => undefined));
    return work;
  }

  /**
   * Convenience bulk enqueue wrapper over {@link schedule}.
   */
  scheduleMany(items: ClusterItem[]): Promise<ClusterAssignment[]> {
    return Promise.all(items.map((item) => this.schedule(item)));
  }

  /**
   * Returns a defensive copy of current clusters and references.
   */
  getClusters(): ClusterNode[] {
    return [...this.clusterMap.values()].map((cluster) => ({
      ...cluster,
      references: cluster.references.map((ref) => ({ ...ref })),
    }));
  }

  /**
   * Returns an immutable runtime summary of queue + cluster state.
   */
  snapshot(): ClusterSetSnapshot {
    const data = {
      processedCount: this.processedCount,
      forgottenCount: this.forgottenCount,
      pendingCount: this.queue.length,
      reviewRuns: this.reviewRuns,
      clusters: this.getClusters(),
    };
    return {
      ...data,
      toMarkdown: () => renderSnapshotMarkdown(data),
    };
  }

  /**
   * PromiseLike implementation.
   *
   * `await clusterSet` resolves to a stable snapshot after all currently known
   * and newly-added in-flight work has finished.
   */
  then<TResult1 = ClusterSetSnapshot, TResult2 = never>(
    onfulfilled?:
      | ((value: ClusterSetSnapshot) => TResult1 | PromiseLike<TResult1>)
      | null,
    onrejected?:
      | ((reason: any) => TResult2 | PromiseLike<TResult2>)
      | null
  ): Promise<TResult1 | TResult2> {
    return this.pending.then(() => this.snapshot()).then(
      onfulfilled ?? undefined,
      onrejected ?? undefined
    );
  }

  /**
   * Main single-consumer loop.
   *
   * Design rationale:
   * - Centralizes all state mutation (`queue`, `clusterMap`, counters).
   * - Prevents concurrent writes and keeps assignment order deterministic.
   * - If new work arrives during shutdown, loop re-enters automatically.
   */
  private async pump(): Promise<void> {
    if (this.processing) {
      return;
    }
    this.processing = true;

    try {
      while (this.queue.length > 0) {
        const entry = this.queue.shift();
        if (!entry) {
          continue;
        }

        const assignment = await this.processItem(entry.item);
        entry.resolve(assignment);

        this.processedCount += 1;
        if (
          this.reconcileWithClassifier &&
          this.processedCount % this.reviewEvery === 0
        ) {
          await this.runPeriodicReview();
        }
      }
    } finally {
      this.processing = false;
      if (this.queue.length > 0) {
        void this.pump();
      }
    }
  }

  /**
   * Processes one item through classify -> resolve target -> append reference.
   *
   * Failure policy:
   * - Never throws to caller.
   * - On classifier/tool/parse failure, returns a forgotten assignment.
   */
  private async processItem(item: ClusterItem): Promise<ClusterAssignment> {
    const itemType = item.type ?? "item";
    try {
      const clusters = [...this.clusterMap.values()];
      const decision = await this.classifyAgainstClusters(item, clusters);
      const belowThreshold = decision.confidence < this.similarityThreshold;
      let createdCluster = false;
      let target =
        !belowThreshold && decision.clusterId != null
          ? this.clusterMap.get(decision.clusterId)
          : undefined;
      if (!target && this.allowNewClusters && !belowThreshold) {
        target = this.createClusterFromDecision(decision);
        createdCluster = true;
      }
      if (!target) {
        this.forgottenCount += 1;
        return {
          itemId: item.id,
          itemType: itemType,
          clusterId: null,
          createdCluster: false,
          confidence: decision.confidence,
          rationale: belowThreshold
            ? "Forgotten: classifier confidence below threshold."
            : "Forgotten: classifier returned unknown theme and new clusters are disabled.",
          forgotten: true,
        };
      }

      target.references.push(this.toReference(item));
      target.updatedAt = Date.now();

      if (!target.brief) {
        target.brief = this.buildFallbackBrief(target);
      }

      return {
        itemId: item.id,
        itemType: itemType,
        clusterId: target.clusterId,
        createdCluster: createdCluster,
        confidence: decision.confidence,
        rationale: decision.rationale,
        forgotten: false,
      };
    } catch (err) {
      this.forgottenCount += 1;
      return {
        itemId: item.id,
        itemType: itemType,
        clusterId: null,
        createdCluster: false,
        confidence: 0,
        rationale: "Forgotten: clustering error.",
        forgotten: true,
        error: this.toErrorMessage(err),
      };
    }
  }

  /**
   * Converts a full item into the compact reference stored in clusters.
   */
  private toReference(item: ClusterItem): ClusterReference {
    return {
      id: item.id,
      type: item.type ?? "item",
      text: item.text,
      metadata: item.metadata ?? {},
    };
  }

  /**
   * Runs strict classifier-based routing.
   *
   * Invalid classifier output throws and is handled by caller policy.
   */
  private async classifyAgainstClusters(
    item: ClusterItem,
    clusters: ClusterNode[]
  ): Promise<ClusterDecision> {
    const prompt = this.buildClassifierPrompt(item, clusters);
    const raw = await this.dispatch(
      `classify ${this.domainLabel} ${item.id} into a theme`,
      prompt,
      CLASSIFIER_JSON_SCHEMA
    );
    return this.parseClassifierDecision(raw, clusters);
  }

  /**
   * Builds a theme-classification prompt for one item.
   */
  private buildClassifierPrompt(
    item: ClusterItem,
    clusters: ClusterNode[]
  ): string {
    const allowedThemes = clusters
      .map((cluster) => {
        const slug = this.clusterThemeFromNode(cluster);
        if (!slug) {
          return null;
        }
        return {
          slug,
          name: cluster.name,
          brief: cluster.brief || this.buildFallbackBrief(cluster),
          itemCount: cluster.references.length,
        };
      })
      .filter((theme): theme is {
        slug: string;
        name: string;
        brief: string;
        itemCount: number;
      } => theme != null);

    return [
      `Classify this ${this.domainLabel} into one theme slug.`,
      "Return strict JSON: slug, name, brief, confidence, rationale.",
      "slug must be slug-like and concise (example: agent-reliability).",
      "Prefer existing themes from ALLOWED_THEMES over creating new ones.",
      `If no existing theme fits well (confidence < ${this.similarityThreshold.toFixed(2)}), propose a new one.`,
      "confidence must be in [0,1].",
      "",
      "ITEM:",
      JSON.stringify({ id: item.id, type: item.type ?? "item", text: item.text, metadata: item.metadata ?? {} }, null, 2),
      "",
      "ALLOWED_THEMES:",
      JSON.stringify(allowedThemes, null, 2),
    ].join("\n");
  }

  /**
   * Dispatches one classification to the ambient `task` global.
   *
   * Folds `intent` + `prompt` into the task description, unwraps the internal
   * schema wrapper into a bare JSON Schema for `responseSchema`, and runs it
   * against `subagentType`.
   */
  private async dispatch(
    intent: string,
    prompt: string,
    schema: { schema?: Record<string, unknown> }
  ): Promise<unknown> {
    // The internal schema constants are wrapped as `{ name, schema, strict }`
    // (OpenAI-style). `task`'s `responseSchema` expects the inner JSON Schema,
    // so unwrap `.schema` when present.
    const responseSchema =
      schema && typeof schema.schema === "object" && schema.schema !== null
        ? schema.schema
        : (schema as Record<string, unknown>);

    return task({
      description: `${intent}\n\n${prompt}`,
      subagentType: this.subagentType,
      responseSchema,
    });
  }

  /**
   * Parses classifier payload into a normalized decision shape.
   *
   * Throws when payload cannot be interpreted safely.
   */
  private parseClassifierDecision(
    raw: unknown,
    clusters: ClusterNode[]
  ): ClusterDecision {
    const payload = this.parseObject(raw, "classifier output");
    const rawTheme = this.readRequiredString(
      payload,
      "slug",
      "classifier output.slug"
    );
    const normalizedTheme = this.slugify(rawTheme);
    if (!normalizedTheme) {
      throw new Error("classifier output.slug is invalid");
    }
    const themeName = this.readRequiredString(
      payload,
      "name",
      "classifier output.name"
    );
    const themeBrief = this.readRequiredString(
      payload,
      "brief",
      "classifier output.brief"
    );
    const confidence = this.readRequiredNumber(
      payload,
      "confidence",
      "classifier output.confidence"
    );
    const rationale = this.readRequiredString(
      payload,
      "rationale",
      "classifier output.rationale"
    );
    const clusterId = this.resolveClusterIdFromTheme(normalizedTheme, clusters);

    return {
      clusterId: clusterId,
      slug: normalizedTheme,
      name: themeName.slice(0, 160),
      brief: themeBrief.slice(0, 500),
      confidence: Math.max(0, Math.min(1, confidence)),
      rationale,
    };
  }

  private resolveClusterIdFromTheme(
    theme: string,
    clusters: ClusterNode[]
  ): string | null {
    const normalizedTheme = this.slugify(theme);
    if (!normalizedTheme) {
      return null;
    }

    const directId = clusters.find(
      (cluster) => cluster.clusterId === normalizedTheme
    );
    if (directId) {
      return directId.clusterId;
    }

    const prefixedId = clusters.find(
      (cluster) => cluster.clusterId === `cluster-${normalizedTheme}`
    );
    if (prefixedId) {
      return prefixedId.clusterId;
    }

    const byDerivedTheme = clusters.find((cluster) => {
      const clusterTheme = this.clusterThemeFromNode(cluster);
      return clusterTheme === normalizedTheme;
    });
    if (byDerivedTheme) {
      return byDerivedTheme.clusterId;
    }

    return null;
  }

  private clusterThemeFromNode(cluster: ClusterNode): string {
    const id = cluster.clusterId.trim().toLowerCase();
    if (id.startsWith("cluster-") && id.length > "cluster-".length) {
      return this.slugify(id.slice("cluster-".length));
    }
    return this.slugify(cluster.name);
  }

  private createClusterFromDecision(decision: ClusterDecision): ClusterNode {
    const baseId = `cluster-${decision.slug}`;
    let clusterId = baseId;
    let suffix = 2;
    while (this.clusterMap.has(clusterId)) {
      clusterId = `${baseId}-${suffix}`;
      suffix += 1;
    }

    const now = Date.now();
    const cluster: ClusterNode = {
      clusterId: clusterId,
      name: decision.name.slice(0, 160),
      brief: decision.brief.slice(0, 500),
      references: [],
      createdAt: now,
      updatedAt: now,
    };
    this.clusterMap.set(cluster.clusterId, cluster);
    return cluster;
  }

  private slugify(value: string): string {
    return value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 80);
  }

  /**
   * Periodic cluster maintenance pass.
   *
   * Steps:
   * 1. Refresh each cluster brief via classifier.
   * 2. Ask classifier for merge candidates.
   * 3. Apply merges above confidence threshold.
   */
  private async runPeriodicReview(): Promise<void> {
    if (!this.reconcileWithClassifier) {
      return;
    }
    const clusters = [...this.clusterMap.values()];
    if (clusters.length <= 1) {
      return;
    }

    this.reviewRuns += 1;

    for (const cluster of clusters) {
      cluster.brief = await this.refreshClusterBrief(cluster);
      cluster.updatedAt = Date.now();
    }

    const mergePlan = await this.proposeClusterMerges(clusters);
    this.applyMergePlan(mergePlan);
  }

  /**
   * Regenerates one cluster brief from current references.
   *
   * Falls back to deterministic brief when classifier output is invalid.
   */
  private async refreshClusterBrief(cluster: ClusterNode): Promise<string> {
    const prompt = [
      `Write a concise brief for cluster ${cluster.clusterId}.`,
      "Focus on the shared theme and why these references belong together.",
      "Return strict JSON with key: brief.",
      "",
      "CLUSTER:",
      JSON.stringify(
        {
          clusterId: cluster.clusterId,
          name: cluster.name,
          references: cluster.references.slice(0, this.maxClusterRefsInPrompt),
        },
        null,
        2
      ),
    ].join("\n");

    try {
      const raw = await this.dispatch(
        `refresh brief ${cluster.clusterId}`,
        prompt,
        CLUSTER_BRIEF_JSON_SCHEMA
      );
      const payload = this.parseObject(raw, "cluster brief output");
      const brief = this.readRequiredString(
        payload,
        "brief",
        "cluster brief output.brief"
      );
      return brief.slice(0, 500);
    } catch {
      return this.buildFallbackBrief(cluster);
    }
  }

  /**
   * Deterministic local brief used when classifier output is missing/invalid.
   */
  private buildFallbackBrief(cluster: ClusterNode): string {
    const sample = cluster.references
      .slice(0, 2)
      .map((ref) => `#${ref.id} ${ref.text}`.slice(0, 160))
      .join(" ");
    return `Cluster for ${cluster.name}. ${sample}`.trim();
  }

  /**
   * Requests merge candidates from classifier.
   *
   * Output is parsed defensively and normalized into `MergePlan`.
   */
  private async proposeClusterMerges(clusters: ClusterNode[]): Promise<MergePlan> {
    const prompt = [
      "Given these clusters, propose merges for highly overlapping clusters only.",
      "Return strict JSON with key `merges` as array of objects:",
      "`{ fromClusterId, intoClusterId, confidence, rationale }`",
      "confidence must be in [0,1].",
      "",
      "CLUSTERS:",
      JSON.stringify(
        clusters.map((cluster) => ({
          clusterId: cluster.clusterId,
          name: cluster.name,
          brief: cluster.brief,
          references: cluster.references.slice(0, this.maxClusterRefsInPrompt).map((ref) => ({
            id: ref.id,
            text: ref.text,
          })),
        })),
        null,
        2
      ),
    ].join("\n");

    try {
      const raw = await this.dispatch(
        "cluster merge planning",
        prompt,
        CLUSTER_MERGE_PLAN_JSON_SCHEMA
      );
      const payload = this.parseObject(raw, "cluster merge output");
      const mergesRaw = payload.merges;
      if (!Array.isArray(mergesRaw)) {
        throw new Error("cluster merge output.merges is not an array");
      }

      const merges: MergePlan["merges"] = [];
      for (const row of mergesRaw) {
        if (!row || typeof row !== "object" || Array.isArray(row)) {
          throw new Error("cluster merge row is not an object");
        }
        const merge = row as Record<string, unknown>;
        const fromClusterId = this.readRequiredString(
          merge,
          "fromClusterId",
          "cluster merge output.fromClusterId"
        );
        const intoClusterId = this.readRequiredString(
          merge,
          "intoClusterId",
          "cluster merge output.intoClusterId"
        );
        const confidence = this.readRequiredNumber(
          merge,
          "confidence",
          "cluster merge output.confidence"
        );
        const rationale = this.readRequiredString(
          merge,
          "rationale",
          "cluster merge output.rationale"
        );
        if (fromClusterId === intoClusterId) {
          continue;
        }
        merges.push({
          fromClusterId: fromClusterId,
          intoClusterId: intoClusterId,
          confidence: Math.max(0, Math.min(1, confidence)),
          rationale,
        });
      }
      return { merges };
    } catch {
      return { merges: [] };
    }
  }

  /**
   * Applies merge plan in-place and deduplicates merged references.
   *
   * Only merges with confidence >= configured merge threshold are applied.
   */
  private applyMergePlan(plan: MergePlan): void {
    for (const merge of plan.merges) {
      if (merge.confidence < this.mergeThreshold) {
        continue;
      }

      const from = this.clusterMap.get(merge.fromClusterId);
      const into = this.clusterMap.get(merge.intoClusterId);
      if (!from || !into) {
        continue;
      }

      const mergedRefs = new Map<string, ClusterReference>();
      for (const ref of into.references) {
        mergedRefs.set(`${ref.type}:${ref.id}`, ref);
      }
      for (const ref of from.references) {
        mergedRefs.set(`${ref.type}:${ref.id}`, ref);
      }

      into.references = [...mergedRefs.values()];
      into.updatedAt = Date.now();
      into.brief = `${into.brief} Merged ${from.clusterId}: ${merge.rationale}`.trim();
      this.clusterMap.delete(from.clusterId);
    }
  }

  private parseObject(raw: unknown, label: string): Record<string, unknown> {
    if (raw && typeof raw === "object" && !Array.isArray(raw)) {
      return raw as Record<string, unknown>;
    }
    if (typeof raw === "string") {
      try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return parsed as Record<string, unknown>;
        }
      } catch {
        throw new Error(`${label} was not valid JSON object output`);
      }
    }
    throw new Error(`${label} was not an object`);
  }

  private readRequiredString(
    obj: Record<string, unknown>,
    key: string,
    label: string
  ): string {
    const value = obj[key];
    if (typeof value !== "string" || !value.trim()) {
      throw new Error(`${label} must be a non-empty string`);
    }
    return value.trim();
  }

  private readRequiredNumber(
    obj: Record<string, unknown>,
    key: string,
    label: string
  ): number {
    const value = Number(obj[key]);
    if (!Number.isFinite(value)) {
      throw new Error(`${label} must be a finite number`);
    }
    return value;
  }

  /**
   * Normalizes unknown errors into loggable message strings.
   */
  private toErrorMessage(err: unknown): string {
    if (err instanceof Error) {
      return err.message;
    }
    return String(err ?? "unknown error");
  }
}
