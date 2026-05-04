"""Deeper analysis of Telstra plan cards + retry blocked sites with 'load' wait."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.render_engine import create_render_engine
from utils.html_parser import parse_html


def deep_analyze_telstra():
    """Parse saved Telstra HTML and map out plan card structure."""
    html_path = "output/telstra_rendered.html"
    if not os.path.exists(html_path):
        print("[!] Run investigate_sites.py first to generate telstra_rendered.html")
        return
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    parser = parse_html(html)
    if not parser:
        return
    
    print("="*60)
    print("TELSTRA - Deep Plan Card Analysis")
    print("="*60)
    
    # Find plan card containers
    card_selectors = [
        '.planCardHeader',
        '.tcom-fixed-plan-card-price__container',
        'div[class*="planCard"]',
        '.tcom-fixed-plan-card-speed',
        '.tcom-fixed-plan-card-name',
    ]
    
    for sel in card_selectors:
        elements = parser.extract_by_selector(sel)
        if elements:
            print(f"\n--- {sel} ({len(elements)} found) ---")
            for i, el in enumerate(elements[:6]):
                classes = ' '.join(el.get('class', []))
                text = el.get_text(strip=True)[:150]
                print(f"  [{i}] <{el.name} class=\"{classes}\">\n       {text}\n")
    
    # Find all elements with "plan" in class that contain a $ price
    print("\n--- Plan containers with prices ---")
    plan_els = parser.soup.find_all(class_=re.compile(r'planCard(?!Carousel)'))
    seen = set()
    for el in plan_els:
        text = el.get_text(strip=True)
        if '$' in text and 'mth' in text.lower():
            classes = ' '.join(el.get('class', []))
            key = classes
            if key not in seen:
                seen.add(key)
                # Get direct children structure
                children = [f"<{c.name} class=\"{' '.join(c.get('class',[]))}\">" 
                           for c in el.children if hasattr(c, 'name') and c.name]
                print(f"\n  <{el.name} class=\"{classes}\">")
                print(f"    Text: {text[:200]}")
                print(f"    Children: {children[:5]}")


def retry_blocked_sites():
    """Retry Aussie/Superloop with 'load' wait and user-agent."""
    sites = {
        'aussie': [
            'https://www.aussiebroadband.com.au/nbn-plans/',
            'https://www.aussiebroadband.com.au/internet/',
        ],
        'superloop': [
            'https://www.superloop.com/consumer/internet/',
            'https://www.superloop.com/broadband/nbn/',
        ],
    }
    
    with create_render_engine(headless=True) as engine:
        # Set a real user-agent on new pages
        for site_name, urls in sites.items():
            for url in urls:
                print(f"\n{'='*60}")
                print(f"[{site_name.upper()}] Trying with 'load' wait: {url}")
                print(f"{'='*60}")
                
                # Use 'load' instead of 'networkidle' to avoid timeout
                result = engine.render(
                    url=url,
                    wait_condition="load",
                    wait_time=5000,
                    screenshot_path=f"output/{site_name}_screenshot.png"
                )
                
                print(f"  Status: {result.status}")
                print(f"  HTML Length: {len(result.html)}")
                print(f"  Error: {result.error}")
                
                if result.html and len(result.html) > 500:
                    html_path = f"output/{site_name}_rendered.html"
                    with open(html_path, 'w', encoding='utf-8') as f:
                        f.write(result.html)
                    print(f"  Saved HTML to: {html_path}")
                    
                    parser = parse_html(result.html)
                    if parser:
                        title = parser.extract_text('title')
                        print(f"  Title: {title}")
                        
                        # Quick price/plan scan
                        for sel in ['[class*="price"]', '[class*="Price"]', '[class*="plan"]', '[class*="Plan"]',
                                    '[class*="card"]', '[class*="Card"]', '[class*="speed"]', '[class*="Speed"]']:
                            elements = parser.extract_by_selector(sel)
                            if elements:
                                print(f"    {sel}: {len(elements)} elements")
                                for el in elements[:2]:
                                    classes = ' '.join(el.get('class', []))
                                    text = el.get_text(strip=True)[:100]
                                    print(f"      <{el.name} class=\"{classes}\">{text}")
                        
                        # Dollar amounts
                        dollar_els = parser.soup.find_all(string=re.compile(r'\$\d+'))
                        if dollar_els:
                            print(f"\n    [$ amounts found: {len(dollar_els)}]")
                            for el in dollar_els[:5]:
                                p = el.parent
                                if p:
                                    print(f"      <{p.name} class=\"{' '.join(p.get('class',[]) if p.get('class') else [])}\">{str(el).strip()[:80]}")
                    
                    break  # Got data, stop trying URLs
                else:
                    print(f"  [!] Failed or too small")


if __name__ == "__main__":
    deep_analyze_telstra()
    print("\n\n")
    retry_blocked_sites()
