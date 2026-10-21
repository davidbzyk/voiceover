### 1. Assumption violation

Identify assumptions the code makes about its environment and construct scenarios where those assumptions break.

- **Data shape assumptions** -- code assumes an API always returns JSON, a config key is always set, a queue is never empty, a list always has at least one element. What if it doesn't?
- **Timing assumptions** -- code assumes operations complete before a timeout, that a resource exists when accessed, that a lock is held for the duration of a block. What if timing changes?
- **Ordering assumptions** -- code assumes events arrive in a specific order, that initialization completes before the first request, that cleanup runs after all operations finish. What if the order changes?
- **Value range assumptions** -- code assumes IDs are positive, strings are non-empty, counts are small, timestamps are in the future. What if the assumption is violated?

For each assumption, construct the specific input or environmental condition that violates it and trace the consequence through the code.

### 2. Composition failures

Trace interactions across component boundaries where each component is correct in isolation but the combination fails.

- **Contract mismatches** -- caller passes a value the callee doesn't expect, or interprets a return value differently than intended. Both sides are internally consistent but incompatible.
- **Shared state mutations** -- two components read and write the same state (database row, cache key, global variable) without coordination. Each works correctly alone but they corrupt each other's work.
- **Ordering across boundaries** -- component A assumes component B has already run, but nothing enforces that ordering. Or component A's callback fires before component B has finished its setup.
- **Error contract divergence** -- component A throws errors of type X, component B catches errors of type Y. The error propagates uncaught.

### 3. Cascade construction

Build multi-step failure chains where an initial condition triggers a sequence of failures.

- **Resource exhaustion cascades** -- A times out, causing B to retry, which creates more requests to A, which times out more, which causes B to retry more aggressively.
- **State corruption propagation** -- A writes partial data, B reads it and makes a decision based on incomplete information, C acts on B's bad decision.
- **Recovery-induced failures** -- the error handling path itself creates new errors. A retry creates a duplicate. A rollback leaves orphaned state. A circuit breaker opens and prevents the recovery path from executing.

For each cascade, describe the trigger, each step in the chain, and the final failure state.

### 4. Abuse cases

Find legitimate-seeming usage patterns that cause bad outcomes. These are not security exploits and not performance anti-patterns -- they are emergent misbehavior from normal use.

- **Repetition abuse** -- user submits the same action rapidly (form submission, API call, queue publish). What happens on the 1000th time?
- **Timing abuse** -- request arrives during deployment, between cache invalidation and repopulation, after a dependent service restarts but before it's fully ready.
- **Concurrent mutation** -- two users edit the same resource simultaneously, two processes claim the same job, two requests update the same counter.
- **Boundary walking** -- user provides the maximum allowed input size, the minimum allowed value, exactly the rate limit threshold, a value that's technically valid but semantically nonsensical.
