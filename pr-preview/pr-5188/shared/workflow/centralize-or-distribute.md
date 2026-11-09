Choose explicitly whether to centralize or distribute.

Ezra, 2026-11-09: "when planning and/or performing work, we should choose explicitly whether to centralize vs distribute content or other work, both within and across repos"
([ai-config#5185](https://github.com/Morrison-Lab/ai-config/issues/5185)).

The rule applies when planning work and again when performing it.
It covers content and other work, such as code, scripts, workflows, and checks.
It applies within a repository and across repositories.

State the choice in the issue or PR, with the reason in a sentence.
Centralizing means one copy that other places link to, include, or call.
Distributing means a copy in each place that uses it.
Neither is the default: a copy that is never reconciled drifts, and a shared copy adds a dependency and a release step.

- **Do:** before copying a file, a workflow, a script, or a passage into a second place, name where the single copy could live, and say in the issue or PR which you chose and why.
- **Do:** when you find an existing duplicate, file an issue for centralizing it, as [gha#1796](https://github.com/Morrison-Lab/gha/issues/1796), [gha#1797](https://github.com/Morrison-Lab/gha/issues/1797), [gha#1798](https://github.com/Morrison-Lab/gha/issues/1798) and [gha#1799](https://github.com/Morrison-Lab/gha/issues/1799) did.
- **Don't:** copy by default because copying is the quickest step.
- **Don't:** centralize by default when the copies must differ per place.

The [`dont-reinvent-wheel`](../principles/dont-reinvent-wheel.md) check asks whether the work already exists.
This rule asks where the work should live once it does.
