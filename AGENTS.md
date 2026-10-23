# AGENTS.md — Armored Glass Solutions outbound program

Handoff note for the agent taking over this project. Read this first.

> **Current task:** review `STRATEGY.md` — the owner's approved outbound plan.
> The review brief is at the top of that file. Review only; do not execute.

> **This repository is PUBLIC.** Never commit a live email address, phone
> number, prospect name, API key, or contact list to it. Live identities belong
> in `pm-pipeline/config/identities.yml`, which is gitignored. Lead data lives
> in Gmail and Instantly, not here. Everything in version control uses
> `example-*` placeholder domains on purpose.

---

## 1. What the business is

Armored Glass Solutions (AGS) installs security window film, anti-graffiti film
and DefenseLite polycarbonate in California. Revenue target is $83K/month.
Jobs run from ~$1.7K to ~$140K.

Two things actually produce revenue:

1. **Grant-funded nonprofits** — organizations that have just been awarded
   federal or state security money (FEMA NSGP, CalOES) and must spend it before
   a deadline. Highest value, proven.
2. **Property managers** — commercial, HOA and multifamily. Lower ticket,
   but **repeat**. This is the strategic priority going forward.

Outbound runs through **Instantly** (cold email) plus phone calling.

## 2. Hard rules — do not violate these

| Rule | Why |
|---|---|
| **No role inboxes on tiers A–D** (`info@`, `management@`, `leasing@`…) | A 259-email campaign to front-desk inboxes produced **0 human replies**. This is the single most expensive lesson in the program. |
| **Verify every address before load** | And treat a *low* bounce rate as an alarm, not a win. See §4. |
| **Dedupe against every prior campaign** before loading anything | A contact mailed by two campaigns at once burns the domain and the relationship. |
| **Direction before opt-out** in reply classification | Our own copy ends with `Reply "no thanks" to opt out`. Check opt-out first and you mark your own prospects as opted out. There is a test for this. |
| **Never suppress an inbound reply based on address shape** | A small church's `info@` sent one of the highest-intent replies the program ever got. Role inboxes are bad *targets*; a reply from one is still a human. |
| **Never invent list data** | If a source is unreachable, say so. Do not produce a plausible-looking CSV of contacts that were not actually found. |
| **Do not email prospects without the owner's approval** | Sequences are loaded and launched by a human. Build and stage; do not send. |
| **Honor opt-outs immediately** | Legal requirement, and a dead domain ends the whole program. |
| Develop on a branch, open a draft PR | Never push to `main`. |

## 3. What is already built

Everything lives in `pm-pipeline/`. Python 3.11.

```bash
cd pm-pipeline
pip install -r requirements.txt
PYTHONPATH=src python -m pytest tests/ -q      # 54 tests
node --test apps-script/parity.test.mjs        # 11 tests
```

### 3a. Reply watcher fix — DONE, tested

**The bug it fixes:** on 2026-10-12 the reply watcher fired six `NEW LEAD REPLY`
alerts for the property-manager campaign. Every one was *our own step-4
follow-up*. The sequence sends step 4 in-thread, so the subject carried `Re:`
and the watcher read our own outbound mail as an inbound reply — then
classified our own copy as a rejection and asked a human to answer it.

The campaign's true reply count was **0 of 259**. The dashboard said 3. A total
failure looked like a working campaign for six weeks.

- `src/agsleads/reply_guard.py` — the classifier. `classify()` checks direction
  first: mail from any owned identity is outbound and never alerts. Bounces and
  autoresponders are separated from human replies.
- `src/agsleads/identity.py` — owned-identity matching.
- `tests/fixtures/*.eml` — structural copies of the real messages, including the
  two that produced the false alerts.

### 3b. Lindy replacement — SUPERSEDED, do not install

> **2026-10-23: DOT now owns all reply handling.** Do not install this Apps
> Script — two watchers on one inbox means duplicate alerts. It stays here as
> the reference for the one rule DOT must also follow: **mail from any of our
> own sending identities is outbound and never a lead.** That is the Oct 12 bug.

Lindy was a credit-metered AI agent doing a cron job's work. Its credits ran out
on 2026-10-16 and a lead that arrived that day may never have been called. **The
metering is the failure mode.** Do not replace it with another metered agent.

`pm-pipeline/apps-script/` is a Google Apps Script: 5-minute trigger, runs inside
the Google account that receives the mail, nothing to top up.

Install steps are in `pm-pipeline/apps-script/README.md`. **Blocked on one
unknown: which mailbox actually receives the Instantly replies.** Confirm that,
then install.

`replyGuard.gs` carries its own copy of the owned-identity list because Apps
Script cannot read YAML. Two tests stop the pair drifting:
`apps-script/parity.test.mjs` (JS must agree with Python on every fixture) and
`tests/test_config_drift.py` (the two identity lists must match).

### 3c. List pipeline — BUILT, never run against live data

```bash
GOOGLE_PLACES_API_KEY=... PYTHONPATH=src \
  python -m agsleads.cli build --tiers B,C --region orange_county \
  --exclude /path/to/all_instantly_contacts.csv

APOLLO_API_KEY=... MILLIONVERIFIER_API_KEY=... PYTHONPATH=src \
  python -m agsleads.cli enrich --in out/contacts_master.csv
```

Outputs `contacts_master.csv` (audit trail, includes rejects and reasons),
`email_list.csv` (verified named people, loads into Instantly), `call_list.csv`
(anything with a phone; unreachable-by-email rows sort first).

Phone is a column on one contact record, not a second pipeline, so the email and
call lists cannot drift apart.

**Blocked on:** `GOOGLE_PLACES_API_KEY`, `APOLLO_API_KEY`,
`MILLIONVERIFIER_API_KEY`, and network access to `dre.ca.gov`, `cacm.org`,
`caanet.org`.

## 4. What the data says — do not re-derive this

Campaign performance as of 2026-10-19:

| Campaign | Sent | Bounce | Real human replies | Verdict |
|---|---|---|---|---|
| Nonprofit security grants | 817 | 2.1% | 14 → **7 opportunities** | **The winner** |
| OC-LA Glass Partners | 217 | — | 2 of 73 companies (2.7%) | Best rate, repeat work |
| Bay Area anti-graffiti | 662 | — | ~1, paused | Weak |
| OC-LA Property Managers | 259 | **0.4%** | **0** | Failed — see below |

**Why the winner won:** it named a trigger (*you were just awarded*), whose money
it was (*the grant*), a deadline (*the spend-down window closes*), and proof of
fluency (the FEMA Authorized Equipment List code for security film). Result: 7
funded opportunities representing **$1,591,820 in awarded grant money** from 817
emails, including the largest quote in company history (~$139,924, still pending
grant-authority approval as of 2026-10-13).

**Why the property-manager campaign failed** — three compounding causes, and the
pricing was not one of them:

1. **The list** was generic role inboxes, not named people. Nobody with
   authority ever saw the email.
2. **The copy** contained no price, no product, no trigger and no deadline. The
   subject line asked *"Who handles entry glass maintenance?"* — an org-chart
   question sent to a gatekeeper. It also invited a no ("if it isn't relevant,
   let me know and we'll close the outreach").
3. **The measurement** was broken (§3a), so the dashboard reported 3 replies
   where there were 0, hiding the failure for six weeks.

**The 0.4% bounce rate is the forensic signature.** One bounce in 259 looks
excellent and means the opposite: `info@`/`management@` catch-alls accept
everything. The nonprofit list bounced 2.1% because those were real individual
mailboxes. **A real named-contact list bounces 3–5%. If a verified load comes
back near zero, targeting has slipped back to reception — treat it as a defect.**

**The segment itself is excellent.** Property managers were signing contracts
through other channels during the same period that this campaign returned zero,
including a signed all-windows proposal and a repeat-work purchase order. The
market was never the problem.

**Volume is the other problem.** ~1,955 emails across ~94 days is about
**21/day**. At the proven 0.86% opportunity rate that is one opportunity every
five or six days. The rates are fine; the throughput is not.

## 5. The strategy

### Fix order — this sequencing matters

Do **not** scale sending volume before reply intake works. Opportunities were
already sitting unanswered; more volume just wastes more list.

1. Restore intake — **done 2026-10-23, DOT handles replies.** Verify item 1 in §8.
2. Answer the overdue warm leads. Get the current list from Gmail — search
   `from:alerts@<grants domain> subject:"NEW LEAD"` and the dated "CEO Review"
   emails. **Several were 8–20 days overdue as of 2026-10-19.**
3. Load the next batch before the running campaign exhausts, so sending never
   hits zero.
4. Rebuild the property-manager list properly (§6).
5. Then raise volume.

### The never-stop sequence

The old pattern was a 4-touch list that ran dry. Replace with two stages:

- **Intro, 14 days, 4 touches.** Price-forward: dollars per square foot, typical
  entry-set cost, warranty term. Where a graffiti or vandalism incident near
  their property is known, lead with it.
- **Evergreen nurture, indefinite.** Non-responders graduate to one touch every
  25–30 days, forever, each carrying genuinely new information — updated
  pricing, a finished job nearby, an incident on their block, seasonal timing,
  an insurance or code angle. Never "just bumping this."

**Stop conditions, and only these:** explicit opt-out · "no thanks" · hard
bounce · closed-won.

### Fuel — the three sources that never run dry

The old failure was finite one-shot lists that all drained in the same week.

1. **Money-triggered (highest value, cyclical).** Grant awardee lists — federal
   NSGP and state cycles, school bond and safety measures, county capital
   budgets. Every cycle republishes. A pull on 2026-10-11 found 16 new
   organizations holding ~$2.5M.
2. **Incident-triggered (infinite, daily).** Crime, vandalism and graffiti data:
   county sheriff crime-mapping feeds and city 311 graffiti service requests.
   **This was specced on 2026-09-30 and never built.** It is the only feed that
   produces new names every morning with nobody sourcing a list, and it is what
   makes the property-manager copy work — cite the actual incident at the actual
   property.
3. **Roster (large, already owned).** A ~2,500-company glass and tint shop list
   the business already has. Best-replying segment and it produces repeat work.
   Currently unused.

### Capacity

- Keep a **30-day list buffer**. At 250/day that is 7,500 contacts queued at all
  times, topped up weekly.
- Keep **at least 3 campaigns live with staggered starts.** All four draining
  together is what caused the outage.
- Separate mailbox pools for intro vs nurture — the nurture tail compounds. At
  10,000 accumulated non-responders on a 25-day cycle that is ~400/day on top of
  intro.
- Keep the main brand domain out of cold sending. Warm new mailboxes two weeks
  before they are needed.

## 6. The property-manager rebuild

Target: every property manager in California, **Santa Rosa to the Mexican
border** — 29 counties, defined in `pm-pipeline/config/counties.yml`. Segment
big to small; the goal is all of them.

| Tier | Who | Role inbox |
|---|---|---|
| A | Institutional (national CRE and multifamily operators) | reject |
| B | Regional commercial — **the proven segment** | reject |
| C | **HOA / community association** | reject |
| D | Multifamily / apartment operators | reject |
| E | Boutique, 1–10 properties | allow + flag (`info@` is often the owner) |
| F | Retail centers, industrial parks, self-storage | reject |

**Tier C is the sleeper and nobody has touched it.** One HOA manager carries
8–15 associations, graffiti is a standing complaint item, they hold
board-approved maintenance budgets, and winning the manager wins every
association they hold. That is the definition of repeat. Run it right behind
Tier B.

Target titles are in `src/agsleads/enrich.py` (`TARGET_TITLES`).

The same ~148 companies from the failed campaign are **not burned** — a vague
email died at a front desk and nobody with authority saw it. They are a clean
first shot once there are named contacts and a real offer.

## 7. Measure these

Three of these were never tracked, and their absence is why the program stalled:

- sends/day
- **days of list runway** ← never tracked
- **hours to first reply** ← never tracked; the single highest-leverage number
- reply → opportunity → walkthrough → quote → close
- $ per 1,000 sent
- **source campaign on every opportunity** ← never tracked, so nobody can prove
  which channel produced the biggest quote

## 8. Open items

| # | Item | Blocked on |
|---|---|---|
| 1 | Confirm DOT ignores our own outbound mail (the Oct 12 bug) | Test DOT with one of our own step-4 follow-ups |
| 2 | Answer overdue warm leads | Human decision; list is in Gmail |
| 3 | Run the list build | 3 API keys + network access to the 3 blocked hosts |
| 4 | Build the incident/crime feed | Nothing — specced, never started |
| 5 | Load next batch before current campaign exhausts | List from #3 |
| 6 | Stand up the evergreen nurture campaign | Instantly-side config |
| 7 | ~~A named owner on the reply inbox~~ | **Done 2026-10-23 — DOT handles all replies** |

## 9. Known-good context

- Reference implementation is the **Python**; the Apps Script is a port held to
  it by tests. Fix Python first, regenerate the golden file, then port.
- The Instantly connector exists but was not enabled in the originating session,
  so all campaign figures above came from Gmail notification mail, not the
  Instantly API. Enable it for live campaign state.
- Prior work: PR #2 on this repo.
