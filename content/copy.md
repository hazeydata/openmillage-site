# OM-PAGE-REDO-001 copy (VOICE DRAFT v2 FINAL, Fred voice pass, not for publishing)

## Headline
Your Florida property tax bill is a stack of rates. Here's who sets each one.

## Lede
Your property tax bill isn't one tax. It's several rates stacked up: county, school district, often a city, and special districts you've maybe never heard of. Each one is set by a different board, at a different public meeting.

OpenMillage lines them up, county by county, so you can see what's in your bill and how each piece has moved. Even the countywide base varies a lot: county and school board levies run from 5.64 mills in Monroe to 15.61 in Putnam, with a median of 12.62 across Florida's 67 counties.*

Every number links to the official file it came from. Missing records stay visible as gaps. We don't fill them in, and we don't take a side on the ballot measure numbered 3.

Built by Fred Hazelton and his team of AI bots. Spot a problem? [Tell us](https://github.com/hazeydata/openmillage-site/issues) and we'll fix it in public.

*City rates and local special-district rates come on top. Jacksonville's consolidated rate doesn't apply countywide in Duval, so it isn't included.

## How to read your bill
- **Millage is the rate.** One mill is $1 of tax per $1,000 of taxable value.
- **Your bill adds up several rates.** County, school, city and special districts each set their own, on separate lines.
- **Taxable value isn't market value.** It's your assessed value, which can be capped below market, minus exemptions such as homestead.
- **Rate times taxable value, divided by 1,000, gives each line.** Taxable value can differ by line; part of the homestead exemption doesn't apply to school taxes, for example. Add the lines for your total.
- **Each rate has an owner.** The board named on each line sets it at its budget hearings. That's where to show up.

## Section intros
### The stack (home page)
Here's a Florida property tax bill, one layer per taxing authority. Pick a county to see its stack. Each layer names who sets it and links to the source.

### The stack (county pages)
Here's a typical bill in this county, one layer per taxing authority. Each layer names who sets it and links to the source.

### Over time (history pages)
Here's how each layer has moved since 1996. Missing years show as gaps, not zeros. Alachua County's county and school board countywide rate, for example, fell from 21.2 mills in 1997 to 13.9 in 2025.†

†Alachua's 2002 school rate is shown as published. Two values with source errors are left out.

### Before you vote (ballot measure numbered 3 page)
These are the 2025 adopted rates, as a baseline for whatever comes next. We don't predict the measure's effect, and we don't take a position.

### Who sets what
Every rate comes from a named board. This table lists each one and links to its official filing. DeSoto (1 row) and Orange (3 rows) have special-district rates from their county property appraisers. They're on those county pages but not in the baseline CSV.

### Get the data (home, county and ballot measure pages)
Everything here comes as CSV and JSON, with a source link on every row. Cite it, check it, build on it.

### Get the data (history pages)
Downloads for this history are coming. Until then, every number links to its official file.

## Open questions
- KEY_NUMBER slots: 3 to 5 numbers for Her? and me to pick, computed from repo files with the query recorded, and verified by fact before use. Candidates: how many separate rates a typical county bill has, the share of special-district rates, how a county's total moved from 1996 to 2025.
- Bill math VERIFIED by fact against Fla. Stat. §192.001 (10), (16), (6).
- KEY_NUMBER_1: option (a) wording per fact (Duval footnote, no 'before any special district'); VERIFIED by fact at 791a317 with footnote fix.
- KEY_NUMBER_2: ON HOLD until OM-HIST-FIX-001 merges (ingestion dropped 352 county values). Her? and fact send the final value; † footnote (from Lucille 2) also needs fact's check.
- v2 (Oct 23, Fred's go via Lucille 2): voice pass per hazeydata-voice-guide.md. Every number unchanged (5.64, 15.61, 12.62, 67, 1996, 21.2, 1997, 13.9, 2025, 2002, $1/$1,000). New lines for fact: "Built by Fred Hazelton and his team of AI bots. Spot a problem? Tell us and we'll fix it in public." (contact route: public openmillage-site GitHub issues, per Lucille 2; fact to re-check) and the DeSoto/Orange line, now matches the follow-up wording sent to George Michael (fixes the 'not yet collected' contradiction on main); counts 1 and 3 per George Michael, pending fact.
- KEY_NUMBER_2 FINAL, VERIFIED by fact on fixed history 7c1a525: Alachua 21.206 to 13.851 (shown 21.2 to 13.9); history line unchanged. Contact line VERIFIED (public issues, 200). Copy leftovers: 0.
