# Reply watcher — the Lindy replacement

Lindy was a credit-metered AI agent doing a cron job's work. On Oct 16 it ran
out of credits, and the CoolVu lead that came in that day (Jeff White,
562-551-2241) may never have been called. That failure mode is the problem, not
Lindy specifically — any metered agent has it.

This runs as a Google Apps Script instead. No credits, no subscription, no
third-party service, no server. It lives inside the Google account that already
receives the mail and runs every 5 minutes.

## Install (about 5 minutes)

1. Sign in as the account that receives the Instantly replies — the lead
   alert pointed at `replies@example-grants.com`, so confirm which mailbox
   that actually is before starting.
2. Go to <https://script.google.com> → **New project**. Name it `AGS Reply Watcher`.
3. Create two files and paste in the contents of:
   - `replyGuard.gs` (the classifier)
   - `Code.gs` (the Gmail watcher)
4. Edit the config block at the top of `Code.gs`:
   - `ALERT_EMAILS` — **make the first entry a shared inbox, not a personal
     one.** A single personal inbox is how replies got missed for 8 days.
   - `WATCH_QUERY` — narrow it if the account carries unrelated mail.
5. Run `selfCheck()` from the editor. It should log four PASS lines, including
   the Oct 12 outbound message classified `outbound_self`. Authorize when prompted.
6. Run `setup()` once. Creates the labels and installs the 5-minute trigger.
7. Optional, under **Project Settings → Script Properties**:
   - `SMS_GATEWAY` — your carrier's email-to-SMS address, e.g.
     `7145551234@txt.att.net`, for a text on every real reply.
   - `SLACK_WEBHOOK` — an incoming-webhook URL to post into `#boardroom`.

Watch **Executions** in the left sidebar for the first few runs. Each one logs a
count by category.

## What it does

| Message | Label | Alert |
|---|---|---|
| Our own send | `AGS/Outbound-Self` | none — **this is the Oct 12 fix** |
| Bounce / DSN | `AGS/Reply-Bounce` | none |
| Out-of-office | `AGS/Reply-Auto` | none |
| Real human reply | `AGS/Reply-Human` | starred + email + SMS + Slack |
| Opt-out | `AGS/Opt-Out` | alerted, so they get pulled from Instantly |

It keeps the last 1000 message IDs, so a retry or an overlapping window can
never page anyone twice. On a first run, or after an outage, it looks back at
most 72 hours.

## Keeping it honest

`replyGuard.gs` carries its own copy of the owned-address list because Apps
Script cannot read `config/identities.yml`. Two tests keep the pair in sync:

```bash
# Python is the reference implementation — 54 tests
PYTHONPATH=src python -m pytest tests/ -q

# The Apps Script must agree with it on every fixture — 11 tests
node --test apps-script/parity.test.mjs
```

`tests/test_config_drift.py` fails if the two identity lists diverge, which is
the mistake that would quietly bring the false alerts back on one side only.

**When you add a sending domain to Instantly, add it to both
`config/identities.yml` and `replyGuard.gs` the same day.** The drift test will
catch you if you only do one.

After changing the Python classifier, regenerate the golden file the JS is
held to:

```bash
PYTHONPATH=src python3 - <<'EOF'
import json, pathlib
from agsleads.identity import Identities
from agsleads.reply_guard import classify_raw
root = pathlib.Path('.')
ids = Identities.load(root / 'config' / 'identities.yml')
out = {}
for f in sorted((root / 'tests' / 'fixtures').glob('*.eml')):
    v = classify_raw(f.read_bytes(), ids)
    out[f.name] = {"kind": v.kind, "alert": v.alert,
                   "responder": v.responder, "optOut": v.opt_out}
(root / 'tests' / 'fixtures' / 'expected_verdicts.json').write_text(
    json.dumps(out, indent=2, sort_keys=True) + "\n")
EOF
```

## One thing this does not fix

An alert still needs a human to answer it. The watcher guarantees a real reply
is never hidden and never faked — it cannot make anyone reply within the hour.
That still needs a named owner on the inbox.
