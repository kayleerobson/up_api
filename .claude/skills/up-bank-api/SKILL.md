---
name: up-bank-api
description: How to work with the Up Bank API for Kaylee and Jai's accounts, and how to run the 2Up Money page's workflows (refreshing its data, applying queued category and tag changes). Use whenever a task reads or changes anything in Up (accounts, balances, transactions, categories, tags, attachments, webhooks), or touches the 2Up Money artifact.
---

# Up Bank API

Up's own LLM reference is saved at `reference/llms.txt` (from https://developer.up.com.au/llms.txt). It is the source of truth for endpoints, parameters and response fields: read the section you need before calling an endpoint you haven't used in this session. `v1/openapi.json` at the repo root is the same API as an OpenAPI spec. This file is the short version plus what we've learned using the API for this household.

## Basics

- Base URL `https://api.up.com.au/api/v1`. JSON in and out.
- Auth: `Authorization: Bearer $UP_API_TOKEN`. The token is set in this cloud environment. Never print it, write it to a file, or put it in a page, commit or message.
- Check the connection: `GET /util/ping` returns 200.
- Use curl with `-g` (globbing off), or the square brackets in `page[size]` and `filter[...]` break the URL.
- Pagination: follow `links.next` until it is `null`. Never build page URLs yourself, and don't use `filter[since]`/`filter[until]` to page. `page[size]` up to 100.
- Errors come back as `{"errors": [{"status", "title", "detail", "source"}]}`; show `detail` to the person. 429 means rate limited: back off and retry later.
- The Python example in llms.txt has a bug: `f"Bearer ${token}"` sends a literal `$`. Use `f"Bearer {token}"`.

## The accounts

- Kaylee has a personal `Spending` account (INDIVIDUAL). Everything else is 2Up (JOINT) with Jai: `2Up Spending` plus savers (Christmas, Cruise, Gold Coast, Home Essentials, Subscriptions, Utilities, Bills, Amari, 2Up Essentials). Account ids change never, but look them up with `GET /accounts` rather than hard-coding.
- Joint history starts 12 August 2026. `filter[ownershipType]=JOINT` lists only 2Up accounts.
- Balances: `GET /accounts` gives today's balance only. Past balances must be worked back from today's balance minus later transactions (each account lands at $0 before its first transaction, which is a good check).

## Transactions: what the fields mean here

- `amount.value` is a string; use `valueInBaseUnits / 100`. Negative is money out.
- `performingCustomer.displayName` is who made a 2Up transaction: `$kayleerobson1` is Kaylee, `$jaiwt` is Jai. Null means automatic (direct debits, interest, salary credits).
- `$jaiwt` is also Jai's personal Up account: "Transfer to $jaiwt" is money to Jai's own Up.
- Jai appears as two saved payees, "Jai Wynbergen Titoko" and "J Wynbergen Titoko". Treat them as one person.
- `relationships.transferAccount` set means a transfer between Up accounts. If that account is one of the joint accounts, it's a move between their own accounts, not spending.
- `message` is the payment reference people typed ("Food", "Mortgage", "Personal Loan").
- `status` is `HELD` (pending) or `SETTLED`. `transactionType` is null while held.
- Recurring: every Wednesday $100 goes to Jai as $44.54 "Personal Loan" plus $55.46 "Personal Loan - Ex". These are categorised Personal > Life Admin and tagged "Personal loan repayments".

## Categories

- `GET /categories` (not paginated). Parents: good-life, home, personal, transport. Only child categories can be set; a parent id is refused.
- Set: `PATCH /transactions/{id}/relationships/category` with `{"data": {"type": "categories", "id": "<child id>"}}`. Remove: `{"data": null}`. Success is 204.
- Only transactions with `attributes.isCategorizable: true`. Transfers between Up accounts (to $jaiwt, to and from savers), interest and withholding tax are not categorisable.
- Up has no income category. Salary and top-ups can technically be categorised but there's nowhere sensible to put them; refunds are worth categorising.
- Changing a category in the API changes it in the Up app for both people. Only do it when asked.

## Tags

- A tag's id is its label ("Holiday"). `GET /tags` lists only tags currently on at least one transaction.
- There is no create-tag endpoint. A tag comes into existence when it is first added to a transaction: `POST /transactions/{id}/relationships/tags` with `{"data": [{"type": "tags", "id": "Holiday"}]}`. Remove with `DELETE` on the same URL and body. Both return 204; duplicates and missing tags are ignored silently.
- At most 6 tags per transaction.
- `filter[tag]=<label>` on transaction lists; an unknown tag returns zero rows, not an error.

## The 2Up Money page

- Artifact: https://claude.ai/artifact/AuQZD2GhnqQQbnxAcQpHu1 (plain page with `db`, `user`, `downloads` and the `mcp` capability for Claude Code Remote `fire_trigger`). Kaylee Brand colours, light only.
- Page source: `tools/up_money/page/index.html`. Data files it fetches: `data/transactions.json`, `data/categories.json`, `data/balances.json`, `data/tags.json`, built by `tools/up_money/export.py`.
- Its database (Artifact database, `ArtifactData` tool):
  - `changes/<txId>`: `{txId, to (child category id or null to remove), from, status}`
  - `tagChanges/<txId>`: `{txId, add: [labels], status}`
  - `tags/<id>`: tags created on the page that aren't in Up yet `{name}`
  - `meta/sync`: last time Send to Up was pressed; `meta/data`: `{refreshedAt}` of the data files
  - status goes `staged` (picked, not sent) → `pending` (Send to Up pressed) → `applied` or `failed` (with `error`). Only touch `pending` ones; `staged` ones are the person's unsent choices.
- Send to Up starts the task `trig_01Vn5Sabem9CtcM58ZypHzWm` (no schedule: it runs only when the button starts it), which runs the workflow below in a fresh session. If the button can't start it, the changes stay `pending` and the button turns into "Try sending again"; in chat, run the workflow directly.

### Workflow: Apply queued changes from 2Up Money

Work in a scratch folder (call it `$W`), not in the repo.

1. `Artifact` `read` the page url. Note the saved path of the live `index.html` it reports (use that copy when republishing, never the repo copy, so you don't undo a newer published version).
2. `ArtifactData` `list` collections `changes` and `tagChanges` with `out_dir: $W/db`. Keep the version of each document from the listing; every write needs it as `if_version`.
3. If no document has status `pending`: `ArtifactData` `get` `meta/data`. If `refreshedAt` is under 24 hours old, stop. Otherwise skip to step 6.
4. `python3 -I tools/up_money/apply_changes.py $W/db/changes $W/db/tagChanges $W/results.json`
5. `ArtifactData` `batch` (up to 50 writes per call): for each result, `update` that document with `{"status": "applied"}` or `{"status": "failed", "error": "<error>"}`, pinned with `if_version`.
6. Refresh the data: `tools/up_money/fetch_all.sh $W/raw` then `python3 -I tools/up_money/export.py $W/raw $W/site/data`. Copy the live `index.html` from step 1 to `$W/site/index.html`.
7. Republish: `Artifact` publish with `url` = the page url, `file_path` = `$W/site/index.html`, `root` = `$W/site`, `files` = `{"data/transactions.json": "data/transactions.json", "data/balances.json": "data/balances.json", "data/tags.json": "data/tags.json", "data/categories.json": "data/categories.json"}`. Omit `capabilities` so they carry forward.
8. `ArtifactData` `set` `meta/data` to `{"refreshedAt": "<now, ISO>"}` (with `if_version` if it exists).
9. Spot-check one applied transaction with `GET /transactions/{id}` and report applied / failed counts.

### Workflow: Change the page itself

Edit `tools/up_money/page/index.html` (start from the live copy if it differs), check the script parses (`node --check` on the extracted `<script>`), republish to the same url with the same `files`, omit `capabilities` unless a capability changes, and commit the page file. Comments sent to Claude on the page arrive as artifact comment threads: reply and resolve each one you act on.
