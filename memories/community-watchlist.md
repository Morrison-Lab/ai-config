# Agentic-AI community watchlist (Reddit)

A standing target list for practice-mining and opposition-research passes
over Reddit's agentic-AI communities,
so future runs start from measured targets instead of re-deriving them.
Produced by the issue [#2041](https://github.com/Morrison-Lab/ai-config/issues/2041) review
(orchestrated workflow, 2026-08-23:
top-of-year listings plus practice-term search, ~25 subreddits, 2,661 unique posts;
full ranked findings are in that issue's report comment).

Yield = how much corpus-applicable practice signal the 2026-08 harvest actually produced,
not subscriber count --- r/mcp (small) out-yielded r/ChatGPT (11M+).
Yields are a dated measurement and decay as communities shift;
re-measure on each pass rather than trusting this table's ranking as current.

Access mechanics (Reddit is blocked to WebFetch/WebSearch/curl in local sessions;
the working Claude-in-Chrome route): [`reddit-access.md`](reddit-access.md).

| Subreddit | Yield (2026-08) | What it carried |
|---|---|---|
| r/AI_Agents | high | Broad agentic-practice surface: orchestration postmortems, token-overhead benchmarks, security incidents, unattended-ops checklists; highest single-post engagement in the dataset. |
| r/ClaudeAI | high | Primary-source tips (Claude Code team), rules-file compliance findings, hook patterns, terminal workflow posts; several of the top-scoring practice posts in the run. |
| r/ClaudeCode | high | Highest density of directly-applicable Claude Code workflow posts: review pipelines, skills with published benchmarks, agent teams, worker pools, token audits. |
| r/cursor | high | Planning-loop and spec-driven workflows, cost-routing measurements, and the price-vs-actual-cost study; practices transfer to Claude Code with little translation. |
| r/LocalLLaMA | high | Tool-interface design from experienced builders, skill-file handoff patterns, and the strongest incident threads; noisy with model releases but the practice posts are substantive. |
| r/mcp | high | Concentrated, convergent clusters on tool-schema bloat, Code Mode, and CLI-over-MCP; small subreddit but nearly every harvested post was on-scope. |
| r/AgentsOfAI | medium | Prohibition-unreliability evidence and Boris Cherny primary-source material; mixed with hype but recurring on-scope threads. |
| r/artificial | medium | Incident reports (deletions, sudo bypass, sandbox escape, runaway bills) -- motivation evidence for guardrails rather than practice descriptions. |
| r/AutoGPT | medium | Verification tooling, guardrail placement grounded in dated incidents, and config-generation tools; low scores but concrete artifacts. |
| r/LangChain | medium | Architecture postmortems (typed graphs over omnipotent agents) and tool-error-shape experiments; lower volume but tested claims. |
| r/LLMDevs | medium | Context-routing bootstraps with deterministic drift checkers and adoption trajectories; occasional but high-precision hits. |
| r/n8n | medium | Production-operations discipline from agency operators: deterministic-over-LLM routing, silent-failure prevention, micro-agent tiering. |
| r/VibeCodeDevs | medium | Memory-index architecture and self-review mechanism posts; small scores but unusually precise practice descriptions. |
| r/aiagents | low | One strong verification incident post; otherwise thin. |
| r/AutoGenAI | low | One agent-verifier tool post; low volume. |
| r/automation | low | Deterministic-over-agent posts duplicating the r/n8n signal at lower quality. |
| r/ChatGPT | low | One prohibition-unsuppressability thread; otherwise consumer chat, off-scope. |
| r/crewai | low | Guardrail-placement discussion only, single-digit scores. |
| r/LocalLLM | low | One vertical-slice planning post; mostly hardware and model talk. |
| r/MachineLearning | low | One open-source agentic-context-engineering implementation; mostly research posts off-scope for practice mining. |
| r/OpenAI | low | One sudo-bypass incident; otherwise model gossip. |
| r/PydanticAI | low | One ~80-line rules-file template mention; minimal volume. |

- **Do:** start a practice-mining pass from the high-yield tier,
  and record the new pass's yields back into this table with their date.
- **Don't:** scope a pass by subscriber counts,
  or treat the 2026-08 yield column as current without re-measuring.
