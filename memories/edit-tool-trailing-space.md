# The Edit tool can drop a trailing space

On a cloud session on 2026-11-22, two `Edit` calls whose `old_string` and `new_string` both ended in a space wrote the replacement without that space.
The results were `counts).An Ollama` in a hook's deny note and `classifier ="Permission` in a test.
Review caught both on [ai-config#6082](https://github.com/Morrison-Lab/ai-config/pull/6082).
The test suite caught neither.

- **Do:** end `old_string` and `new_string` on a non-space character, by taking in the next word or the closing quote.
- **Don't:** end either string on the space that separates the replacement from the text after it.
