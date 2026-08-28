# Full Review — "can't see the forest for the trees"

## When this triggers

"full review," "state of the fund," "where do we stand overall," "let's
evaluate everything against the goal," "I can't see the forest through
the trees," or any version of the CEO asking for the whole picture rather
than a status snapshot. This is different from `brief me`: `brief me` is
"what changed and what needs me," this is "are we actually on track, and
what's the real bottleneck."

Use this when there are too many open threads for the CEO to synthesize
themselves — that's the entire point of the command, so don't wait for a
"big enough" moment to justify it. If the CEO says they can't see the
forest, that's the trigger, full stop.

## Process

### Step 1 — Chief of Staff pulls full context

Read `ops/status.md`, `ops/campaign-log.md`, `ops/decisions.md`, and any
repo docs that define the goal (e.g. the Core v2 charter, the campaign
board). Assemble a single context block: current deficiencies, open
campaigns, blockers, recent decisions. This gets handed identically to
every seat below — no seat answers from a different picture of reality.

### Step 2 — Convene four seats, independently, same question

**In Claude Code:** spawn CIO, Risk/PM, Ops/Compliance, and Performance as
real parallel subagent calls, each given the identical context block from
Step 1. They do not see each other's answers — independence matters here
for the same reason it matters for Red Team: a seat that can see what the
others already said will drift toward agreement instead of surfacing its
own honest read.

**Outside Claude Code:** run each seat's answer yourself in sequence, but
flag that this is the weaker version — genuine independence isn't
possible without separate contexts.

Each seat answers exactly these three questions, from its own mandate:

1. **Distance to goal** — on your specific dimension (research validity /
   portfolio construction / execution & compliance / track record), how
   far is the fund from being real-capital-ready? Be specific, not vague
   ("two deficiencies still open" not "making progress").
2. **The actual bottleneck** — what is the single thing, in your lane,
   that is actually slowing this down? Not a list — the one thing that
   would unblock the most if it were solved.
3. **What you'd do this week** — the concrete next action in your lane,
   if the CEO gave you a green light right now.

### Step 3 — Chief of Staff synthesizes (does not just relay)

Don't hand the CEO four separate reports and call it synthesis. Produce:

- **Where we actually stand** — one paragraph, plain language, no jargon:
  is this a real fund yet, and if not, what would have to be true for it
  to be one?
- **The bottleneck, ranked** — across all four seats' answers, which single
  bottleneck is most load-bearing? (e.g., if Ops says "IBKR approval" and
  Risk/PM says "no diversifying second sleeve yet," but the diversifying
  sleeve doesn't matter until VRP can even trade — sequence them, don't
  just list them.)
- **What's actually the CEO's decision vs. what isn't** — of everything
  raised, which items need the CEO's call right now, and which are staff
  already handling? Don't let four seats' worth of updates read like four
  seats' worth of asks.
- **One next move** — not a list of four next moves, one per seat. The
  single highest-leverage thing to do next, given the ranked bottleneck.

## Output format

```
FULL REVIEW — [date]

WHERE WE STAND: [one paragraph, plain language]

THE BOTTLENECK: [the one thing most load-bearing right now, and why —
name the sequencing if multiple things compete for "the" bottleneck]

BY SEAT:
  CIO — [distance to goal / bottleneck / this week]
  Risk/PM — [same]
  Ops/Compliance — [same]
  Performance — [same]

NEEDS YOU: [the actual decision(s), if any — or "none, staff has this"]

ONE NEXT MOVE: [single highest-leverage action]
```

Keep "where we stand" and "the bottleneck" skimmable even if the CEO
reads nothing else — those two lines are the actual answer to "help me
see the forest." Everything below is support for that answer, not a
replacement for it.
