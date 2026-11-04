# Never send email for the user

Ezra's standing rule, 2026-11-04: "never send emails for me".

An agent may draft an email: a draft in the mail account, a file, or text in the thread.
An agent never sends one, whatever the account, tool, or harness, and no `daytb`, `away`, or default-to-action rule changes that.
The user reads the draft and sends it.

`hooks/no-send-email.py` is the mechanism.
It denies a mail-sender command in Bash (`sendmail`, `mail`, `mutt`, `msmtp`, `git send-email`, an `smtp://` URL, `smtplib`) and an MCP tool on a mail account whose action is send, reply, or forward.
Drafting tools are untouched, and the hook has no override.
Its test is `hooks/test-no-send-email.py`.

The hook cannot see a harness that sends mail through a tool it does not match, so the rule holds there on its own words.

Origin: a draft note to a collaborator (Zach) about a CI problem that Ezra did not want sent.

- **Do:** write the email as a draft and tell the user where it is.
- **Don't:** send it, even when the user approved its wording.
