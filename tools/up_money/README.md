# 2Up Money tools

Scripts behind the [2Up Money](https://claude.ai/artifact/AuQZD2GhnqQQbnxAcQpHu1) page: a dashboard of the joint Up accounts where you can also categorise and tag transactions.

| File | What it does |
|---|---|
| `fetch_all.sh` | Pulls accounts, categories, tags and every joint-account transaction from the Up API into a work folder. |
| `export.py` | Turns that pull into the data files the page reads (`transactions`, `categories`, `balances`, `tags`). |
| `apply_changes.py` | Applies the category and tag changes queued on the page to Up. |
| `page/index.html` | The page itself. |

All three scripts read the token from `UP_API_TOKEN` and never store it.

How the pieces fit together, and the step-by-step workflows Claude follows, are in [`.claude/skills/up-bank-api/SKILL.md`](../../.claude/skills/up-bank-api/SKILL.md).
