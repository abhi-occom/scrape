"""
Speed/Price ROI Calculator.
Generates an interactive HTML page showing "megabits per dollar" value
across all ISP providers. Lets users filter by provider, speed, and budget.
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.benchmark import (
    load_all_plans,
    get_effective_price,
    get_regular_price,
    calc_value_score,
    calc_annual_cost,
    classify_speed_tier,
    SPEED_TIERS,
)
from utils.logger import log_info, log_success, log_error
from config import OUTPUT_DIR, PROVIDERS


# Provider colors (same as benchmark dashboard)
PROVIDER_COLORS = {
    'occom': '#6C3CE1',
    'telstra': '#0D47A1',
    'optus': '#00897B',
    'superloop': '#E65100',
    'aussie': '#C62828',
    'tpg': '#2E7D32',
}


def compute_roi_data(plans: list = None) -> dict:
    """
    Compute ROI (Mbps/$) data for every plan.
    Returns structured data for the HTML page and API.
    """
    if plans is None:
        plans = load_all_plans()

    if not plans:
        return {'error': 'No plan data available'}

    enriched = []
    for plan in plans:
        speed = plan.get('download_speed') or plan.get('speed') or 0
        eff_price = get_effective_price(plan)
        reg_price = get_regular_price(plan)
        provider = plan.get('provider', '').lower()

        if speed <= 0 or eff_price <= 0:
            continue

        enriched.append({
            'provider': provider,
            'plan_name': plan.get('plan_name', ''),
            'network_type': plan.get('network_type', ''),
            'speed': speed,
            'upload_speed': plan.get('upload_speed') or 0,
            'effective_price': eff_price,
            'regular_price': reg_price,
            'promo_price': plan.get('promo_price'),
            'promo_period': plan.get('promo_period'),
            'contract': plan.get('contract', ''),
            'roi_effective': calc_value_score(speed, eff_price),
            'roi_regular': calc_value_score(speed, reg_price),
            'annual_cost': calc_annual_cost(plan),
            'tier': classify_speed_tier(speed),
        })

    # Sort by ROI descending
    enriched.sort(key=lambda x: x['roi_effective'], reverse=True)

    # Stats
    providers_seen = sorted(set(p['provider'] for p in enriched))
    best_overall = enriched[0] if enriched else None
    best_occom = next((p for p in enriched if p['provider'] == 'occom'), None)
    avg_roi = round(sum(p['roi_effective'] for p in enriched) / len(enriched), 2) if enriched else 0
    max_roi = enriched[0]['roi_effective'] if enriched else 0

    return {
        'generated_at': datetime.now().isoformat(),
        'total_plans': len(enriched),
        'providers': providers_seen,
        'best_overall': best_overall,
        'best_occom': best_occom,
        'avg_roi': avg_roi,
        'max_roi': max_roi,
        'plans': enriched,
    }


def generate_roi_page(plans: list = None, file_path: str = None) -> str:
    """Generate the interactive ROI Calculator HTML page."""
    if file_path is None:
        file_path = os.path.join(OUTPUT_DIR, 'roi_calculator.html')

    data = compute_roi_data(plans)
    if 'error' in data:
        log_error(f"ROI calculator: {data['error']}")
        return None

    summary = data
    enriched = data['plans']
    max_roi = data['max_roi']
    generated_at = data['generated_at']

    def prov_color(name):
        return PROVIDER_COLORS.get(name.lower(), '#757575')

    # --- Table rows ---
    table_rows = ''
    for i, p in enumerate(enriched):
        bar_pct = round(p['roi_effective'] / max_roi * 100, 1) if max_roi > 0 else 0
        promo_cell = ''
        if p.get('promo_price') and p['promo_price'] > 0:
            promo_cell = f"${p['promo_price']:.0f} <small>({p.get('promo_period', '')})</small>"

        is_occom = p['provider'] == 'occom'
        table_rows += f"""
        <tr class="plan-row {'highlight-occom' if is_occom else ''}"
            data-provider="{p['provider']}"
            data-speed="{p['speed']}"
            data-price="{p['effective_price']}"
            data-roi="{p['roi_effective']}"
            data-tier="{p['tier']}">
            <td>{i+1}</td>
            <td><span class="provider-tag" style="background:{prov_color(p['provider'])}">{p['provider'].title()}</span></td>
            <td>{p['plan_name']}</td>
            <td>{p['speed']} <small>Mbps</small></td>
            <td>${p['effective_price']:.0f}<small>/mo</small></td>
            <td>${p['regular_price']:.0f}<small>/mo</small></td>
            <td>{promo_cell}</td>
            <td>
                <div class="roi-cell">
                    <strong>{p['roi_effective']}</strong>
                    <div class="roi-bar-wrap"><div class="roi-bar" style="width:{bar_pct}%;background:{prov_color(p['provider'])}"></div></div>
                </div>
            </td>
            <td>${p['annual_cost']:,.0f}</td>
        </tr>"""

    # --- Provider filter checkboxes ---
    provider_checks = ''
    for prov in data['providers']:
        provider_checks += f"""
        <label class="filter-check">
            <input type="checkbox" value="{prov}" checked onchange="applyFilters()">
            <span class="provider-tag" style="background:{prov_color(prov)}">{prov.title()}</span>
        </label>"""

    # --- Tier filter checkboxes ---
    tiers_in_data = sorted(set(p['tier'] for p in enriched), key=lambda t: SPEED_TIERS.get(t, {}).get('min', 0))
    tier_checks = ''
    for tier in tiers_in_data:
        lbl = SPEED_TIERS.get(tier, {}).get('label', tier.title())
        tier_checks += f"""
        <label class="filter-check">
            <input type="checkbox" value="{tier}" checked onchange="applyFilters()">
            <span class="tier-tag">{lbl}</span>
        </label>"""

    # --- Best per provider cards ---
    best_per_provider = {}
    for p in enriched:
        if p['provider'] not in best_per_provider:
            best_per_provider[p['provider']] = p
    provider_cards = ''
    for prov in data['providers']:
        bp = best_per_provider.get(prov)
        if bp:
            provider_cards += f"""
            <div class="card" style="border-top:4px solid {prov_color(prov)}">
                <div class="card-provider" style="color:{prov_color(prov)}">{prov.title()}</div>
                <div class="big-number">{bp['roi_effective']}<small> Mbps/$</small></div>
                <p class="card-plan">{bp['plan_name']}</p>
                <p class="card-detail">{bp['speed']} Mbps &middot; ${bp['effective_price']:.0f}/mo</p>
            </div>"""

    best_overall = data['best_overall']
    best_occom = data['best_occom']

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Speed/Price ROI Calculator — Occom</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',system-ui,-apple-system,sans-serif;background:#f0f2f5;color:#1a1a2e}}

.top-bar{{
    background:linear-gradient(135deg,#0D8065 0%,#065A46 100%);
    color:white;padding:28px 40px;
}}
.top-bar h1{{font-size:1.8em;font-weight:700}}
.top-bar .sub{{opacity:.85;margin-top:4px;font-size:.95em}}
.top-bar-inner{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:16px;max-width:1400px;margin:0 auto}}
.back-link{{color:white;text-decoration:none;font-size:.9em;opacity:.8;transition:opacity .2s}}
.back-link:hover{{opacity:1}}

.container{{max-width:1400px;margin:0 auto;padding:30px 20px}}

/* Summary */
.summary-strip{{
    display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
    gap:16px;margin-bottom:28px;
}}
.summary-card{{
    background:white;border-radius:12px;padding:22px;text-align:center;
    box-shadow:0 2px 8px rgba(0,0,0,.06);
}}
.summary-card .val{{font-size:2.2em;font-weight:700;color:#0D8065}}
.summary-card .lbl{{font-size:.85em;color:#666;margin-top:4px}}

/* Best per provider */
.cards-grid{{
    display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));
    gap:14px;margin-bottom:28px;
}}
.card{{
    background:white;border-radius:10px;padding:18px;
    box-shadow:0 2px 6px rgba(0,0,0,.06);
}}
.card-provider{{font-weight:700;font-size:.9em;margin-bottom:6px}}
.big-number{{font-size:1.8em;font-weight:700;color:#333}}
.big-number small{{font-size:.4em;color:#888}}
.card-plan{{font-size:.85em;color:#555;margin-top:4px}}
.card-detail{{font-size:.8em;color:#888;margin-top:2px}}

/* Filters */
.filters-panel{{
    background:white;border-radius:12px;padding:22px;margin-bottom:24px;
    box-shadow:0 2px 8px rgba(0,0,0,.06);
}}
.filters-panel h3{{font-size:1em;color:#0D8065;margin-bottom:14px}}
.filter-row{{display:flex;flex-wrap:wrap;gap:20px;align-items:flex-end}}
.filter-group{{display:flex;flex-direction:column;gap:6px}}
.filter-group label.group-label{{font-size:.8em;font-weight:600;color:#555}}
.filter-checks{{display:flex;flex-wrap:wrap;gap:8px}}
.filter-check{{display:inline-flex;align-items:center;gap:4px;cursor:pointer;font-size:.85em}}
.filter-check input{{cursor:pointer}}
.filter-input{{
    padding:8px 12px;border:2px solid #ddd;border-radius:8px;font-size:.9em;width:120px;
}}
.filter-input:focus{{border-color:#0D8065;outline:none}}

/* Table */
.section{{
    background:white;border-radius:14px;padding:28px;margin-bottom:28px;
    box-shadow:0 2px 8px rgba(0,0,0,.06);
}}
.section h2{{
    font-size:1.3em;color:#333;margin-bottom:16px;
    border-bottom:3px solid #0D8065;padding-bottom:8px;display:inline-block;
}}
.table-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:.88em}}
th{{background:#f8f9fa;padding:12px 10px;text-align:left;font-weight:600;color:#555;position:sticky;top:0;cursor:pointer;user-select:none}}
th:hover{{background:#eee}}
td{{padding:10px;border-bottom:1px solid #eee}}
tr:hover{{background:#fafafa}}
.highlight-occom{{background:#f3edff !important}}
.highlight-occom:hover{{background:#ece3ff !important}}

.provider-tag{{
    display:inline-block;padding:3px 10px;border-radius:20px;
    color:white;font-size:.78em;font-weight:600;
}}
.tier-tag{{
    display:inline-block;padding:3px 10px;border-radius:20px;
    background:#e9e9e9;font-size:.78em;font-weight:600;color:#555;
}}

.roi-cell{{display:flex;align-items:center;gap:8px}}
.roi-bar-wrap{{width:80px;height:8px;background:#eee;border-radius:4px;overflow:hidden}}
.roi-bar{{height:100%;border-radius:4px;transition:width .3s}}

.no-results{{text-align:center;padding:40px;color:#888;font-size:1.1em}}
.plan-count{{font-size:.85em;color:#888;margin-bottom:10px}}
.timestamp{{text-align:center;color:#999;font-size:.85em;margin-top:30px}}

@media(max-width:768px){{
    .summary-strip{{grid-template-columns:repeat(2,1fr)}}
    .cards-grid{{grid-template-columns:1fr 1fr}}
    table{{font-size:.78em}}
    .roi-bar-wrap{{width:50px}}
}}
</style>
</head>
<body>

<div class="top-bar">
    <div class="top-bar-inner">
        <div>
            <h1>💰 Speed/Price ROI Calculator</h1>
            <div class="sub">Megabits per dollar — find the best value internet plan across all providers</div>
        </div>
        <a href="/" class="back-link">← Back to Dashboard</a>
    </div>
</div>

<div class="container">

    <!-- Summary -->
    <div class="summary-strip">
        <div class="summary-card">
            <div class="val">{summary['total_plans']}</div>
            <div class="lbl">Plans Ranked</div>
        </div>
        <div class="summary-card">
            <div class="val">{len(summary['providers'])}</div>
            <div class="lbl">Providers</div>
        </div>
        <div class="summary-card">
            <div class="val">{summary['avg_roi']}</div>
            <div class="lbl">Avg Mbps/$</div>
        </div>
        <div class="summary-card">
            <div class="val" style="color:#2E7D32">{best_overall['roi_effective'] if best_overall else 'N/A'}</div>
            <div class="lbl">Best ROI ({best_overall['provider'].title() if best_overall else '-'})</div>
        </div>
        <div class="summary-card">
            <div class="val" style="color:#6C3CE1">{best_occom['roi_effective'] if best_occom else 'N/A'}</div>
            <div class="lbl">Best Occom ROI</div>
        </div>
    </div>

    <!-- Best per provider -->
    <div class="section">
        <h2>Best Value per Provider</h2>
        <div class="cards-grid">{provider_cards}</div>
    </div>

    <!-- Filters -->
    <div class="filters-panel">
        <h3>🔍 Filter & Search</h3>
        <div class="filter-row">
            <div class="filter-group">
                <label class="group-label">Providers</label>
                <div class="filter-checks" id="providerFilters">{provider_checks}</div>
            </div>
            <div class="filter-group">
                <label class="group-label">Speed Tiers</label>
                <div class="filter-checks" id="tierFilters">{tier_checks}</div>
            </div>
            <div class="filter-group">
                <label class="group-label">Max Budget ($/mo)</label>
                <input type="number" class="filter-input" id="maxBudget" placeholder="e.g. 80" oninput="applyFilters()">
            </div>
            <div class="filter-group">
                <label class="group-label">Min Speed (Mbps)</label>
                <input type="number" class="filter-input" id="minSpeed" placeholder="e.g. 100" oninput="applyFilters()">
            </div>
        </div>
    </div>

    <!-- Full table -->
    <div class="section">
        <h2>All Plans Ranked by ROI</h2>
        <div class="plan-count" id="planCount">Showing {len(enriched)} plans</div>
        <div class="table-wrap">
        <table id="roiTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0,'num')">#</th>
                    <th onclick="sortTable(1,'text')">Provider</th>
                    <th onclick="sortTable(2,'text')">Plan</th>
                    <th onclick="sortTable(3,'num')">Speed ↕</th>
                    <th onclick="sortTable(4,'num')">Price ↕</th>
                    <th onclick="sortTable(5,'num')">Regular</th>
                    <th>Promo</th>
                    <th onclick="sortTable(7,'num')">ROI (Mbps/$) ↕</th>
                    <th onclick="sortTable(8,'num')">Annual Cost ↕</th>
                </tr>
            </thead>
            <tbody id="roiBody">{table_rows}</tbody>
        </table>
        </div>
        <div class="no-results" id="noResults" style="display:none">No plans match your filters.</div>
    </div>

    <div class="timestamp">Generated: {generated_at}</div>
</div>

<script>
function applyFilters() {{
    const checkedProviders = new Set(
        [...document.querySelectorAll('#providerFilters input:checked')].map(c => c.value)
    );
    const checkedTiers = new Set(
        [...document.querySelectorAll('#tierFilters input:checked')].map(c => c.value)
    );
    const maxBudget = parseFloat(document.getElementById('maxBudget').value) || Infinity;
    const minSpeed = parseFloat(document.getElementById('minSpeed').value) || 0;

    const rows = document.querySelectorAll('.plan-row');
    let visible = 0;
    let rank = 0;

    rows.forEach(row => {{
        const prov = row.dataset.provider;
        const speed = parseFloat(row.dataset.speed);
        const price = parseFloat(row.dataset.price);
        const tier = row.dataset.tier;

        const show = checkedProviders.has(prov) && checkedTiers.has(tier) && price <= maxBudget && speed >= minSpeed;
        row.style.display = show ? '' : 'none';
        if (show) {{
            visible++;
            rank++;
            row.cells[0].textContent = rank;
        }}
    }});

    document.getElementById('planCount').textContent = 'Showing ' + visible + ' of {len(enriched)} plans';
    document.getElementById('noResults').style.display = visible === 0 ? '' : 'none';
}}

function sortTable(colIdx, type) {{
    const tbody = document.getElementById('roiBody');
    const rows = Array.from(tbody.querySelectorAll('tr'));

    // Toggle direction
    const key = 'sortDir' + colIdx;
    window[key] = window[key] === 'asc' ? 'desc' : 'asc';
    const dir = window[key] === 'asc' ? 1 : -1;

    rows.sort((a, b) => {{
        let va = a.cells[colIdx].textContent.trim();
        let vb = b.cells[colIdx].textContent.trim();
        if (type === 'num') {{
            va = parseFloat(va.replace(/[^\\d.\\-]/g, '')) || 0;
            vb = parseFloat(vb.replace(/[^\\d.\\-]/g, '')) || 0;
            return (va - vb) * dir;
        }}
        return va.localeCompare(vb) * dir;
    }});

    rows.forEach(r => tbody.appendChild(r));
    // Re-number visible rows
    let rank = 0;
    rows.forEach(r => {{
        if (r.style.display !== 'none') {{
            rank++;
            r.cells[0].textContent = rank;
        }}
    }});
}}
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return file_path


def run_and_save_roi(plans: list = None) -> dict:
    """Run ROI calculation and save HTML page. Returns data + file path."""
    log_info("Generating Speed/Price ROI Calculator")

    data = compute_roi_data(plans)
    if 'error' in data:
        log_error(f"ROI calculator: {data['error']}")
        return data

    html_path = generate_roi_page(plans)
    log_success(f"ROI Calculator: {data['total_plans']} plans ranked, "
                f"best ROI = {data['max_roi']} Mbps/$ ({data['best_overall']['provider'].title()})")

    return {
        'data': data,
        'file': html_path,
    }


if __name__ == '__main__':
    result = run_and_save_roi()
    if 'error' not in result:
        d = result['data']
        print(f"\n{'='*60}")
        print(f"  SPEED/PRICE ROI CALCULATOR")
        print(f"{'='*60}")
        print(f"  Plans ranked:      {d['total_plans']}")
        print(f"  Providers:         {', '.join(d['providers'])}")
        print(f"  Avg ROI:           {d['avg_roi']} Mbps/$")
        print(f"  Best overall:      {d['best_overall']['roi_effective']} Mbps/$ "
              f"({d['best_overall']['provider'].title()} - {d['best_overall']['plan_name']})")
        if d['best_occom']:
            print(f"  Best Occom:        {d['best_occom']['roi_effective']} Mbps/$ "
                  f"({d['best_occom']['plan_name']})")
        print(f"  File:              {result['file']}")
        print(f"{'='*60}\n")
    else:
        print(f"Error: {result.get('error')}")
        sys.exit(1)
