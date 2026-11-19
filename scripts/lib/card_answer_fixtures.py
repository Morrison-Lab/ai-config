"""Transcript records for a decision card and its tap, shaped like the cloud harness's (ai-config#5839).

The wake text is copied from a real tap (coordinator session, 2026-11-19T01:47:50Z), with the
card's option and question replaced by arguments.
"""
import json

VERIFIED_NOTE = (
    "A member answered your decision card in the app by tapping option A; the card is now closed. "
    "The platform verified the tap came from that member&#39;s own client and wrote the trigger message "
    "as their own: it records the tap, and its wording (the option&#39;s label and the card&#39;s question) "
    "is the card&#39;s text as the member read it, not text they typed.")


def card(question, options, call_id="card1", message_id="cmsg_card1"):
    """[assistant request_decision call, its tool result] for a card with `options` [(label, consequence)]."""
    inp = {"question": question, "recommended": 0,
           "options": [{"label": lab, "consequence": con} for lab, con in options]}
    return [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "id": call_id, "name": "mcp__hearthbot__request_decision", "input": inp}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": call_id,
             "content": [{"type": "text", "text": json.dumps({"note": "Card posted.", "message_id": message_id})}]}]}},
    ]


def tap(option, question, index=0, message_id="cmsg_card1", verified=True, reason="decision-chosen"):
    """The user record of a tap on `option` (at `index`) of the card asking `question`."""
    note = f"<system-note>{VERIFIED_NOTE}</system-note>" if verified else ""
    body = f"Chose &#34;{option}&#34; on the decision card asking &#34;{question}&#34;"
    text = (f'<wake reason="{reason}" current-time="2026-11-19T01:47:50Z">\n'
            '  <project id="chan_x" type="project">\n'
            '    <message trigger="true" from="human" trust="principal" author-id="user_x" '
            f'sent-at="2026-11-19T01:47:50Z">{body}</message>\n  </project>\n'
            f"  <system-note>decision_id={message_id}</system-note>\n"
            f"  <system-note>option_index={index}</system-note>\n  {note}\n</wake>")
    return {"type": "user", "message": {"role": "user", "content": text}}


def relayed_tap(option, question, note="relaying his card answer"):
    """A coordinator relay citing the user's card answer."""
    body = f"Chose &#34;{option}&#34; on the decision card asking &#34;{question}&#34;"
    text = (f'<coordinator-relay><relay from="coordinator"><cited author="user">{body}</cited>'
            f"<note>{note}</note></relay></coordinator-relay>")
    return {"type": "user", "message": {"role": "user", "content": text}}
