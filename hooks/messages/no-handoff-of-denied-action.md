The auto-mode classifier denied {what} in session {sid},
and this `{tool}` call carries that denied {kind} verbatim.
Ezra's standing rule is that a denied action is reported,
not handed to another session to run instead
(shared/workflow/ask-for-manual-approval.md, ai-config#5914).
Report the denial to the user and stop.
The one thing that clears this is a message the user types after the denial
that names both the action ({action}) and the session ({sid}).
A prompt that quotes the user's earlier words does not count.
