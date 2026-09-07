# Beauty Partner Incentive Site — Project Spec (CLAUDE.md)

## Editable decisions (change these lines, everything else follows)
- LEADERBOARD_VISIBILITY = named       # anonymous | named
- LEADERBOARD_AUDIENCE   = pros        # pros | managers_only
- LEADERBOARD_TOP_N      = 10          # per category, per month
- EARNED_DEFINITION      = TOTAL_INCENTIVE + TOTAL_TIP + TOTAL_OT + RAMADAN_PRIZE  (everything EXCEPT base salary)
- BENCHMARK_PERCENTILE   = 80

## Objective
A simple page where each Urban Company KSA beauty professional picks their own name from a dropdown
and sees (1) how much they earned in a month, with a breakdown of what it's made of, (2) an anonymous
REAL colleague who did the SAME number of jobs but earned more (rebooking + commission only) with a
higher rating and more rebookings, and (3) a simple explanation of how commission is earned — to
motivate better ratings and rebookings.

DEVIATION FROM THE ORIGINAL "NEVER expose rates/tiers/formulas" RULE: the rebooking-incentive rate
tiers are still never shown -- that part of the rule holds. It was explicitly and deliberately relaxed
for TWO things, each per its own direct, explicit request from the business owner:
  1. A simple, approximate explanation of how the 3% commission threshold works per category (see
     "Commission explainer" below).
  2. Stating the performance-incentive salary threshold ("salary less than SAR 2,300") in the
     performance-incentive caption (see "Performance incentive" under Data, and "Commission explainer"
     section) -- this DOES disclose a base-salary-adjacent number, confirmed explicitly and knowingly by
     the owner after being told the real underlying condition.
Don't extend this relaxation to any OTHER number (rebooking rate tiers, actual per-person salaries,
etc.) without an equally explicit ask, and don't second-guess or walk back either of the two exceptions
above on privacy grounds -- both were raised as concerns and explicitly overridden already.

## Access model — NAME DROPDOWN (single shared page, replaces the earlier private-link design)
- One shared URL. On load: a searchable dropdown listing every active professional's name (grouped
  by category is fine). No L-number entry, no login, no per-person link.
- Selecting a name immediately shows that person's comparison view (see "Page behavior" below).
- Because everyone reaches this from one shared page, ALL professionals' monthly data is embedded in
  index.html (JS data object keyed by name or a stable ID), the same way as before. This is a known,
  accepted tradeoff of the dropdown approach — the page is on GitHub Pages and its content is public.
- Still exclude entirely: base salary, incentive rates, tiers, formulas, and the RATING_INCENTIVE
  breakdown mechanics. Only "earned" totals + rating + rebookings + jobs are ever shown.

## Repo & hosting
- Repo: github.com/SamINurDev/Incentives-calculator → live at https://saminurdev.github.io/Incentives-calculator/
- GitHub Pages must be: main branch, "/ (root)" folder.
- Deploy = replace index.html at repo ROOT, commit, push. Pages redeploys in ~1 min.
- Google Analytics (gtag.js, measurement ID G-67PP4FCR1K) is baked into index_template.html's <head>,
  right after <title>, and must stay there permanently -- it's part of the template now, not a
  one-off addition to a generated file. It survives every `python build_data.py` run automatically.
  Do NOT edit index.html directly to add/remove it; edit the template instead.

## Data
- Input: monthly .xlsx files, sheet name "result". Columns:
  PROVIDER_ID, PROVIDER_NAME, L_NO, CATEGORY, CITY, VISA_TYPE, PAYABLE_DAYS, AVERAGE_RATING, JOBS,
  REBOOKING_COUNT, REBOOKING_INCENTIVE, TOTAL_TIP, PERC_COMM, PERFORMANCE_INCENTIVE, RATING_INCENTIVE,
  REFERRAL_INCENTIVE, SHADOWING_INCENTIVE, RAMADAN_PRIZE, TOTAL_OT, TOTAL_INCENTIVE, RETRAINING_DAYS_DEDUCTION.
  (RATING_INCENTIVE/RAMADAN_PRIZE are absent from the Jarvis-sourced query below entirely -- they were
  never real columns there, not "missing data"; still defaulted to 0 defensively in load_month().)
- Key internally by PROVIDER_ID, NOT L_NO (see the PROVIDER_ID note further down -- L_NO can collide
  between two different real people).
- Active = rows with JOBS > 0 only.
- SOURCE OF TRUTH is now the Jarvis/Redash saved query "Updated Beauty Timesheet Query 2026" (query id
  506684, data_source_id 20, at https://jarvis.urbancompany.com). It takes one parameter,
  `date_range` (start/end date strings), and returns EXACTLY the columns above (confirmed 2026-09-06).
  Calling the API directly (not through a wrapper skill) requires both
  `Authorization: Key <api_key>` AND `X-Client-Id: uc-data-analysis-agent/1.0` headers, or it 403s.
  POST the query's own SQL (fetched via GET /api/queries/506684) to /api/query_results with
  `{"data_source_id":20,"query":<sql>,"parameters":{"date_range":{"start":...,"end":...}},"max_age":0}`,
  poll /api/jobs/<id> until status 3, then fetch /api/query_results/<query_result_id>. Convert the
  returned {columns, rows} to a DataFrame and write it to <Month>_incentives.xlsx, sheet "result", to
  slot into the existing pipeline unchanged. Manual xlsx uploads from ops are still a valid fallback
  path if this API is unavailable -- both feed the same load_month() function.
- CITY MULTIPLIER (discovered 2026-09-06 while investigating the "other bonuses" 2x-residual mystery
  from mid-August): the source SQL doubles (REBOOKING_INCENTIVE + PERC_COMM) for any pro whose CITY is
  NOT Riyadh or Jeddah (multiplier 2 vs 1) before summing into TOTAL_INCENTIVE. This is a real,
  intentional business rule, not a data bug -- confirmed directly against the SQL
  (`MAX(CASE WHEN a.city IN ('Riyadh','Jeddah') THEN 1 ELSE 2 END) AS multiplier`) and reconciles
  TOTAL_INCENTIVE to the itemized columns with EXACTLY zero residual for June/July/August (April/May
  still carry a small residual, presumably an older query version). build_data.py's load_month()
  computes CITY_MULT per row and applies it to ADJ_RBI/ADJ_COMM (used everywhere rbi/comm/yc/COMPARE
  are used) so the displayed "Rebooking incentive"/"Commission" already reflect what the pro actually
  earned, not the pre-multiplier raw column value. Do not remove this multiplier without re-checking
  the source SQL first -- removing it will silently reintroduce the "mystery" residual for every pro
  outside Riyadh/Jeddah (the majority of the roster).
- PERFORMANCE INCENTIVE: the source SQL's actual condition is
  `basic_salary IN ('2000','1700') AND average_rating >= 4.85 THEN 300`. The business owner was told
  this exact condition (not just "less than 2300") and, after that, EXPLICITLY confirmed twice that the
  salary threshold should be stated on the page anyway, in their own words ("salary is less than 2300").
  This is now a CONFIRMED, DELIBERATE second exception to the original "never expose base salary" rule
  (same status as the commission-explainer exception) -- do not revert it, and do not re-raise the
  privacy concern as if it were still open; it was raised and the owner overrode it knowingly.
  Only the resulting PERFORMANCE_INCENTIVE AMOUNT (already in the xlsx, no salary column ever touches
  this pipeline) is a real number pulled from data; the "SAR 2,300" / "high rating" wording in the UI
  caption is static, hand-approved text -- NOT derived from or read out of the actual SQL threshold
  (which is really "salary IN (2000, 1700)" and "rating >= 4.85", not "< 2300"). If the real thresholds
  ever change, this caption will silently go stale -- there is no code path connecting them. Caption
  currently: "Performance incentive is given to professionals whose salary is less than SAR 2,300 and
  who maintain a high rating." Do not touch this wording without an equally explicit ask, in either
  direction (neither hiding it again nor "correcting" it to the literal SQL thresholds).
- "Earned" (this view) = EARNED_DEFINITION above. Use the RECORDED values; do NOT recompute from a formula.
- Categories: "Salon Nails", "Spa for Women", "Advanced Facecare", "Hair for Women".
- If two professionals share the exact same display name, disambiguate in the dropdown (e.g. append
  city or last initial) so selection is unambiguous.

## Peer benchmark (per professional, per month) — for the comparison card
- WHO COUNTS AS A PEER / WHO GETS PICKED AS THE EXEMPLAR is still based on REBOOKING_INCENTIVE +
  PERC_COMM ONLY (the "COMPARE"/"yc" metric, tips and OT/ramadan/etc. excluded) — this part is
  unchanged. Consider active pros that month with JOBS within ±10 of this pro (widen to ±25, then ±40,
  if fewer than ~8 peers); among those whose COMPARE is more than this pro's, PREFER candidates with
  strictly higher AVERAGE_RATING AND more REBOOKING_COUNT; from that set pick the exemplar at
  ~BENCHMARK_PERCENTILE of COMPARE (a strong but real example, not an extreme outlier). If nobody
  scores higher on COMPARE, mark this pro a TOP PERFORMER (positive message, no peer).
- WHAT GETS DISPLAYED in the comparison bars is intentionally ASYMMETRIC (explicit request): the
  viewer's own bar shows their FULL "you earned" total (EARNED_DEFINITION, tips included) -- the exact
  same number as the hero. The colleague's bar stays at their COMPARE metric (rebooking + commission
  only, no tips) -- we don't know/show a stranger's tips. The gap note ("+SAR X within reach") is
  peer.e - you (full), and is HIDDEN (not shown as zero/negative) whenever the viewer's full total
  already meets or exceeds the colleague's partial figure.
  KNOWN TRADEOFF: because the exemplar is selected on COMPARE but displayed against the viewer's FULL
  total, ~13% of active pro-months (measured directly against the April-July data) end up with the
  viewer's bar visually LONGER than the "colleague who earned more" bar, with no gap note shown. This
  looks inconsistent but is the direct, deliberate consequence of comparing two different metrics side
  by side. Don't "fix" this by changing the peer-selection metric back to match the display metric
  without checking first -- it was called out and accepted as-is.
- Show the exemplar ANONYMOUSLY: only the comparison amount, rating, and rebooking count. NEVER a name
  or L_NO.

## Category leaderboard (all 4 categories, top LEADERBOARD_TOP_N)
- Originally hair-only; generalized to all 4 categories after the site went live, because hiding the
  leaderboard for everyone except hair pros looked like a bug ("I can not see the leaderboard?") when
  it was actually working as originally spec'd. Every pro's own category now gets a top-10 leaderboard.
- Ranked by earned DESC, top LEADERBOARD_TOP_N (=10) per category per month. Hair naturally has only
  ~3-9 pros/month, so it still effectively shows everyone including zero earners (e.g. Christine
  Padayao must appear even with 0) -- Nails/Spa/Facecare have 80-120+ active pros, so top 10 only, NOT
  everyone (a full scrolling list of 100+ was explicitly ruled out for those categories).
- Respect LEADERBOARD_VISIBILITY / LEADERBOARD_AUDIENCE (currently: named, shown to pros) -- each card
  shows the pro's display name (not L_NO/PROVIDER_ID), rating, rebooking count, and earned amount. The
  viewer's own card shows "You" instead of their name -- but ONLY if they're actually in that
  category's top 10; if not, no card is highlighted (there's no "show my rank outside top 10" feature).
- Each card's stat line spells out "rebooking(s)" in full (not "reb.") to keep the emphasis on rating
  and rebookings as the two levers that actually move earnings.
- LAYOUT: display all entries SIDE BY SIDE in a single row of cards (flex/grid, no vertical scrolling
  list) — e.g. equal-width cards laid out horizontally, wrapping to a second row only if the viewport
  is too narrow to fit them. On mobile, cards may wrap 2-per-row rather than a long scrolling list.
  Highlight the viewer's own card distinctly (e.g. berry border/background).
- The section eyebrow/subtitle is generated from the viewer's own category (CAT_LABELS lookup), not
  hardcoded to "Hair for Women" anymore.

## Page behavior (index.html — ONE static file, no backend)
- Landing: name dropdown (searchable/typeahead), grouped by category. Nothing else shown until a name
  is picked.
- After picking a name: greet by first name; "You earned SAR X" hero (full EARNED_DEFINITION, tips
  included, with rating/jobs/rebookings) and month tabs (derived from that pro's data, so new months
  appear automatically) are ALWAYS visible, above everything else.
- Below the hero, content is split into SECTION TABS (not one long scrolling page -- switching this
  from a scroll to tabs was itself a direct request, after "why can't I see the leaderboard" turned out
  to mean "I don't want to scroll to find it"). Exactly one section panel is visible at a time:
    1. Breakdown (default tab) -- Rebooking incentive / Commission / Tips / Other bonuses, summing
       exactly to the hero total. ("Other bonuses" = OT + Ramadan + any other incentive component
       bundled into TOTAL_INCENTIVE beyond rebooking incentive + commission -- e.g. performance/
       rating/referral/shadowing incentives. Still no rates or formulas, just recorded amounts.)
    2. Compare -- "A colleague with the same N jobs earned SAR Y" (colleague = rebooking + commission
       ONLY; see "Peer benchmark" above for the asymmetric-display caveat) with the colleague's rating
       and rebookings; two comparison bars (You = full total incl. tips, vs colleague = partial metric)
       + gap note (hidden when the gap isn't positive); top-performer case ("You're among the highest
       earners...", no peer); a 0-jobs month shows "No comparison to show for a month with 0 jobs"
       instead of either.
    3. Leaderboard -- top-10 side-by-side cards, defaults to the viewer's own category, but has its
       OWN sub-tabs (one per category) so anyone can browse any of the 4 categories' leaderboards, not
       just their own. "Me" highlighting only ever applies on the viewer's own category tab (a Nails
       pro browsing the Hair leaderboard is never highlighted there -- she isn't in it). Switching the
       category sub-tab does NOT change which category's DATA/comparison card you're looking at
       elsewhere on the page -- it's purely a leaderboard browsing view sourced from the global BOARDS
       table (see "Data embedding shape").
    4. Commission -- the explainer below, viewer's own category tagged.
    5. Calculator -- see "Earnings calculator" below.
  Switching month tabs re-renders whichever section tab is currently active (and refreshes the
  Calculator's slider prefill -- see below); it does not reset which section tab is selected. Picking a
  NEW name always resets back to the Breakdown tab.
- A "change name" control lets anyone switch to a different name from the same page.
- NO tier rates, NO base salary anywhere. The two exceptions are the commission explainer and the
  calculator below -- everything else stays hidden.

## Earnings calculator (deliberate exception -- reuses real, hidden rate tiers)
- Two sliders: "Your average rating" (4.00–5.00, step 0.01) and "Rebookings this month" (0–60). Output:
  "Estimated rebooking incentive: SAR X", plus a generic nudge message with NO numbers in it (e.g.
  "Raise your rating...", "You're at the top rating tier...").
- Internally computes X = rebookings × rate(rating), using the REAL tiers: rating >= 4.97 -> 18/rebook,
  >= 4.90 -> 15/rebook, >= 4.85 -> 8/rebook, else 0. These tiers/thresholds are the same real numbers
  used by the business, but are NEVER printed anywhere in the UI text -- only the resulting SAR
  estimate and generic guidance. (Anyone opening dev tools / view-source could still find the constants
  in the JS -- that's an accepted limitation of doing this client-side with no backend, same tradeoff as
  the rest of this site. Hiding them from the UI text is the practical ceiling here, not true secrecy.)
- On opening a name (or switching months), the sliders prefill from that pro's actual rating/rebookings
  for the currently selected month, so the calculator opens already reflecting reality -- then the pro
  can slide from there to see "what if".
- This does NOT compute commission or any other incentive component -- rebooking incentive only, per
  the original request ("check maximum earning potential by sliding rating and number of rebookings").

## Commission explainer (deliberate, explicit exception -- see "DEVIATION" note above)
- Static text, same for everyone, always shown after a name is picked (not gated by month). Lists all
  4 categories, with the viewer's own category tagged "Your category". Unified to the same ~90
  jobs/month threshold for all 4 categories (originally 88/80/100/100 per category, simplified to one
  round number on request):
      Salon Nails, Spa for Women, Advanced Facecare, Hair for Women  ->  over ~90 jobs/month, all four
  Copy: "once you pass about {N} jobs in a month (roughly SAR 15,000 in total job value), you earn 3%
  commission on the value of every job above that."
- These are approximate, illustrative numbers given directly by the business owner — the real trigger
  is total job VALUE (~SAR 15,000), not the job count alone; the job-count figures are a rough proxy.
  Label it clearly as approximate in the UI. Do not present these as exact/guaranteed thresholds.
- This is the ONE deliberate exception to "never expose formulas" -- don't generalize it to also
  reveal rebooking-rate tiers or base salary.

## Data embedding shape (in index.html)
const DATA = {
  "<PROVIDER_ID>": { "name": "...", "cat": "...",
    "m": { "June": { "j":jobs, "r":rating, "rb":rebookings,
                     "you":earned_full_incl_tips,           // hero "You earned" figure
                     "yc":earned_rebooking_plus_commission, // comparison-bars "You" figure (no tips, city-adjusted)
                     "rbi":rebooking_incentive, "comm":commission,   // BOTH already city-multiplier-adjusted
                     "tip":tips, "perf":performance_incentive, "other":other_bonuses,
                     // breakdown -- rbi + comm + tip + perf + other must always sum to "you"
                     "peer": {"e":rebooking_plus_commission,"r":rating,"rb":rebookings} | null,
                     "lb":  [ {"n":name,"e":earned,"r":rating,"rb":rebookings,"me":true|false}, ... ] | null } } },
                     // "lb" here is ALWAYS the viewer's own category's top-10, personalized ("me" set).
  ...
};
const NAMES = [ {"l":"<PROVIDER_ID>","label":"Display Name (disambiguator if needed)"}, ... ]   // powers the dropdown
const BOARDS = {
  "June": { "<CATEGORY>": [ {"n":name,"e":earned,"r":rating,"rb":rebookings}, ... top 10 ... ], ... 4 categories ... },
  ...
};   // global, unpersonalized (no "me") -- lets the Leaderboard tab's category sub-tabs show ANY
     // category, not just the viewer's own (which comes from DATA[pid].m[month].lb instead, since
     // that copy has "me" flags baked in). Injected via the __BOARDS__ marker in index_template.html.

## Build script (build_data.py — replaces make_links.py; no more per-person links)
- Config at top: MONTH_FILES mapping label→path, BENCHMARK_PERCENTILE=80. Current state:
      MONTH_FILES = {
        "April": "April_incentives.xlsx",
        "May":   "May_incentives.xlsx",
        "June":  "June_incentives.xlsx",
        "July":  "July_incentives.xlsx",
        "August (1-16)": "August_incentives.xlsx",   # partial month, see below
      }
  Note the "August (1-16)" key: when a month's file is a PARTIAL snapshot (check PAYABLE_DAYS -- a
  full month is usually ~28-31, a partial one will be visibly less, e.g. 16), label the MONTH_FILES key
  with the day range so the tab itself reads "August (1-16)" rather than looking like a full month's
  total. Any string works as the key/tab label; once the real full-month file for that month arrives,
  replace the partial key with the plain month name and re-run the build -- don't keep both.
- Reads the months, computes earned + peer benchmark + top-10 category leaderboard per pro per month,
  builds the DATA + NAMES + BOARDS objects above, and injects them into index_template.html (markers
  __DATA__, __NAMES__, __BOARDS__) to produce index.html.
- Keyed internally by PROVIDER_ID, NOT L_NO. L_NO looked unique but isn't: the source spreadsheets
  have at least 3 confirmed cases of two different people sharing the same L_NO (e.g. L_204015 is
  both "April Anne Vivero" and "Mary Grace A. Decastro" in every month file). Keying by L_NO silently
  merges such pairs into one record and drops one person entirely. PROVIDER_ID is the actual unique
  system ID — always key on that; treat L_NO as a display/reference field only.
- Also drops the literal "Sami - Test" dummy row (0 jobs, no L_NO) that appears in each month file.
- Normalize L_NO whitespace for display purposes. Requires: pip install pandas openpyxl.

## ADDING A NEW MONTH (e.g. August) — the routine each cycle
1. Put the new file in the folder as "August_incentives.xlsx" (sheet "result", same columns).
2. In build_data.py MONTH_FILES, add: "August": "August_incentives.xlsx".
3. Run: python build_data.py   → regenerates index.html with August included (August tab appears
   automatically for every pro who has August data).
4. Commit and push index.html to redeploy.

## Design (warm, premium, mobile-first) — "Lacquer" theme
- background #FBF6F4, ink #2A1A22, berry accent #B4285E, plum #6D2E5B, gold #B07C2E.
- Fonts via Google Fonts: Bricolage Grotesque (display + numbers) + Inter (body). Tabular numerals for figures.
- Rounded cards (~20px), soft borders (#EEE1DC), subtle shadows. Clean and legible on a phone.
- Dropdown should be a proper searchable/typeahead control (typing filters the name list), not a giant
  native <select> with 350+ unsorted options.

## Git hygiene
- Create .gitignore containing:  *.xlsx
  (The raw monthly spreadsheets should not be committed. index.html itself will contain the embedded
  data by design of this dropdown approach — that is expected and intentional here.)
- index_template.html, build_data.py, CLAUDE.md, .gitignore, and index.html belong in the repo.

## Validation before you call it done
- The page JS must parse (run `node --check` on the extracted script).
- Confirm the dropdown lists every active pro across all months, disambiguating duplicate names.
- Confirm a hair pro with 0 earned appears in the hair leaderboard, laid out side by side with the
  others (not a scrolling list).
- Confirm the leaderboard shows for ALL 4 categories, not just hair, capped at LEADERBOARD_TOP_N (=10)
  for the larger categories (Nails/Spa/Facecare), and that the section title reflects the viewer's own
  category rather than being hardcoded to "Hair for Women".
- Confirm picking a top-performer name shows the positive message with no peer card.
- Confirm switching names via "change name" updates the view correctly without a page reload glitch.
- Confirm only ONE section panel (Breakdown/Compare/Leaderboard/Commission/Calculator) is visible at a
  time, picking a name always lands on Breakdown, and switching months keeps the currently active
  section panel selected (doesn't bounce back to Breakdown).
- Confirm the Leaderboard tab's category sub-tabs can show a category OTHER than the viewer's own
  (sourced from the global BOARDS table), with no "me" highlight in categories the viewer isn't in, and
  the highlight correctly reappears when switching back to their own category.
- Confirm the Calculator prefills from the viewer's real rating/rebookings for the selected month, that
  sliding to rating=5.00/rebookings=60 gives the mathematically correct maximum (60 × 18 = SAR 1,080),
  and that no rate number (8/15/18) or rating threshold (4.85/4.90/4.97) appears anywhere in the visible
  page text at any slider position.

## Deliverables
1) index_template.html   2) build_data.py   3) .gitignore   4) index.html (generated)   5) a short deploy note.
