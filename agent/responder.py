"""Turns executor.run_job() results into a plain-English reply with small
HTML tables. All scraped plan data is treated as untrusted external input
and HTML-escaped before being embedded in the reply.
"""
from html import escape
from typing import Any, Dict, List

from config import PROVIDERS


def _display_name(provider_key: str) -> str:
    return escape(str(PROVIDERS.get(provider_key, {}).get('name') or provider_key.title()))


def _plan_table(plans: List[Dict[str, Any]], limit: int = 8) -> str:
    if not plans:
        return '<p><em>No plans found.</em></p>'

    rows = []
    for p in plans[:limit]:
        promo = f"${escape(str(p.get('promo_price')))}" if p.get('promo_price') else '&mdash;'
        rows.append(
            '<tr>'
            f"<td>{escape(str(p.get('plan_name', '?')))}</td>"
            f"<td>{escape(str(p.get('network_type', '?')))}</td>"
            f"<td>{escape(str(p.get('download_speed', '?')))}/{escape(str(p.get('upload_speed', '?')))}</td>"
            f"<td>${escape(str(p.get('price', '?')))}</td>"
            f"<td>{promo}</td>"
            '</tr>'
        )
    more = f'<p><em>...and {len(plans) - limit} more.</em></p>' if len(plans) > limit else ''

    return (
        '<table class="plan-table">'
        '<thead><tr><th>Plan</th><th>Network</th><th>Down/Up (Mbps)</th>'
        '<th>Price</th><th>Promo</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        '</table>'
        f'{more}'
    )


def _tier_comparison_lines(benchmark: Dict[str, Any], requested_providers: List[str]) -> List[str]:
    """Build 'Provider $X vs Occom $Y' lines only for the providers actually
    requested in this job, using the same speed-tier data utils/benchmark.py
    already computes for the main benchmark dashboard."""
    lines: List[str] = []
    if not benchmark or benchmark.get('error'):
        return lines

    for tier in benchmark.get('tier_comparisons', []):
        providers_in_tier = tier.get('providers', {})
        occom = providers_in_tier.get('occom')
        if not occom:
            continue

        for key in requested_providers:
            entry = providers_in_tier.get(key)
            if not entry:
                continue
            diff = round(entry['effective_price'] - occom['effective_price'], 2)
            if diff > 0:
                verdict = f"Occom is ${diff} cheaper"
            elif diff < 0:
                verdict = f"Occom is ${abs(diff)} more expensive"
            else:
                verdict = 'same price'
            lines.append(
                f"<li><strong>{escape(tier['tier_label'])} ({escape(tier['speed_range'])})</strong>: "
                f"{_display_name(key)} ${entry['effective_price']} vs Occom "
                f"${occom['effective_price']} &mdash; {escape(verdict)}</li>"
            )
    return lines


def format_reply(job: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    """Return {'html': str} — a small, already-escaped HTML fragment ready
    to inject into the chat UI."""
    action = job.get('action')

    if action in ('empty', 'unsupported_scrape_all', 'unsupported_history', 'unrecognized'):
        note = ' '.join(job.get('notes') or ['Not sure what you meant.'])
        return {'html': f'<p>{escape(note)}</p>'}

    if result.get('errors') and not result.get('scraped'):
        return {'html': ''.join(f'<p>{escape(e)}</p>' for e in result['errors'])}

    parts: List[str] = []

    for provider_key, scraped in result.get('scraped', {}).items():
        name = _display_name(provider_key)
        if not scraped.get('success'):
            reason = escape(str(scraped.get('error') or 'no plans matched your request'))
            parts.append(f"<p><strong>{name}</strong>: couldn't get plans ({reason}).</p>")
            continue
        plans = scraped['plans']
        fallback_note = ''
        if scraped.get('source') == 'local_llm_fallback':
            fallback_note = (
                ' <em>(via the experimental local-LLM fallback, not the regular scraper — '
                'double check anything important)</em>'
            )
            if scraped.get('possibly_incomplete'):
                fallback_note += (
                    ' <em>This page looks like it mentions more prices than plans '
                    'returned — the local model may have missed some.</em>'
                )
        parts.append(f"<p><strong>{name}</strong>: found {len(plans)} plan(s).{fallback_note}</p>")
        parts.append(_plan_table(plans))

    benchmark = result.get('benchmark')
    if benchmark:
        if benchmark.get('error'):
            parts.append(f"<p>Comparison skipped: {escape(str(benchmark['error']))}</p>")
        else:
            lines = _tier_comparison_lines(benchmark, job.get('providers') or [])
            if lines:
                parts.append('<p>Compared to Occom by speed tier:</p>')
                parts.append(f'<ul>{"".join(lines)}</ul>')
            else:
                parts.append('<p>No overlapping speed tiers found to compare against Occom.</p>')

    for err in result.get('errors', []):
        parts.append(f'<p><em>Note: {escape(err)}</em></p>')

    return {'html': ''.join(parts) or '<p>Done, but nothing came back.</p>'}
