# Plan: An "AI Agent Browser" for Scraping ISP Plans

## 1. What you're asking for, in plain words

You want something like this:

1. You open Chrome.
2. You see a simple box — like a search bar or a chat box.
3. You type something like: *"Get me TPG and Superloop NBN plans and tell me
   how they compare to Occom"* — in normal English, not a form with dropdowns.
4. The system understands what you meant, goes and scrapes the right
   websites, pulls out the plan names/prices/speeds, checks the data is
   correct, and shows you a clean comparison — including how Occom stacks up
   against those competitors.
5. It should be able to do everything the current `/isp` crawler can already
   do (scrape one ISP, scrape all ISPs, save results, compare old vs new
   runs, show a health report) — just controlled through plain language
   instead of clicking buttons.

**Short answer: yes, this is achievable.** Nothing about it requires
technology that doesn't exist — it's a matter of connecting pieces you
already have to a new, simpler front end, plus adding a "translate English
into a scrape job" step.

## 2. What you already have (the hard part is done)

Your `/isp` folder is a real, working scraper engine. In plain terms, here's
what it already does today:

- **Knows about 27+ Australian ISPs** and their websites (`config.py`,
  `isp/routes.py`).
- **Can scrape a brand-new ISP it's never seen before** by visiting the
  site, guessing which pages have pricing, and pulling out plan cards
  automatically (`isp/url_discovery.py`, `isp/plan_detector.py`,
  `isp/scraper_engine.py`).
- **Checks the data makes sense** before saving it — rejects junk prices,
  impossible speeds, duplicate plans (`isp/validator.py`).
- **Saves everything** to JSON/CSV files, and keeps one big combined file
  (`output/all_plans.json`) that has every provider's latest plans in one
  place.
- **Can run one ISP or all ISPs at once**, shows live progress, and lets you
  come back later and compare "what changed since last time" (price went up,
  a plan disappeared, a new plan appeared) — this is in `isp/routes.py`
  already.
- **Already has a price-comparison brain for Occom** — `utils/benchmark.py`
  groups plans into speed tiers (Basic, Standard, Fast, Superfast, etc.) and
  tells you where Occom is cheaper or more expensive than competitors, plus
  `utils/alerts.py` flags price changes automatically.

So the scraping, checking, saving, and comparing logic all already exists.
What's missing is the **"talk to it in plain English, from Chrome"** part.

## 3. What's new / what needs to be built

### A. A place to type your request ("opens directly in Chrome")

There are two realistic ways to do this — pick one:

**Option A — A simple web page that acts like an app (recommended to start,
now built)**
A single page served by your existing Flask app at
**`http://localhost:5000/agent/`**. You can make Chrome open it like its
own little app window (no address bar, looks like a dedicated tool) using a
Chrome shortcut flag, e.g.:
```
chrome.exe --app=http://localhost:5000/agent/
```
Fast to build, reuses everything you already have, no browser extension
approval process needed.

**Option B — A real Chrome extension**
A small icon in the Chrome toolbar that opens a side panel with the chat
box, everywhere, all the time, in your normal browsing Chrome window. Feels
more like a "built into Chrome" agent. Takes longer to build (extensions
have their own rules and packaging), but is closer to what you described.

*Recommendation: build Option A first (it's basically free, since 90% of the
backend exists), then turn it into Option B later if you still want the
"lives in the browser toolbar" feel.*

### B. A "translator" that turns English into a scrape job

This is the genuinely new piece. When you type something like *"check
TPG and Superloop NBN prices and compare to us"*, something needs to work
out:
- Which providers you mean (TPG, Superloop)
- What network types you care about (NBN)
- What action you want (scrape + compare vs Occom)

This translator will use an AI model behind the scenes to read your sentence
and turn it into a small structured instruction. Rather than locking into
one provider, it'll support **both Claude (Anthropic) and Gemini (Google)**
behind one simple interface — pick whichever is configured as the active
one, with the other ready to switch to at any time. For example:

```json
{
  "providers": ["tpg", "superloop"],
  "networks": ["nbn"],
  "action": "scrape_and_compare",
  "compare_against": "occom"
}
```

That structured instruction is then just handed to your **existing**
crawler code — nothing about the crawler itself changes.

### C. A results view that answers in plain English too

Instead of a raw JSON dump, the chat box should reply with something like:

> "I checked TPG and Superloop's NBN 100 Mbps plans. TPG is $79/mo,
> Superloop is $75/mo. Occom's equivalent plan is $69/mo — you're
> $6–10 cheaper than both."

This is a thin "make it readable" layer on top of the benchmark data that
already exists in `utils/benchmark.py`.

### D. An optional local fallback extractor (Ollama) for tricky pages

This is a different job from the translator (B) — it doesn't read your
English request, it reads a **scraped webpage** when the existing
deterministic engine (`isp/plan_detector.py` / `isp/scraper_engine.py`)
can't confidently find plan cards on a brand-new or unusually-structured
ISP site.

Important distinction: **this does not replace the existing scraper.** The
deterministic selector/embedded-data/text-pattern engine stays the primary
path for every site, because it's faster, free, and already tuned. The
local LLM only gets a page when that primary path comes back empty or
low-confidence — a rare fallback, not the default extraction method.

How it would work:

1. Deterministic engine tries first, as it does today.
2. If it finds nothing (or very low confidence), the page's visible text is
   sent to a **local model running via Ollama** (no cloud, no API key, no
   per-request cost) with a strict instruction: "extract every plan as
   `{plan_name, price, download_speed, upload_speed}`, output JSON only,
   use `null` for anything unsure."
3. Whatever it returns is run through the **existing**
   `isp/validator.py` checks exactly like any other scraped plan — rejected
   if the price/speed look impossible, deduplicated, etc. The LLM's answer
   is treated as untrusted input, same as raw HTML.

**Recommended local model — generic guidance:** `qwen2.5:14b` (via
`ollama pull qwen2.5:14b`) — the Qwen2.5 family is a strong choice for
structured/JSON-style field extraction relative to its size, and 14B is a
reasonable balance of quality vs. hardware needs (~10GB VRAM for the 4-bit
version Ollama uses by default). If your hardware doesn't have that much
VRAM, `phi4:14b` or `qwen2.5:7b` are lighter fallbacks — expect a higher
validator rejection rate from those. If you have a strong GPU (~40GB+
VRAM) and want the best possible local quality, `llama3.3:70b` is the
upgrade option.

**Recommendation tuned to your actual laptop:** checked directly —
Intel Core i5-13420H (8 cores/12 threads), 16GB system RAM, NVIDIA GeForce
RTX 3050 Laptop GPU with **4GB VRAM**. That's an entry-level GPU for local
LLMs, so the generic 14B recommendation above won't fit in VRAM on this
machine — here's what actually fits:

| Model | Fit on this laptop | Use for |
|---|---|---|
| `qwen2.5:7b-instruct` | Fits mostly in the 4GB VRAM (small CPU spillover) — fast, a few seconds per page | **Best pick for this laptop** — the practical ceiling for GPU-accelerated speed here |
| `llama3.2:3b` | Comfortably fits in 4GB VRAM — very fast | Good if you want near-instant responses and can accept a slightly higher rejection rate from the validator |
| `qwen2.5:14b` | Won't fit in 4GB VRAM — Ollama will run most of it on the CPU using system RAM (16GB is enough to hold it) | Usable **only** as an occasional, patience-required fallback (expect roughly 20–60+ seconds per page, not seconds) — fine since Phase 4 is a rare fallback, not a live chat response |
| `qwen2.5:32b` / `llama3.3:70b` | Not realistic on this laptop — would spill heavily to CPU/disk or fail to load | Skip these on this machine |

**Practical starting point for this laptop: use `qwen2.5:7b-instruct` as the
default for Phase 4.** It's the largest model that still runs at a usable
speed on this GPU. Only reach for `qwen2.5:14b` if you specifically find
7B's extraction accuracy too unreliable and are fine waiting longer per
page — test both against a handful of real ISP pages before deciding.

Request shape (via Ollama's local REST API, no key required):

```python
import requests

response = requests.post(
    "http://localhost:11434/api/chat",
    json={
        "model": "qwen2.5:14b",
        "messages": [{
            "role": "user",
            "content": f"Extract every internet plan from this page text as JSON "
                       f"[{{plan_name, price, download_speed, upload_speed}}], "
                       f"use null if unsure:\n\n{page_text}",
        }],
        "format": "json",
        "stream": False,
    },
)
```

This is genuinely optional — the crawler already works without it. It's
worth building only if you find yourself frequently hitting brand-new ISP
sites where the deterministic engine can't find anything at all.

## 4. How it will work, step by step

```
 You type in the box:
 "Scrape Telstra and Optus NBN plans and compare to Occom"
              │
              ▼
 Translator step (Claude or Gemini reads your sentence —
 whichever is configured as active)
 → figures out: providers = [telstra, optus], networks = [nbn],
                 action = scrape_and_compare
              │
              ▼
 Hands the job to your EXISTING isp/main_crawler.py
 → visits the sites, finds plan pages, extracts prices/speeds,
    validates them, saves JSON/CSV (exactly like today)
              │
              ▼
 Hands the fresh plans to your EXISTING utils/benchmark.py
 → compares against Occom's current plans by speed tier
              │
              ▼
 Reply is turned into a plain-English + table answer
 → shown back in the chat box, with a link to the full data if you
    want to dig in (reuses the existing /isp dashboard & health page)
```

## 5. What stays exactly the same

Nothing in `/isp` needs to be thrown away or rewritten:

- Every provider scraper in `providers/` — unchanged.
- The crawler pipeline (discover → detect → scrape → validate → save) —
  unchanged.
- The combined snapshot file `output/all_plans.json` — unchanged, still the
  source of truth.
- Scrape-all, single-provider scrape, results history, run-vs-run
  comparison, health report — all unchanged, all still usable from the
  existing `/isp` dashboard if you want the "old" way too.
- The Occom benchmark/alerts logic — unchanged, just reused.

The new chat box is a **new way in**, not a replacement.

## 6. Suggested build order (phases)

**Phase 1 — MVP chat box (biggest value, least work) — ✅ built**

Lives entirely in a new **`agent/`** folder at the project root, mirroring
how `isp/` is its own self-contained package with its own blueprint:

```text
agent/
├── __init__.py
├── translator.py    # English → structured job (rule-based, no AI call yet)
├── executor.py       # Runs the job via the EXISTING scraper_service.py +
│                      #   utils/benchmark.py — no scraping logic duplicated
├── responder.py       # Turns results into a plain-English + HTML-table reply
├── routes.py           # Flask blueprint `agent_bp`, mounted at /agent
└── templates/
    └── chat_ui.html    # The chat box page
```

Registered in `app.py` the same way `isp_bp` is: `from agent.routes import
agent_bp` + `app.register_blueprint(agent_bp)`. Open `http://localhost:5000/agent/`
to use it.

What it does today:
- Recognizes provider names/network types by matching against `config.py`'s
  `PROVIDERS` dict directly (so newly added providers are picked up
  automatically, no separate list to maintain).
- Supports `scrape_only` ("scrape TPG NBN plans") and `scrape_and_compare`
  ("compare Superloop to Occom") — the latter calls the existing
  `utils/benchmark.py::run_benchmark()` and reports only the speed tiers
  relevant to the providers you actually asked about, not the whole report.
- Scraped plans are saved via the existing `scraper_service.save_output()`,
  so they show up in the normal `output/scrape_isp_<provider>/` files and
  feed the existing benchmark/dashboard tooling — nothing agent-specific.
- Checks `isp/routes.py`'s in-memory crawl state first and returns a "busy,
  try again" message instead of starting a second Playwright job if the
  `/isp` crawler is already running (the concurrency gap flagged in
  section 10).
- Gracefully declines two things instead of guessing: "scrape all"
  (redirects to the existing `/isp` Scrape All button, since that needs
  background-thread progress tracking this MVP doesn't have) and "what
  changed/history" (redirects to the existing `/isp/health` report).
- All scraped plan text is HTML-escaped before being shown back — untrusted
  external data, handled the same way section 7 calls for.

What it deliberately does **not** do yet (this is still Phase 1):
- No AI model call — provider/network recognition is pattern matching
  against known names, not free-form understanding. Ambiguous or
  unrecognized phrasing gets a clear "try rephrasing" message rather than a
  guess. Phase 2 below replaces this translator internals only — routes.py,
  executor.py, and responder.py do not need to change.
- No follow-up/context memory across messages (each message is translated
  independently).
- No fuzzy provider-name matching yet (exact word match against
  `config.py` names/keys) — the fuzzy-matching reuse noted in section 10 is
  a next step, not yet wired in.

**Phase 2 — Smarter understanding (Claude + Gemini, pluggable) — ✅ built**

Lives in a new `agent/translators/` sub-package:

```text
agent/translators/
├── __init__.py          # re-exports translate() / active_provider_status()
├── base.py                # shared Translator interface + AI_SYSTEM_PROMPT +
│                           #   parse_ai_job() (shared JSON parsing/validation)
├── rule_based.py           # Phase 1 logic, moved here — the guaranteed fallback
├── claude_translator.py     # Anthropic backend
├── gemini_translator.py      # Google Gemini backend
└── factory.py                 # picks the active backend via AI_PROVIDER,
                                #   always falls back to rule_based
```

`agent/translator.py` is now a two-line compatibility shim re-exporting
`agent.translators.translate`, so `executor.py`/`routes.py` didn't need to
change at all when this was added.

How selection actually works:
- `AI_PROVIDER` env var picks `claude`, `gemini`, or `rule_based` (default).
- If the chosen backend's SDK isn't installed, or its API key env var isn't
  set, or the API call itself fails/returns invalid JSON — `factory.py`
  transparently falls back to `RuleBasedTranslator`, which never fails. The
  chat endpoint never breaks because of a Phase 2 problem.
- Both AI backends share one prompt (`AI_SYSTEM_PROMPT` in `base.py`) and
  one parser (`parse_ai_job()`), so they're held to the same output
  contract and can't drift into subtly different job shapes.
- **Provider names the AI returns are never trusted as-is** — every name
  goes through `agent/provider_matching.py` (exact match, then fuzzy match
  via `difflib`) against the real `config.py` keys before being used. This
  closes the gap flagged in section 10 (an AI hallucinating a provider name
  would otherwise pass straight through).
- `GET /agent/api/config` reports which backend is configured and whether
  it's actually usable right now (key present, SDK installed) — useful for
  confirming setup without guessing.

**What you still need to do to actually turn Phase 2 on:** add
`ANTHROPIC_API_KEY` and/or `GEMINI_API_KEY` to your `.env` (see
`.env.example`), set `AI_PROVIDER=claude` or `AI_PROVIDER=gemini`, and
`pip install anthropic` / `pip install google-genai` (both added to
`requirements.txt`, marked optional). Without any of that, the agent runs
exactly as it did in Phase 1 — rule-based, no behavior change.

**Phase 3 — Chrome extension — ✅ built**

Lives in `agent/chrome_extension/` — a Manifest V3 extension with a side
panel, so it's available from a toolbar icon in any tab, not just the
`/agent/` web page:

```text
agent/chrome_extension/
├── manifest.json     # MV3, side panel, host permission for localhost:5000
├── background.js      # opens the side panel on toolbar-icon click
├── side_panel.html      # same chat UI as chat_ui.html, sized for a side panel
├── side_panel.js          # calls http://localhost:5000/agent/api/chat directly
└── icons/                  # generated 16/32/48/128px icons
```

It's a thin client — all the actual work (translation, scraping,
comparison) still happens in your Flask app; the extension just gives you
a toolbar-accessible window onto the same `/agent/api/chat` endpoint. It
also calls the new `/agent/api/config` endpoint on open to show a
connection status line ("Connected — translator: rule_based" or "Not
connected — make sure python app.py is running").

**Loading it is a manual, one-time step in Chrome itself — this can't be
scripted from outside the browser:**
1. Make sure `python app.py` is running (the extension talks to
   `localhost:5000`).
2. Open `chrome://extensions` in Chrome.
3. Turn on **Developer mode** (top-right toggle).
4. Click **Load unpacked** and select the `agent/chrome_extension/` folder.
5. Click the extension's icon in the toolbar to open the side panel.

**Phase 4 — Local fallback extractor (Ollama) — ✅ built, off by default**

Lives in `agent/local_llm_extractor.py`, wired into `agent/executor.py`.
Genuinely optional and disabled unless you explicitly turn it on:
`AGENT_ENABLE_LOCAL_LLM_FALLBACK=true` in `.env`.

How it actually behaves:
1. A named provider's normal scraper runs first, exactly as in Phase 1.
2. Only if that returns **zero** plans, and the fallback flag is on, and
   Ollama is actually reachable (`GET /api/tags` on `localhost:11434`) — it
   fetches that provider's known URL (from `isp/routes.py`'s
   `PROVIDER_CRAWL_URLS`) with a plain HTTP GET, strips it to visible text
   with BeautifulSoup, and asks the local model to extract plans as JSON.
3. Every plan it returns goes through the project's **existing**
   `isp/validator.py::ISPValidator.validate_batch()` before being trusted —
   same rejection rules as any other scraped plan.
4. The chat reply flags when a result came from this fallback path
   ("via the experimental local-LLM fallback... double check anything
   important"), so it's never silently mixed in as if it were the regular
   scraper's output.

**Real-world finding while testing this live** (this machine actually has
Ollama running, with `llama3.1:8b`, `qwen3.5:9b`, `qwen3.5:4b`, and
`qwen3:4b-instruct-2507-q4_K_M` already pulled — not the `qwen2.5` models
originally guessed at in section 3.D before checking): the smaller model's
**first** raw response returned a single JSON *object* for only the first
plan on the page, not an array of every plan, despite the prompt asking
for a JSON array — a concrete example of the "less reliable" caveat this
plan already carried, not a hypothetical one. Fixed by (a) making the
prompt more explicit ("there may be several; list all of them... always
wrap in `[ ]`, even for one plan") and (b) making the parser tolerant of a
bare single-object response or a wrapped list under some other key, rather
than silently discarding real data over a formatting slip. `DEFAULT_MODEL`
was updated to `qwen3:4b-instruct-2507-q4_K_M` (small, explicitly
instruct-tuned, and — unlike the earlier guess — actually installed on
this machine already) instead of the originally-guessed `qwen2.5:7b-instruct`.

## 7. Things to be aware of (honest limitations)

- **Some sites actively block bots.** Aussie Broadband already blocks
  automated visits (Cloudflare) — this is why it uses a fixed fallback list
  today instead of live scraping. Any new provider you ask for in English
  could hit the same wall. The system should say "this one's blocked, here's
  the last known data" rather than pretending it worked.
- **English understanding won't be perfect on day one.** Very unusual or
  ambiguous requests may need a follow-up question ("did you mean NBN or
  fixed wireless?").
- **Using an AI model to translate English costs a small amount per
  request** (API usage — fractions of a cent for a short parsing task,
  whether it's Claude Haiku or Gemini Flash) and needs an API key
  configured. Supporting **both** Claude and Gemini means potentially two
  keys/two billing accounts to manage, and a small amount of extra code (the
  translator interface) — a fair trade for not being locked to one vendor,
  but worth knowing it's not "free" compared to picking just one.
- **Scraping etiquette still applies.** Running "scrape all" too often or
  too fast against competitor sites risks getting rate-limited or blocked —
  the existing crawler's pacing/stealth settings should still be respected,
  not bypassed just because a chat box makes it easy to ask.
- **The local Ollama fallback extractor (Phase 4) is meaningfully less
  reliable than Claude/Gemini at getting prices and speeds exactly right**,
  and it needs Ollama actually installed and running on the machine hosting
  the app, plus enough VRAM/RAM for whichever model you pick. Every result
  from it must pass the existing validator before being trusted — treat it
  the same as any other untrusted scrape, not a shortcut around validation.

## 8. What I'd need from you to start building

- Confirm Option A (simple page, fast) vs Option B (real Chrome extension,
  slower) for the "opens in Chrome" part — or start with A and decide on B
  later.
- API key(s) for whichever provider(s) you want enabled in Phase 2:
  - **Anthropic**: console.anthropic.com → API Keys, added to `.env` as
    `ANTHROPIC_API_KEY`.
  - **Google Gemini**: aistudio.google.com → API keys, added to `.env` as
    `GEMINI_API_KEY`.
  - You can supply just one to start (the other slot stays wired but
    unused until a key is added) or both at once.
- Which provider should be the **default/active** one when both are
  configured (this is just a starting setting — easy to flip later).
- A short list of example sentences you'd actually want to type, so the
  translator is tuned to real requests rather than guesses.

## 9. Status — all four phases built

- **Phase 1 (MVP chat box): done, and live-verified against a real
  website, not just mocked.** After building `agent/` (`translator.py`,
  `executor.py`, `responder.py`, `routes.py`, `templates/chat_ui.html`) and
  registering it in `app.py`, I sent real requests through
  `POST /agent/api/chat` on the running Flask app:
  - `"scrape tangerine nbn plans"` → ran a real Playwright scrape of
    Tangerine's actual NBN page, returned 3 real plans, and wrote real
    files to `output/scrape_isp_tangerine/json/` (timestamps confirmed).
  - `"compare tangerine to occom"` → same real scrape, plus a real
    tier-by-tier price comparison against the already-scraped Occom data,
    correctly computed (e.g. "Standard (16-30 Mbps): Tangerine $42.9 vs
    Occom $60.0 — Occom is $17.1 more expensive").
- **Phase 2 (Claude + Gemini pluggable translator): done, code-complete.**
  `agent/translators/` built with the factory/fallback chain described
  above. Verified: config-detection (`AI_PROVIDER=claude` with no API key
  correctly falls back to `rule_based` with no error), and the shared
  parser/prompt path. **Not** verified: an actual live Claude or Gemini API
  call, since that needs your own API key — the code path is ready and
  falls back safely if the key is ever missing or the call fails.
- **Phase 3 (Chrome extension): done, code-complete.** Built in
  `agent/chrome_extension/` (manifest, background script, side panel,
  generated icons). **Not** verified: I can't load an unpacked extension
  into your actual Chrome profile from here — that's a one-time manual step
  in `chrome://extensions` (steps given above). The side panel's JS talks
  to the same `/agent/api/chat` and `/agent/api/config` endpoints the web
  page already uses and live-tested successfully.
- **Phase 4 (local Ollama fallback extractor): done, live-tested, and
  the honest limitation is now empirically confirmed rather than
  theoretical.** This machine actually had Ollama running already — real
  models tested directly, not simulated:
  - `qwen3:4b-instruct-2507-q4_K_M`: fast (2–3s), but **reproducibly only
    extracted the first plan out of three** on a test page, even after
    strengthening the prompt twice and setting temperature to 0. This
    happened consistently across separate attempts, not once.
  - `qwen3.5:4b` and `qwen3.5:9b`: both exceeded a 120-second timeout on
    this hardware without returning a result.
  - A cloud-hosted option (`qwen3.5:cloud`) was tried too and returned
    `410 Gone` — model retired server-side as of today, showing "just use
    the cloud model" isn't a dependable escape hatch either.
  - In response, the code now (a) uses a stronger "extract ALL plans, wrap
    in `[ ]` even for one" prompt, (b) tolerates a bare single-object
    reply instead of silently discarding it, and (c) flags results as
    `possibly_incomplete` via a cheap price-count heuristic, surfaced in
    the chat reply — so an incomplete extraction is visible to you instead
    of silently passed off as complete. `DEFAULT_MODEL` was corrected to
    `qwen3:4b-instruct-2507-q4_K_M` (what's actually installed) instead of
    the originally-guessed, uninstalled `qwen2.5:7b-instruct`.
  - **Bottom line: Phase 4 works as designed, but on real-world testing it
    is genuinely unreliable for multi-plan pages on this hardware** — a
    much stronger version of the caveat this plan already carried in
    section 7, now backed by a reproduced failure rather than a guess.
    It stays off by default (`AGENT_ENABLE_LOCAL_LLM_FALLBACK=false`) for
    this reason.

## 10. Verification pass — what checked out, and what was missing

I went back through this whole conversation and the actual project code
(not just re-reading my own earlier claims) to verify it and catch gaps.

**Confirmed accurate against the real code:**
- The `/isp` folder's capabilities described in section 2 all check out
  directly against `isp/main_crawler.py` and `isp/routes.py` — known-provider
  fallback, URL discovery, page analysis, extraction, global dedup,
  validation, JSON/CSV + combined-snapshot saving, scrape-all with progress
  events, and run-vs-run comparison are all real, working code today, not
  aspirational.
- `utils/benchmark.py` genuinely does speed-tier-based competitive
  comparison already, which is what section 3.C leans on.
- The Chrome "app window" approach (Option A), Ollama's local no-key REST
  API, and the Claude/Gemini/Ollama model guidance all check out against
  how those tools actually work.

**Gaps this conversation hadn't covered — now flagged so nothing gets
built blind:**

- **No access control today.** `app.py` and `/isp` currently have no login
  or API-key gate on the dashboard itself (only `app_api.py`'s protected
  endpoints require a key). A chat box that can trigger scrapes should not
  be exposed beyond your own machine/network without adding at least basic
  auth — otherwise anyone who can reach the page can trigger scrape jobs.
- **Only one crawl can run at a time.** `isp/routes.py` already enforces
  this (`_crawl_lock`, returns HTTP 409 "A crawl is already running") — the
  chat UI needs to surface that clearly ("still working on the last
  request") rather than silently failing or queuing invisibly.
- **The translator's provider names need validation, not blind trust.**
  If Claude/Gemini/Ollama returns a provider name that doesn't match a real
  key in `config.py`'s `PROVIDERS` dict (typo, unknown ISP, hallucinated
  name), it needs to be checked against that list — ideally reusing the
  **fuzzy-matching logic already added in this repo's recent "fuzzy
  plan-rename alerts" work** rather than building a second, separate fuzzy
  matcher from scratch.
- **The benchmark engine is Occom-specific today.** `utils/benchmark.py`
  hardcodes `OCCOM_PROVIDER_ID` as the comparison anchor. That's fine for
  "compare to Occom" requests (the main use case), but if you ever want
  "compare TPG to Superloop" (neither being Occom), that needs a small
  generalization this plan hadn't called out.
- **No cost guardrail on repeated AI calls.** Nothing stops someone typing
  many requests back-to-back and running up Claude/Gemini usage. Worth a
  light rate limit (e.g. per-minute cap) on the translator step once it's
  live, not because cost is high per call, but because there's currently no
  ceiling at all.
- **No accuracy testing plan for the translator itself.** Once Phase 2 is
  built, it's worth building a small evaluation set (a fixed list of
  example sentences with the correct expected JSON) to check translator
  accuracy after any prompt or model change, instead of eyeballing it.
- **Laptop-specific local model sizing was missing until now** — added
  directly above in section 3.D, based on this machine's actual detected
  hardware (i5-13420H, 16GB RAM, RTX 3050 4GB VRAM) rather than generic
  advice.

None of these are blockers — they're small additions to fold into Phase 1/2
rather than reasons to hold off starting.
