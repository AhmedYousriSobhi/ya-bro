# ADR-0008: Brain: LLM strategy, step-plan representation, re-planning, budgets

- Status: Proposed (partly built in #5: one `plan` route over plain HTTPS instead of the SDK, see PROGRESS)
- Date: 2026-11-20
- Issue: #13 (implements #5)
- Depends on: ADR-0003, ADR-0005, ADR-0007, ADR-0012

## Context
SPEC has one LLM backend (Claude) for the MVP and a step loop: `perceive → plan → present → [act|wait] → verify → next`. Each step has an intent, target, narration, expected-result check and risk level. The step latency budget is under 3 s from step done to next highlight, with a cloud LLM.

Facts about the Claude API, from the Anthropic API reference cached 2026-10-06 and checked via the claude-api skill:

**Current models**

| Model | Input $/MTok | Output $/MTok |
|---|---|---|
| `claude-opus-5-5` | 4 | 20 |
| `claude-sonnet-5-5` | 2 | 10 |
| `claude-haiku-5-5` | 0.10 | 0.50 |

All three have a 1M-token context.

**Prompt caching**
- Prefix match.
- Up to 4 breakpoints.
- 5-minute TTL by default; 1-hour TTL is optional.
- Writes cost 1.25× for 5 min and 2× for 1 h.
- Reads cost about 0.1×; on Opus 5.5 they are 0.05×.
- Minimum cacheable prefix is 512 tokens on the 5.x models.

**Request behaviour**
- Strict tool use (`strict: true`) and structured outputs (`output_config.format`) guarantee the shape of the JSON that comes back.
- Opus 5.5 cannot disable thinking. Effort (default `medium`) is the control.
- Forced `tool_choice` is rejected on Opus 5.5 and Sonnet 5.5. Use `auto` plus `strict`, or structured outputs.
- Mid-conversation `system` messages provide an operator channel that does not invalidate the cache.

**Prior art**
- Agent S splits a planner, which describes the target, from a grounder.
- Copilot, Cursor and JetBrains gate *whether* to call the big model with a cheap local filter ([ai-tools.md §2.4](../research/ai-tools.md)).

## Decision drivers
- Step latency under 3 s, and the first visible feedback under 1 s.
- Correctness of plans in unfamiliar apps.
- Cost per completed task. The working assumption is under $0.10 for a 10-step task; to be validated.
- Robustness to prompt injection from screen text (ADR-0014).
- Offline degradation.
- Provider portability behind `Brain`.

## Options considered
| Option | For | Against |
|---|---|---|
| **One frontier model at tuned effort (recommended start)** | One cache namespace, so cached reads repeat across steps. Simplest. The skill guidance is to measure "most capable model at lower effort" before building cascades. | Per-token cost is higher than a cascade |
| **Tiered cascade (Opus plans, Haiku narrates and words offers, local filter gates)** | Cheaper for chatty parts | Caches are model-scoped, so the cascade loses cache reuse. More prompts to keep consistent. |
| **Local LLM (Ollama / llama.cpp) primary** | Private, offline | The maintainer's laptop (RTX 3050 4 GB, 14 GiB RAM) limits it to roughly ≤ 8B quantised models. Weak planning in unfamiliar apps (unverified for our tasks). |
| **Free-text plans parsed by regex** | Easy | Brittle. Strict tools make this unnecessary. |

## Decision
1. **Provider.** Claude via the official `anthropic` Python SDK (async client, streaming).
   - Configurable models per *route*: `plan`, `ground`, `chat`, `offer`.
   - **Default: `claude-opus-5-5` for every route.** Effort is `low` for `offer`/`chat` and `medium` for `plan`/`ground`.
   - Add `claude-haiku-5-5` (or `claude-sonnet-5-5`) to `offer`/`chat` **only if** the eval (ADR-0016) shows equal quality. That keeps one cache namespace until data says otherwise.
2. **The struggle gate is not an LLM.** Whether to offer help is decided locally (ADR-0010). The LLM is called only to word an offer, or after the user accepts.
3. **Step plan representation.** The planner calls a strict tool `propose_plan`:

   ```
   Plan { goal, app_id, assumptions[], steps: [Step] }   # full ordered plan, re-planned each iteration
   Step { id, intent, target: TargetSpec, narration{en,ar?}, why, mode_hint(show|do),
          action?: {kind: click|type|key|scroll|select|menu_path|shell_suggest, args},
          expect: Predicate, risk: R0|R1|R2|R3, fallback_hint? }
   Predicate = all/any of {event(type, role?, name~?), state(target, flag), focus(target),
                            exit_code(==0), url_matches, hook_state(key==val), text_present(re)}
   ```

   - Only `steps[0]` is presented.
   - The rest stays visible to the planner and appears in the bubble's "what's next" peek.
   - After verification the loop calls `revise_plan(observation)` with a compact diff of what changed (event list, new candidate list). The model only re-plans fully when the observation contradicts its `assumptions`.
4. **Fast path, no LLM per step.**
   - If the plan came from a **pack task graph** (ADR-0012) and the observation matches the expected predicate, advance without calling the LLM.
   - The LLM is consulted on mismatch, on "why?", or on free-form questions.
   - Target: most pack-covered steps complete in under 500 ms.
5. **Prompt layout for caching** (stable first). In order: tools → system (persona, safety policy, output rules; frozen) → pack context (frozen per app session) → conversation.
   - Put an explicit breakpoint after the pack context.
   - Use automatic caching for the conversation tail.
   - Default TTL is 5 min, because steps arrive more often than every 5 min. Use the 1-hour TTL only for long idle sessions.
   - Never put timestamps or volatile ids before the breakpoint.
6. **Injection-safe framing.**
   - Screen, terminal and web content goes only inside clearly delimited `observation` blocks, described as untrusted data.
   - Operator rules travel in system and mid-conversation system messages.
   - Tool calls are validated by the local `Policy` engine (ADR-0014). The LLM's output never directly authorises an action of risk R2 or above.
7. **Budgets** (initial; measured in the eval):

   | Item | Limit |
   |---|---|
   | Plan call | ≤ 1.5 s to first token streamed; narration streams into the bubble |
   | Context per step | ≤ 6k input tokens, excluding cached prefix |
   | Screenshots | ≤ 1 per step, cropped |
   | Hard cap per task | Configurable, default 30 LLM calls |
   | Daily spend guard | Configurable, default off. When set, the bro tells the user when it is reached. |

8. **Offline / no-key mode.** The bro still works for:
   - pack task graphs (deterministic steps and predicates);
   - terminal fix-it rules (thefuck-style, ADR-0021);
   - struggle offers that link to pack docs.

   Free-form planning needs a backend. Later, a `LocalBrain` speaking the OpenAI-compatible API (llama.cpp / Ollama) can plug into the same interface. Not in the MVP.
9. **Key handling.** The API key comes from the Secret Service (libsecret) or `ANTHROPIC_API_KEY` in `.env` (ADR-0014). It is never logged.
   *As built (#5):* order is environment, then the keyring, then `.env`; `broctl key set|status|clear` manage the stored key (hidden prompt, never argv). The keyring is reached through a helper run by the system python3 (libsecret), so the core has no new dependency; see the API-key row of ADR-0014's threat table.

## Consequences
- **Positive:**
  - Structured, verifiable steps.
  - Packs make common tasks cheap and fast.
  - Caching cuts the per-step cost of the frozen prefix to about 5%.
  - The design stays provider-portable at the `Brain` interface.
- **Negative:**
  - Opus-for-everything may cost more than a cascade until evals justify a split.
  - Thinking always runs on Opus 5.5 (effort `low` minimises it), which adds some latency.
- **Risks:**
  - Model IDs and pricing drift. They live in config, never in code.
  - The 3 s budget may fail for vision-tier steps. The UX then shows "looking…" within 300 ms so the user knows it heard.

## Validation plan
- **Spike within S5 (step loop).** 10 tasks × 3 apps.
  - Measure p50/p95 time from step-done to highlight, tokens per step, cache hit ratio (`usage.cache_read_input_tokens` > 0 on ≥ 90% of steps after the first), and cost per task.
  - **Go:** p50 ≤ 2 s and p95 ≤ 3 s (SPEC) on AT-SPI-tier steps.
- **Model-route eval.** Run `offer`/`chat` on Opus `low` against Haiku 5.5, graded on the tone rubric (ADR-0013) and on correctness. Switch only if Haiku is within 5% on the rubric.

## Revisit if
- Costs exceed budget in dogfooding.
- A local model passes the plan eval at ≥ 90% of Claude's score.
- Anthropic API changes (model retirements, caching rules).
- Multi-provider support is requested.

## Sources
- Claude API reference via the claude-api skill (models table, cached 2026-10-06; prompt caching economics; Opus 5.5 behaviour): https://platform.claude.com/docs (live docs index in skill `shared/live-sources.md`)
- Prompt caching: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
- [docs/research/ai-tools.md](../research/ai-tools.md): §2.2 Agent S planner/grounder split; §2.4 Copilot/Cursor/JetBrains gating; §3.5 injection lessons
- [docs/research/non-ai-tools.md](../research/non-ai-tools.md): §12 thefuck-style rules
