import json

with open('/home/runner/.claude/projects/-home-runner-work-ai-config-ai-config/6d8fd568-4026-4254-bb15-c7515852b380/tool-results/b0gnu1f08.txt') as f:
    lines = f.readlines()
# strip leading line number + tab from cat -n format
text = ''.join(l.split('\t', 1)[1] if '\t' in l else l for l in lines)
data = json.loads(text)
for c in data:
    login = c['user']['login']
    utype = c['user'].get('type')
    created = c['created_at']
    body = c['body']
    has_claude = '@claude' in body
    print(f"id={c['id']} created={created} login={login} type={utype} has_claude_mention={has_claude}")
    if has_claude:
        idx = body.find('@claude')
        print("   CONTEXT:", body[max(0,idx-100):idx+300].replace('\n',' | '))
