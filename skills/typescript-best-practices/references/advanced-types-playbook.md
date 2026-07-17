# Advanced Types Playbook

Use this reference when a public contract needs type-level relationships that ordinary annotations, built-in utility types, `satisfies`, or overloads cannot express cleanly. Keep runtime representations simple, keep inference caller-friendly, and add type tests for every non-trivial utility.

The parent skill's rules still apply: no `any`, narrow `unknown` at boundaries, and do not use assertions to bypass proof.

## Choose the Smallest Useful Tool

1. Start with inference, `satisfies`, `as const`, indexed access, and built-in utility types.
2. Add a constrained generic when values must preserve a relationship.
3. Add a conditional type when the result depends on the input type.
4. Add a mapped type when every key follows the same transformation.
5. Add a template-literal type only when strings are part of the public protocol.
6. Add bounded recursion only when a finite nesting model materially improves the API.

If the type cannot be explained in one sentence or verified with a compact type test, simplify the API or move validation to runtime.

## Generics Preserve Value Flow

Let callers infer type arguments whenever possible:

```ts
function identity<Value>(value: Value): Value {
  return value;
}

interface HasLength {
  length: number;
}

function withMeasuredLength<Value extends HasLength>(value: Value): {
  value: Value;
  length: number;
} {
  return { value, length: value.length };
}

const result = withMeasuredLength("hello");
// result.value is string
```

Use multiple parameters only when each represents a real relationship:

```ts
function merge<Left extends object, Right extends object>(
  left: Left,
  right: Right,
): Left & Right {
  return { ...left, ...right };
}
```

Prefer semantic names such as `Input`, `Output`, `Key`, and `Value` when several parameters interact.

## Conditional Types and `infer`

Extract relationships rather than duplicating declarations:

```ts
type FunctionResult<Fn> =
  Fn extends (...args: never[]) => infer Result ? Result : never;

type ElementOf<Value> = Value extends readonly (infer Element)[] ? Element : never;
type AwaitedValue<Value> = Value extends PromiseLike<infer Result> ? Result : Value;
```

Conditional types distribute over a naked type parameter:

```ts
type ToArray<Member> = Member extends unknown ? Member[] : never;
type Distributed = ToArray<string | number>; // string[] | number[]
```

Wrap both sides to treat a union as one value:

```ts
type ToArrayTogether<Value> = [Value] extends [unknown] ? Value[] : never;
type Combined = ToArrayTogether<string | number>; // (string | number)[]
```

Use `never` to filter union members or impossible branches, not as a generic error message.

## Mapped Types and Key Remapping

Use mapped types for systematic transformations:

```ts
type Mutable<Value> = {
  -readonly [Key in keyof Value]: Value[Key];
};

type RequiredFields<Value> = {
  [Key in keyof Value]-?: Value[Key];
};

type Getters<Value> = {
  [Key in keyof Value as Key extends string
    ? `get${Capitalize<Key>}`
    : never]: () => Value[Key];
};

type PickByValue<Value, Selected> = {
  [Key in keyof Value as Value[Key] extends Selected ? Key : never]: Value[Key];
};
```

Preserve `symbol` and numeric keys unless the public API intentionally supports strings only. When remapping to strings, state that restriction explicitly.

## Template-Literal Protocols

Template-literal types are useful for finite naming conventions:

```ts
type EventName = "click" | "focus" | "blur";
type HandlerName = `on${Capitalize<EventName>}`;

type PropertyEvents<Value extends object> = {
  on<Key extends Extract<keyof Value, string>>(
    event: `${Key}Changed`,
    callback: (next: Value[Key]) => void,
  ): () => void;
};
```

Avoid generating huge cross-products. If the possible strings are open-ended or validated externally, accept `string` and validate at runtime instead.

## Recursive Types Must Be Bounded

Unbounded path and deep-transformation utilities can slow editors or trigger excessive-instantiation errors. Carry an explicit depth budget:

```ts
type PreviousDepth = [never, 0, 1, 2, 3, 4, 5];

type NestedPath<Value, Depth extends number = 5> =
  Depth extends 0
    ? never
    : Value extends object
      ? {
          [Key in Extract<keyof Value, string>]:
            | Key
            | (NestedPath<Value[Key], PreviousDepth[Depth]> extends infer Rest
                ? Rest extends string
                  ? `${Key}.${Rest}`
                  : never
                : never);
        }[Extract<keyof Value, string>]
      : never;
```

For deep readonly/partial helpers, preserve callable values and decide explicitly how arrays, maps, sets, dates, and class instances should behave:

```ts
type DeepReadonly<Value, Depth extends number = 5> =
  Depth extends 0
    ? Value
    : Value extends (...args: never[]) => unknown
      ? Value
      : Value extends readonly (infer Element)[]
        ? readonly DeepReadonly<Element, PreviousDepth[Depth]>[]
        : Value extends object
          ? {
              readonly [Key in keyof Value]: DeepReadonly<
                Value[Key],
                PreviousDepth[Depth]
              >;
            }
          : Value;
```

Do not ship a generic "deep" utility until its container and leaf semantics are documented.

## Type-Safe Event Contracts

Represent events as a payload map and derive the API from it:

```ts
type EventMap = {
  "user:created": { id: string; name: string };
  "user:updated": { id: string };
  "user:deleted": { id: string };
};

interface TypedEventEmitter<Events extends object> {
  on<Event extends keyof Events>(
    event: Event,
    listener: (payload: Events[Event]) => void,
  ): () => void;

  emit<Event extends keyof Events>(event: Event, payload: Events[Event]): void;
}
```

Keep the interface fully typed. If an underlying untyped emitter accepts arbitrary payloads, isolate it behind one adapter that receives `unknown`, validates or narrows it, and never exposes the unsafe storage model.

## Type-Safe API Contracts

Model endpoint relationships separately from transport behavior:

```ts
type Endpoint = {
  params?: object;
  body?: unknown;
  response: unknown;
};

type ApiSchema = Record<string, Record<string, Endpoint>>;

type RequestOptions<Definition extends Endpoint> =
  (Definition extends { params: infer Params } ? { params: Params } : object) &
  (Definition extends { body: infer Body } ? { body: Body } : object);

interface ApiClient<Schema extends ApiSchema> {
  request<
    Path extends keyof Schema,
    Method extends keyof Schema[Path],
    Definition extends Schema[Path][Method] & Endpoint,
  >(
    path: Path,
    method: Method,
    ...options: keyof RequestOptions<Definition> extends never
      ? []
      : [RequestOptions<Definition>]
  ): Promise<Definition["response"]>;
}
```

Static endpoint types do not validate network data. The implementation must parse the response as `unknown` and validate it before resolving the typed promise.

## Builders and State Transitions

Use a state parameter when an operation should become available only after required steps:

```ts
type UserDraft = {
  id?: string;
  name?: string;
  email?: string;
};

type User = Required<UserDraft>;

type Complete = { id: true; name: true; email: true };

declare class UserBuilder<State extends Partial<Complete> = {}> {
  id(value: string): UserBuilder<State & { id: true }>;
  name(value: string): UserBuilder<State & { name: true }>;
  email(value: string): UserBuilder<State & { email: true }>;
  build(this: UserBuilder<Complete>): User;
}
```

The runtime implementation must still check required values before constructing `User`. Keep any unavoidable assertion private, precise, and immediately after that invariant check; never return a fabricated value merely to satisfy the generic signature.

## Validation Shapes

Mapped types can preserve field-specific validator inputs and errors:

```ts
type ValidationRule<Value> = {
  validate: (value: Value) => boolean;
  message: string;
};

type FieldValidation<Form extends object> = {
  [Key in keyof Form]?: readonly ValidationRule<Form[Key]>[];
};

type ValidationErrors<Form extends object> = {
  [Key in keyof Form]?: readonly string[];
};
```

At external boundaries, validate an `unknown` input before treating it as the form type. Generic structure alone is not runtime validation.

## Discriminated Unions and Exhaustiveness

Encode state transitions with a stable discriminant and keep payloads precise:

```ts
type AsyncState<Value> =
  | { status: "idle" }
  | { status: "loading"; requestId: string }
  | { status: "success"; data: Value }
  | { status: "error"; error: Error };

function assertNever(value: never): never {
  throw new Error(`Unexpected variant: ${String(value)}`);
}

function describe<Value>(state: AsyncState<Value>): string {
  switch (state.status) {
    case "idle":
      return "Idle";
    case "loading":
      return `Loading ${state.requestId}`;
    case "success":
      return "Complete";
    case "error":
      return state.error.message;
    default:
      return assertNever(state);
  }
}
```

Prefer this to optional fields whose legal combinations are implicit.

## Narrowing and Assertion Functions

Reusable guards should accept `unknown`:

```ts
function isArrayOf<Element>(
  value: unknown,
  isElement: (candidate: unknown) => candidate is Element,
): value is Element[] {
  return Array.isArray(value) && value.every(isElement);
}

function assertString(value: unknown): asserts value is string {
  if (typeof value !== "string") {
    throw new TypeError("Expected a string");
  }
}
```

Use assertion functions only when failure should throw. Use predicates when callers need branching control.

## Type Tests

Test both successful inference and intended rejection:

```ts
type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends
  (<Value>() => Value extends Right ? 1 : 2)
    ? true
    : false;

type Expect<Condition extends true> = Condition;

type _element = Expect<Equal<ElementOf<readonly string[]>, string>>;
type _distributed = Expect<
  Equal<ToArray<string | number>, string[] | number[]>
>;
```

When supported by the project, also use `expectTypeOf` or `.test-d.ts` files and `// @ts-expect-error` for negative cases. Every `@ts-expect-error` should explain the invariant it protects.

## Performance and Review Checklist

- Prefer interfaces over large repeated intersections when diagnostics or checking become slow.
- Name intermediate results to break up deeply nested expressions.
- Split very large unions and avoid circular generic constraints.
- Bound recursive types and provide a simple fallback at depth zero.
- Do not compute type-level results that runtime validation must compute anyway.
- Confirm public inference at call sites without explicit generic arguments.
- Confirm there is no `any`, including hidden occurrences in function constraints and distributive conditionals.
- Run the project's typecheck and type tests before accepting the design.
