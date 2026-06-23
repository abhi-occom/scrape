# Australian Internet Plan Tracker — Simple Project Guide

## What Is This Project?

This project is a tool for collecting and comparing internet plans offered by Australian providers.

Instead of visiting many provider websites one by one, the tool can gather plan information automatically and place it into one combined list.

It collects information such as:

- Internet provider
- Plan name
- Internet speed
- Monthly price
- Discounted price
- Discount duration
- Contract details
- Network type, such as NBN, fibre, fixed wireless, 5G, or satellite
- The web page where the information was found

The project can then display this information in dashboards, downloadable files, reports, and Google Sheets.

---

## Why Was It Created?

Internet plan information changes regularly. Providers may:

- Introduce new plans
- Remove old plans
- Increase or reduce prices
- Start or end special offers
- Change internet speeds
- Change contract conditions

Checking every provider manually would take a significant amount of time and could lead to missed information.

This project reduces that manual work. It creates a central place where internet plans can be collected, reviewed, compared, and monitored.

---

## What Does the Tool Do?

The tool performs six main jobs:

1. Visits internet provider websites.
2. Finds pages containing internet plans.
3. Collects important plan information.
4. Organizes the information into a standard format.
5. Saves the results for review and download.
6. Creates comparisons, alerts, and pricing reports.

---

## Who Can Benefit From It?

The system may be useful for:

- Sales teams
- Marketing teams
- Pricing teams
- Product managers
- Business analysts
- Internet service providers
- Comparison websites
- Customer support teams
- Managers monitoring competitors

No programming knowledge is required to view the dashboards, download reports, or review the saved plan data.

---

## Providers Covered

The main provider list includes:

- Telstra
- Optus
- Aussie Broadband
- Superloop
- Occom
- TPG
- Exetel
- Leaptel
- iiNet
- Swoop
- iPrimus
- Dodo
- Kogan
- More
- Tangerine
- MATE
- Spintel
- Origin Energy
- Airtel
- Alpha
- City7Net
- Epsinet
- IQNet
- New Aus Fiber
- VOCPhone

The system also contains saved information for some additional providers discovered or added during previous collection runs.

---

## How Does It Collect Information?

The tool has two ways of collecting plans.

### Method 1: Provider-specific collection

Many providers have their own dedicated collection process.

This is similar to giving the tool special instructions for each website. These instructions tell it where the plan names, prices, speeds, discounts, and other details normally appear.

This method usually provides the most accurate results for known providers.

### Method 2: Automatic website search

The tool also has a general-purpose website crawler.

A user can enter an internet provider’s website address. The crawler will:

- Look through the website
- Find pages that appear to contain internet plans
- Review the page content
- Identify possible prices and speeds
- Collect plan details
- Check whether the results appear valid

This is useful when a provider does not yet have a dedicated collection process.

---

## What Information Is Saved?

Each plan is normally saved with the following details:

| Information | Meaning |
| --- | --- |
| Provider | Company offering the plan |
| Network type | NBN, fibre, 5G, fixed wireless, satellite, and similar |
| Plan name | Name used by the provider |
| Download speed | How quickly customers can receive data |
| Upload speed | How quickly customers can send data |
| Regular price | Normal monthly cost |
| Promotional price | Temporary discounted monthly cost |
| Promotion period | How long the discount applies |
| Contract | Contract length or month-to-month details |
| Evening speed | Expected speed during busy evening hours |
| Source page | Website page where the plan was found |

Not every provider displays every detail. A field may be empty when the source website does not provide the information clearly.

---

## Current Saved Information

The latest combined saved file reviewed for this document was created on June 16, 2026.

It contained:

- 391 internet and telecommunications plans
- 32 saved provider groups

These figures describe the saved data at that time. They may change after a new collection run.

The number of saved provider groups is larger than the main provider list because the system can retain information from extra providers discovered or added during earlier runs.

---

## Main Dashboard

The main dashboard is available at:

```text
http://localhost:5000
```

From this dashboard, a user can:

- View the provider list
- Collect plans from one provider
- Collect plans from all enabled providers
- Choose whether to watch the browser while it works
- Follow collection progress
- View recently captured website screenshots
- Review saved results
- Download JSON or CSV files

The dashboard runs on the computer hosting the project. The application must be started before the address can be opened.

---

## Automatic ISP Crawler

The automatic crawler is available at:

```text
http://localhost:5000/isp
```

A user can enter a provider website and ask the tool to search for plans.

The crawler can show:

- Which website pages it checked
- Which pages appeared to contain plans
- How many plans were found
- Which network types were detected
- Whether any errors occurred
- How long the process took

It also keeps previous results so users can compare one collection run with another.

---

## Health Report

The crawler health report is available at:

```text
http://localhost:5000/isp/health
```

This report helps users understand:

- Which providers were collected successfully
- Which providers failed
- How many plans were found
- Whether the number of plans changed
- Whether pages produced errors
- How recent the saved information is

This is useful for identifying providers that may need attention.

---

## Downloadable Files

The tool saves plan information in two common formats.

### CSV files

CSV files can be opened in:

- Microsoft Excel
- Google Sheets
- Apple Numbers
- Most reporting and data tools

CSV is the easiest format for non-technical users who want to filter, sort, or compare plans in a spreadsheet.

### JSON files

JSON files are mainly intended for:

- Other software systems
- Websites
- APIs
- Developers
- Automated reporting tools

Non-technical users will usually prefer the CSV files or dashboards.

---

## Where Are the Results Stored?

The main combined files are:

```text
output/all_plans.json
output/all_plans.csv
```

Each provider also has its own folder containing separate files.

For example:

```text
output/scrape_isp_telstra/
output/scrape_isp_optus/
output/scrape_isp_occom/
```

The system also stores:

- Website screenshots
- Activity logs
- Previous crawler results
- Price comparison reports
- Alert history
- Value reports

---

## Google Sheets Integration

The tool can update a prepared Google Sheet with selected NBN pricing.

The Google Sheets page is available at:

```text
http://localhost:5000/sheets
```

The usual process is:

1. Open the Google Sheets page.
2. Connect an authorized Google account.
3. Run a test or “dry run.”
4. Review the proposed updates and warnings.
5. Run the real synchronization.

The system attempts to match:

- Providers
- Internet speed levels
- Regular prices
- Promotional prices

It excludes plans that are clearly related to mobile phones, travel SIMs, prepaid services, or similar non-NBN products.

The spreadsheet must have the expected provider and speed headings for the synchronization to work correctly.

---

## Competitor Price Comparison

The system can compare Occom’s pricing with competitor plans.

Plans are grouped into speed categories, from basic services through very high-speed services.

For each speed category, the report can show:

- The cheapest provider
- The most expensive provider
- The best speed-for-price value
- Whether Occom is the cheapest
- How much Occom saves compared with the next provider
- How far Occom is behind when another provider is cheaper
- Estimated first-year cost

The comparison dashboard is available at:

```text
http://localhost:5000/benchmark
```

The report must be generated before this page will contain current information.

---

## Price and Plan Alerts

The system can compare the latest plans with an older saved copy.

It can identify:

- Price increases
- Price decreases
- Changed discounts
- New plans
- Removed plans
- Competitors offering a lower price than Occom

Alerts are marked with levels such as high, medium, or low to help users prioritize their review.

The alert process only becomes fully useful after at least two data collections, because the system needs an older copy for comparison.

---

## Value and ROI Calculator

The project contains a value calculator that compares internet speed with monthly price.

For example, a plan offering a high speed for a relatively low price will receive a better value score.

The report considers:

- Internet speed
- Regular price
- Promotional price
- Estimated first-year cost
- Speed received for each dollar spent

The value dashboard is available at:

```text
http://localhost:5000/roi
```

This report can help answer questions such as:

- Which plan offers the best value?
- Which provider gives the most speed for the price?
- Does a discount make a plan more attractive?
- How much might the customer pay during the first year?

---

## Website Screenshots

While collecting information, the system can save screenshots of provider websites.

Screenshots help confirm:

- Which page was opened
- Whether the website loaded correctly
- Whether a plan page changed
- Whether a login, address check, error, or security screen appeared
- Why a collection run may have failed

They are stored in provider folders under:

```text
output/screenshots/
```

---

## Visible Browser Mode

The dashboard can run a collection with a visible browser.

This allows a user to watch the tool:

- Open a provider website
- Move between pages
- Load plan information
- Interact with parts of the website

Visible mode is mainly useful for investigation and troubleshooting. Normal scheduled collection would usually use hidden browser mode.

---

## What Happens When a Provider Fails?

A failure with one provider does not normally stop the entire system.

The tool records the error and continues with other providers.

A provider may fail because:

- Its website design changed
- The page took too long to load
- A security check blocked access
- Plans became available only after entering an address
- The website was temporarily unavailable
- The page content moved to a different location
- The provider changed the wording or structure of its plans

The saved error, screenshots, and health report can help determine what happened.

---

## Important Limitations

### Website information can change

The tool records what was available when a collection was performed. It does not guarantee that the information is still current days or weeks later.

### Collection is not always perfect

Websites are designed for people, not automated collection. Some prices or plan details may be missed or interpreted incorrectly.

Important business decisions should be checked against the provider’s official website.

### Some providers block automated access

Security systems may ask for human verification or block the tool. Aussie Broadband is one known example where live access may be restricted by Cloudflare Turnstile.

### Address-dependent plans may vary

Some providers show different plans depending on the customer’s address, location, or available network technology. The collected list may not represent every address.

### Discounts can be complicated

Promotions may depend on:

- New-customer status
- Direct debit
- Bundling
- Mobile service ownership
- Specific addresses
- Limited application dates
- Special promotional codes

The system records the details it can identify, but users should review the provider’s full conditions.

### Provider names are not perfectly consistent

Some saved information uses different capitalization or slightly different provider labels. For example, a provider may appear once in title case and elsewhere in lowercase.

### Reports may use different saved sources

The combined dashboard, provider files, and comparison reports can sometimes use different saved collections. Users should confirm the date and source before comparing reports.

---

## Is the Information Guaranteed?

No.

The system is a research, monitoring, and business-support tool. It helps reduce manual work, but it should not be treated as the final legal or contractual source of plan information.

Before publishing prices or making major decisions, confirm:

- Current monthly price
- Discount conditions
- Promotion end date
- Contract terms
- Setup and modem charges
- Address availability
- Typical evening speeds
- Cancellation fees
- Provider terms and conditions

The official provider website and official plan documents remain the final source of truth.

---

## Basic Daily or Weekly Use

A simple operating routine could be:

1. Start the application.
2. Open the main dashboard.
3. Run collection for all providers.
4. Review providers that failed or returned unusually few plans.
5. Check the health report and screenshots.
6. Review the combined plan list.
7. Generate the price comparison.
8. Run the alert check.
9. Generate the value report.
10. Test and then update Google Sheets.
11. Manually confirm important price changes on official provider websites.

---

## How to Know Whether the Results Look Correct

Users should look for warning signs such as:

- A major provider returning zero plans
- A provider suddenly returning far fewer plans
- Prices that are unusually high or low
- Missing speeds
- Mobile plans appearing in an NBN report
- Duplicate plans
- Old collection dates
- Screenshots showing an error or security page
- Provider names appearing under several spellings

If something looks unusual, check the source page before relying on the result.

---

## Business Benefits

The project can provide several practical benefits:

- Reduces repetitive website checking
- Creates one central market view
- Speeds up competitor research
- Helps identify pricing opportunities
- Highlights changes between collection dates
- Supports spreadsheet-based reporting
- Keeps evidence through screenshots and source links
- Makes plan information available to other systems
- Helps compare value rather than price alone

---

## Suggested Improvements

The most useful future improvements for business users would be:

1. Show the age of every provider’s data clearly.
2. Display a warning when a provider’s plan count changes sharply.
3. Use one consistent provider name everywhere.
4. Create a scheduled daily or weekly collection.
5. Send email or messaging alerts for important price changes.
6. Add an approval step before new data is published.
7. Create a simple report showing only changes since the previous run.
8. Clearly separate broadband, mobile, business, and satellite services.
9. Record whether a price requires bundling or special eligibility.
10. Provide a simple “data confidence” score for each plan.

---

## Short Summary

This project is an automated Australian internet-plan monitoring and comparison system.

It visits provider websites, collects plan details, stores the information, and makes it available through dashboards, files, reports, APIs, and Google Sheets.

Its main value is saving time and creating a central view of the market. It can also highlight competitor pricing, plan changes, promotional offers, and speed-for-price value.

Because provider websites and offers change frequently, the results should be treated as business intelligence that requires occasional human review—not as a guaranteed replacement for official provider information.

