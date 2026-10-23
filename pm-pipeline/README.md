# AGS property-manager lead pipeline

Two jobs:

1. **Stop the reply watcher from alerting on our own mail.** (done, tested)
2. **Build a real CA property-manager list** — Santa Rosa to the border, 29 counties.

## 1. The reply watcher fix

On 2026-10-12 the watcher fired six `NEW LEAD REPLY` alerts for the OC-LA
Property Managers campaign. Every one was our own step-4 follow-up:

```
From: sender1@example-outreach.com      <- us
To:   info@example-propmgmt.com                 <- the prospect
Subject: Re: Who handles entry glass maintenance?
"Last follow-up from me... CA Contractor License #000000"
```

The sequence sends step 4 in-thread, so the subject carried `Re:` and the
watcher read it as inbound. It then classified our own copy as
`negative_or_no_current_need` and asked a human to answer it.

**The campaign's real reply count was 0 of 259. The dashboard said 3.** A total
failure looked like a working campaign for six weeks.

### Drop it into the existing watcher

The watcher itself isn't in this repo — it runs under
`alerts@example-grants.com`. Wherever it decides "this is a reply", call this
first and bail on anything that isn't `human_reply`:

```python
from agsleads.identity import Identities
from agsleads.reply_guard import classify_raw

IDENTITIES = Identities.load("config")

verdict = classify_raw(raw_rfc822_bytes, IDENTITIES)
if not verdict.alert:
    log(verdict.kind, verdict.reason)   # outbound_self | bounce | autoreply
    return                              # never page anyone
send_alert(verdict.responder)            # human_reply — 1 business hour SLA
```

Check a single message from the shell:

```bash
PYTHONPATH=src python -m agsleads.cli check-reply < message.eml
# exit 0 = stay quiet, exit 10 = a human needs to answer
```

Order matters. Direction is checked **before** opt-out detection, because our
own copy ends with `Reply "no thanks" to opt out` — checked the other way round,
the watcher would mark our own prospects as opted out and quietly burn the list.
There's a test for exactly that.

**Add every new sending domain to `config/identities.yml` the same day you add
it to Instantly**, or the false alerts come back.

## 2. The list

```bash
pip install -r requirements.txt

# Universe + phone numbers. Free apart from Places API calls.
GOOGLE_PLACES_API_KEY=... PYTHONPATH=src \
  python -m agsleads.cli build --tiers B,C --region orange_county \
  --exclude /path/to/all_instantly_contacts.csv

# Named people + verified emails.
APOLLO_API_KEY=... MILLIONVERIFIER_API_KEY=... PYTHONPATH=src \
  python -m agsleads.cli enrich --in out/contacts_master.csv
```

Outputs to `out/`:

| File | What it is |
|---|---|
| `contacts_master.csv` | every row including rejects, with the reason — audit trail |
| `email_list.csv` | verified, non-role, named-person rows. Loads into Instantly |
| `call_list.csv` | everything with a phone. Rows with no usable email sort first |

Phone is a column on the contact record, not a separate pipeline — the email
list and call list are two views of the same rows, so nothing drifts between
them.

### Tiers

| Tier | Who | Role inbox |
|---|---|---|
| A | Institutional (CBRE, JLL, Greystar, Irvine Co) | reject |
| B | Regional commercial — the proven segment (the firms already closing with us) | reject |
| C | HOA / community association — best repeat bet, untouched | reject |
| D | Multifamily / apartment operators | reject |
| E | Boutique, 1-10 properties | allow + flag (info@ is often the owner) |
| F | Retail centers, industrial parks, self-storage | reject |

### The rule that matters

No role inboxes on tiers A-D. `info@example-propmgmt.com` and
`management@example-realty2.com` are why 259 sends returned nothing.

**Watch the bounce rate as a quality alarm.** That campaign bounced 0.4%, which
looks excellent and was actually the tell: front-desk catch-alls accept
everything. A real named-contact list bounces 3-5%. If a verified load comes
back near zero, targeting has slipped back to reception.

## Tests

```bash
PYTHONPATH=src python -m pytest tests/ -q
```

50 tests. The reply-guard fixtures are real messages from the campaigns — the
two `outbound_*.eml` files are the exact ones that produced the two false
alerts, and `reply_from_role_inbox.eml` is a real high-intent reply that
came *from* a role inbox, which is why a reply is never suppressed on address
shape.

## Not done yet

- **Evergreen nurture** — the "until asked to stop" sequence. Instantly-side
  config: 4-touch intro, then one new-information touch every 25-30 days,
  indefinitely. Stop only on opt-out, "no thanks", hard bounce, or closed-won.
  Plan separate mailbox pools for intro vs nurture; the nurture tail compounds.
- **Live data pull** — this session's network policy blocks `dre.ca.gov`,
  `cacm.org` and `caanet.org`, so the crawl has not been run. Run it where
  egress is open, or allow those hosts for the environment.
