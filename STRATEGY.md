# STRATEGY.md — outbound plan (for review)

## Review request — Codex, start here

The owner approved this plan and wants an independent check before anything is
built or loaded. Review it; do not execute it.

**Check for:**
- Gaps — a segment, step or failure mode the plan misses
- Weak assumptions — every item in "Assumptions to pressure-test" below
- Instantly mechanics — campaign structure, sending limits, warmup, the
  evergreen nurture design, whether it can be set up as described
- Deliverability — mailbox/domain math, bounce handling, sending cadence
- Compliance — CAN-SPAM (identification, physical address, working opt-out)
  for an indefinite follow-up sequence
- Sequencing — is the order of operations right for a cash-constrained owner
- Anything that contradicts the data in `AGENTS.md` §4

**Output:** findings ranked most-serious first, each with a concrete change.
Say plainly where you agree. Keep it short — the owner reads bullet points.

**Do not:** email any prospect, load any list, change any campaign, or commit
any real email address, phone number or person/company name. This repo is
public. See `AGENTS.md` §2.

---

## Core strategy

- Stop selling one window at a time — sell to **multipliers**, people who
  control many jobs
- One yes from a glass shop, a property manager, an HOA manager or a grant
  writer = a stream of jobs, not one
- Every campaign leads with **trigger + whose money + deadline + price** — the
  formula behind the grant campaign's $1.59M in funded opportunities
- Named humans only, never front desks
- Always sending, always answered within the hour

## Glass companies — partner channel (start first)

- Every smash-and-grab calls a glass company first — **they are the incident
  feed**, already pre-qualified
- Pitch: *"You replace the glass, we film it so it doesn't break again. You keep
  the customer and earn on every referral."*
- Offer: referral fee per job, or wholesale sub pricing they can mark up
- Evidence: two glass shops replied to the last partner campaign — one asked
  for a referral swap unprompted, one asked for a price list
- List: ~2,500 shops already owned — load this week, $0
- Best reply rate in the program (2.7%) and produces repeat work

## Property managers — repeat engine

- Lead with a **free film-condition audit**, not anti-graffiti — the walkthrough
  that found failing film is what closed the most recent signed PM job
- Failing film = tenant complaints + liability; the audit surfaces work they
  didn't know they needed
- Target named property managers, facilities directors, maintenance supervisors
- Tier B regional commercial first, Tier C HOA managers right behind
- **HOA managers carry 8–15 associations each** — win the manager, win every
  building
- Price in the email: $/sq ft, typical entry-set cost, warranty
- The ~148 companies from the failed campaign are fair game — nobody with
  authority saw it
- **Expand existing accounts:** ask current PM customers for their other
  buildings and their peers

## Grant recipients — big tickets

- Pitch: *"Congratulations on your NSGP award — here's a grant-compliant quote
  you can submit (FEMA AEL 14EX-00-BSIR)."*
- Load the 16 awardees pulled 2026-10-11 (~$2.5M, 14 with phones) — never
  contacted
- Pull every federal NSGP and CalOES cycle the day it publishes
- **Partner with grant writers/consultants** — they write applications for many
  orgs and can spec us in before the award
- Add school districts with safety bonds
- Long approval cycle — next-quarter pipeline, not this month's cash

## Other multipliers

- General contractors — bid invites already arrive regularly; bid every one
- Security integrators (alarm/camera installers) — film completes their package
- Restoration and board-up companies — first responders after break-ins
- National film installation networks — one already sends paid work; ask for
  more territory

## How it runs nonstop

- Minimum 3 live campaigns, staggered starts — never drain together again
- One campaign and one piece of copy per segment
- 4-touch intro over 14 days, then one new-information email every 25–30 days
  indefinitely
- Stop only on: opt-out, "no thanks," hard bounce, closed-won
- 30 days of contacts queued at all times; refill weekly
- ~25 emails/day per mailbox — add mailboxes until at 150–250/day
- Main brand domain stays out of cold sending

## Answering

- One shared reply inbox, one named owner
- Install the Apps Script watcher (`pm-pipeline/apps-script/`) — no credits
- Every real reply: phone call within 1 hour, not an email
- Booking link in every reply so walkthroughs don't wait on the owner

## Order of operations

- **Today:** enable the Instantly connector; unpause the Bay Area campaign
- **This week:** load the glass list and the 16 NSGP awardees; install the
  watcher
- **Week 2:** rebuild the PM list with named contacts; launch the audit-offer
  campaign; start the HOA tier
- **Week 3+:** grant-writer partnerships, GC bids, security integrators; scale
  mailboxes

## Stop doing

- One-shot lists that run dry
- Role inboxes on tiers A–D
- Copy without a price or a reason to act
- Rebuilding the machine instead of running it
- Daily side-agents spending credits on unrelated income experiments

## Money timeline

- New sends → replies 3–14 days → walkthroughs weeks 2–3 → closes weeks 3–8
- **This month's cash comes from work already signed and money already owed**,
  not new sends
- This plan is what keeps the following months from repeating October

---

## Assumptions to pressure-test

| Assumption | Basis | Risk if wrong |
|---|---|---|
| ~25/day per mailbox, 150–250/day total | Common cold-email practice | Domains burn, or volume is lower than planned |
| The audit offer converts PMs | **One** signed job (n=1) | PM tier stays near zero again |
| HOA managers hold 8–15 associations | Industry estimate, unverified | Tier C is less leveraged than claimed |
| Glass shops will refer for a fee | Two replies asking about it | Partner channel is slower than expected |
| Referral fee / sub pricing | **Not yet set** | Can't launch the glass pitch without a number |
| The 2,500-shop list is usable | Owned, never checked | High bounce, or many role inboxes. Many shops are small owner-operators, so the Tier E rule may apply |
| Grant writers will partner | Untested | Grant pipeline stays dependent on award lists only |
| Indefinite 25–30 day nurture is safe | Plan design | Spam complaints, domain reputation, compliance |
| Replies land in 3–14 days, closes in 3–8 weeks | Estimate from past campaigns | Cash arrives later than planned |
| A named human owns the reply inbox | **Unresolved** | Replies go unanswered again — the failure that already happened |
