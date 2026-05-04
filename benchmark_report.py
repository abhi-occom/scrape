"""
Benchmark Report Generator.
Runs the competitive benchmark analysis and generates JSON, CSV, and HTML reports.
Can be run standalone or called from main.py pipeline.
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.benchmark import (
    run_benchmark,
    save_benchmark_report,
    save_benchmark_csv,
    load_all_plans,
    SPEED_TIERS,
)
from utils.logger import log_info, log_success, log_error
from config import OUTPUT_DIR


def generate_html_report(report: dict, file_path: str = None) -> str:
    """Generate a standalone HTML dashboard from the benchmark report."""
    if file_path is None:
        file_path = os.path.join(OUTPUT_DIR, 'benchmark_dashboard.html')

    summary = report.get('summary', {})
    tiers = report.get('tier_comparisons', [])
    advantages = report.get('occom_advantages', [])
    gaps = report.get('occom_gaps', [])
    value_rankings = report.get('value_rankings', [])
    generated_at = report.get('generated_at', '')

    # Provider color map
    colors = {
        'occom': '#6C3CE1',
        'telstra': '#0D47A1',
        'optus': '#00897B',
        'superloop': '#E65100',
        'aussie': '#C62828',
        'tpg': '#2E7D32',
    }

    def prov_color(name):
        return colors.get(name.lower(), '#757575')

    # --- Build tier comparison rows ---
    tier_rows = ''
    for tc in tiers:
        providers = tc.get('providers', {})
        # Sort providers so occom is first
        sorted_provs = sorted(providers.keys(), key=lambda x: (0 if x == 'occom' else 1, x))
        for prov in sorted_provs:
            info = providers[prov]
            is_cheapest = tc['cheapest'] == prov
            is_best_val = tc['best_value'] == prov
            badges = ''
            if is_cheapest:
                badges += '<span class="badge badge-green">Cheapest</span> '
            if is_best_val:
                badges += '<span class="badge badge-blue">Best Value</span> '

            promo_cell = ''
            if info.get('promo_price') and info['promo_price'] > 0:
                promo_cell = f"${info['promo_price']:.0f} <small>({info.get('promo_period', '')})</small>"

            tier_rows += f"""
            <tr class="{'highlight-occom' if prov == 'occom' else ''}">
                <td>{tc['tier_label']}</td>
                <td><span class="provider-tag" style="background:{prov_color(prov)}">{prov.title()}</span></td>
                <td>{info['plan_name']}</td>
                <td>{info['speed']} Mbps</td>
                <td><strong>${info['effective_price']:.0f}</strong>/mo</td>
                <td>${info['regular_price']:.0f}/mo</td>
                <td>{promo_cell}</td>
                <td>${info['annual_cost']:,.0f}</td>
                <td>{info['value_score']}</td>
                <td>{badges}</td>
            </tr>"""

    # --- Advantages cards ---
    advantage_cards = ''
    for adv in advantages:
        advantage_cards += f"""
        <div class="card advantage-card">
            <div class="card-header"><strong>{adv['tier_label']}</strong> tier</div>
            <div class="card-body">
                <div class="big-number">${adv['occom_price']:.0f}<small>/mo</small></div>
                <p>{adv['occom_plan']} &middot; {adv['occom_speed']} Mbps</p>
                <div class="savings">
                    Save <strong>${adv.get('savings_vs_next', 0):.0f}/mo</strong>
                    ({adv.get('savings_pct', 0):.0f}%) vs {(adv.get('next_cheapest') or 'N/A').title()}
                </div>
            </div>
        </div>"""

    # --- Gaps cards ---
    gap_cards = ''
    for gap in gaps:
        gap_cards += f"""
        <div class="card gap-card">
            <div class="card-header"><strong>{gap['tier_label']}</strong> tier</div>
            <div class="card-body">
                <div class="big-number">${gap['occom_price']:.0f}<small>/mo</small></div>
                <p>{gap['occom_plan']} &middot; {gap['occom_speed']} Mbps</p>
                <div class="gap-info">
                    Gap: <strong>${gap.get('gap_amount', 0):.0f}/mo</strong>
                    ({gap.get('gap_pct', 0):.0f}%) vs {(gap.get('cheapest_competitor') or 'N/A').title()}
                    @ ${gap.get('cheapest_competitor_price', 0):.0f}/mo
                </div>
            </div>
        </div>"""

    # --- Value ranking rows ---
    value_rows = ''
    for vr in value_rankings:
        for r in vr['rankings']:
            medal = ''
            if r['rank'] == 1:
                medal = '🥇'
            elif r['rank'] == 2:
                medal = '🥈'
            elif r['rank'] == 3:
                medal = '🥉'
            value_rows += f"""
            <tr class="{'highlight-occom' if r['provider'] == 'occom' else ''}">
                <td>{vr['tier_label']}</td>
                <td>{medal} #{r['rank']}</td>
                <td><span class="provider-tag" style="background:{prov_color(r['provider'])}">{r['provider'].title()}</span></td>
                <td><strong>{r['value_score']}</strong> Mbps/$</td>
                <td>{r['speed']} Mbps</td>
                <td>${r['price']:.0f}/mo</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Occom Competitive Benchmark Dashboard</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; background: #f0f2f5; color: #1a1a2e; }}

.top-bar {{
    background: linear-gradient(135deg, #6C3CE1 0%, #4A1DB2 100%);
    color: white; padding: 28px 40px;
}}
.top-bar h1 {{ font-size: 1.8em; font-weight: 700; }}
.top-bar .sub {{ opacity: .85; margin-top: 4px; font-size: .95em; }}

.container {{ max-width: 1400px; margin: 0 auto; padding: 30px 20px; }}

/* Summary strip */
.summary-strip {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; margin-bottom: 30px;
}}
.summary-card {{
    background: white; border-radius: 12px; padding: 22px; text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
}}
.summary-card .val {{ font-size: 2.2em; font-weight: 700; color: #6C3CE1; }}
.summary-card .lbl {{ font-size: .85em; color: #666; margin-top: 4px; }}

/* Sections */
.section {{ background: white; border-radius: 14px; padding: 28px; margin-bottom: 28px; box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
.section h2 {{ font-size: 1.35em; color: #333; margin-bottom: 18px; border-bottom: 3px solid #6C3CE1; padding-bottom: 8px; display: inline-block; }}

/* Cards grid */
.cards-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }}
.card {{ border-radius: 10px; overflow: hidden; box-shadow: 0 2px 6px rgba(0,0,0,.08); }}
.card-header {{ padding: 12px 16px; color: white; font-size: .95em; }}
.card-body {{ padding: 16px; }}
.advantage-card .card-header {{ background: #2E7D32; }}
.gap-card .card-header {{ background: #C62828; }}
.big-number {{ font-size: 2em; font-weight: 700; color: #333; }}
.big-number small {{ font-size: .45em; color: #888; }}
.savings {{ margin-top: 10px; color: #2E7D32; font-size: .9em; }}
.gap-info {{ margin-top: 10px; color: #C62828; font-size: .9em; }}

/* Table */
table {{ width: 100%; border-collapse: collapse; font-size: .9em; }}
th {{ background: #f8f9fa; padding: 12px 10px; text-align: left; font-weight: 600; color: #555; position: sticky; top: 0; }}
td {{ padding: 10px; border-bottom: 1px solid #eee; }}
tr:hover {{ background: #fafafa; }}
.highlight-occom {{ background: #f3edff !important; }}
.highlight-occom:hover {{ background: #ece3ff !important; }}

.provider-tag {{
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    color: white; font-size: .8em; font-weight: 600;
}}
.badge {{
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: .75em; font-weight: 600; color: white;
}}
.badge-green {{ background: #2E7D32; }}
.badge-blue {{ background: #1565C0; }}

.timestamp {{ text-align: center; color: #999; font-size: .85em; margin-top: 30px; }}

/* Tabs */
.tabs {{ display: flex; gap: 4px; margin-bottom: 20px; }}
.tab-btn {{
    padding: 10px 22px; border: none; background: #e9e9e9; border-radius: 8px 8px 0 0;
    cursor: pointer; font-size: .95em; font-weight: 600; color: #555;
}}
.tab-btn.active {{ background: white; color: #6C3CE1; box-shadow: 0 -2px 6px rgba(0,0,0,.06); }}
.tab-content {{ display: none; }}
.tab-content.active {{ display: block; }}

@media(max-width: 768px) {{
    .summary-strip {{ grid-template-columns: repeat(2, 1fr); }}
    .cards-grid {{ grid-template-columns: 1fr; }}
    table {{ font-size: .8em; }}
}}
</style>
</head>
<body>

<div class="top-bar">
    <h1>Occom Competitive Benchmark</h1>
    <div class="sub">Real-time price &amp; value comparison against Australian ISP competitors</div>
</div>

<div class="container">

    <!-- Summary Strip -->
    <div class="summary-strip">
        <div class="summary-card">
            <div class="val">{summary.get('total_plans_analyzed', 0)}</div>
            <div class="lbl">Plans Analysed</div>
        </div>
        <div class="summary-card">
            <div class="val">{summary.get('total_providers', 0)}</div>
            <div class="lbl">Providers Compared</div>
        </div>
        <div class="summary-card">
            <div class="val">{summary.get('total_speed_tiers', 0)}</div>
            <div class="lbl">Speed Tiers</div>
        </div>
        <div class="summary-card">
            <div class="val" style="color:#2E7D32">{summary.get('occom_cheapest_tiers', 0)}</div>
            <div class="lbl">Tiers Occom Wins</div>
        </div>
        <div class="summary-card">
            <div class="val" style="color:#C62828">{summary.get('occom_gap_tiers', 0)}</div>
            <div class="lbl">Tiers with Gaps</div>
        </div>
        <div class="summary-card">
            <div class="val">{summary.get('occom_win_rate', 0)}%</div>
            <div class="lbl">Occom Win Rate</div>
        </div>
    </div>

    <!-- Tabs -->
    <div class="tabs">
        <button class="tab-btn active" onclick="switchTab('overview')">Overview</button>
        <button class="tab-btn" onclick="switchTab('comparison')">Full Comparison</button>
        <button class="tab-btn" onclick="switchTab('value')">Value Rankings</button>
    </div>

    <!-- Tab: Overview -->
    <div id="tab-overview" class="tab-content active">
        <div class="section">
            <h2>Occom Wins &mdash; Cheapest in Tier</h2>
            <div class="cards-grid">
                {advantage_cards if advantage_cards else '<p style="color:#888">No advantages found in current data.</p>'}
            </div>
        </div>

        <div class="section">
            <h2>Pricing Gaps &mdash; Competitors Cheaper</h2>
            <div class="cards-grid">
                {gap_cards if gap_cards else '<p style="color:#888">No pricing gaps &mdash; Occom leads everywhere!</p>'}
            </div>
        </div>
    </div>

    <!-- Tab: Full Comparison -->
    <div id="tab-comparison" class="tab-content">
        <div class="section">
            <h2>Tier-by-Tier Price Comparison</h2>
            <div style="overflow-x:auto">
            <table>
                <thead>
                    <tr>
                        <th>Tier</th><th>Provider</th><th>Plan</th><th>Speed</th>
                        <th>Price</th><th>Regular</th><th>Promo</th>
                        <th>Annual Cost</th><th>Value (Mbps/$)</th><th>Status</th>
                    </tr>
                </thead>
                <tbody>{tier_rows}</tbody>
            </table>
            </div>
        </div>
    </div>

    <!-- Tab: Value Rankings -->
    <div id="tab-value" class="tab-content">
        <div class="section">
            <h2>Value Score Rankings (Mbps per Dollar)</h2>
            <div style="overflow-x:auto">
            <table>
                <thead>
                    <tr>
                        <th>Tier</th><th>Rank</th><th>Provider</th>
                        <th>Value Score</th><th>Speed</th><th>Price</th>
                    </tr>
                </thead>
                <tbody>{value_rows}</tbody>
            </table>
            </div>
        </div>
    </div>

    <div class="timestamp">Report generated: {generated_at}</div>
</div>

<script>
function switchTab(name) {{
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    event.target.classList.add('active');
}}
</script>
</body>
</html>"""

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(html)

    return file_path


def run_and_save_benchmark(plans: list = None) -> dict:
    """
    Run benchmark and save all report formats.
    Returns the report dict and file paths.
    """
    log_info("Starting competitive benchmark analysis")

    if plans is None:
        plans = load_all_plans()

    if not plans:
        log_error("No plan data found for benchmarking")
        return {'error': 'No plan data'}

    report = run_benchmark(plans)

    if 'error' in report:
        log_error(f"Benchmark failed: {report['error']}")
        return report

    # Save all formats
    json_path = save_benchmark_report(report)
    csv_path = save_benchmark_csv(report)
    html_path = generate_html_report(report)

    log_success(
        f"Benchmark complete: {report['summary']['occom_cheapest_tiers']} wins, "
        f"{report['summary']['occom_gap_tiers']} gaps across "
        f"{report['summary']['total_speed_tiers']} tiers"
    )

    return {
        'report': report,
        'files': {
            'json': json_path,
            'csv': csv_path,
            'html': html_path,
        }
    }


if __name__ == '__main__':
    result = run_and_save_benchmark()
    if 'error' not in result:
        summary = result['report']['summary']
        print(f"\n{'='*60}")
        print(f"  OCCOM COMPETITIVE BENCHMARK REPORT")
        print(f"{'='*60}")
        print(f"  Plans analysed:    {summary['total_plans_analyzed']}")
        print(f"  Providers:         {', '.join(summary['providers'])}")
        print(f"  Speed tiers:       {summary['total_speed_tiers']}")
        print(f"  Occom wins:        {summary['occom_cheapest_tiers']} tiers")
        print(f"  Occom gaps:        {summary['occom_gap_tiers']} tiers")
        print(f"  Win rate:          {summary['occom_win_rate']}%")
        print(f"{'='*60}")
        print(f"  Files saved:")
        for fmt, path in result['files'].items():
            print(f"    {fmt.upper()}: {path}")
        print(f"{'='*60}\n")
    else:
        print(f"Error: {result.get('error')}")
        sys.exit(1)
