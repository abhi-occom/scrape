"""Test script to verify rendered HTML scraping works."""
import sys
sys.path.insert(0, 'c:/xampp/htdocs/staging/scrape')

from utils.render_engine import create_render_engine
from utils.html_parser import parse_html

def test_render_engine():
    """Test the render engine with a simple page."""
    print("Testing Render Engine...")
    
    # Test with a simple page that should work
    test_url = "https://example.com"
    
    with create_render_engine(headless=True) as engine:
        result = engine.render(test_url, wait_condition="domcontentloaded")
        
        print(f"URL: {result.url}")
        print(f"Status: {result.status}")
        print(f"HTML Length: {len(result.html)}")
        print(f"Error: {result.error}")
        
        if result.html:
            # Parse and extract title
            parser = parse_html(result.html)
            if parser:
                title = parser.extract_text('title')
                print(f"Page Title: {title}")
                
                # Extract all links
                links = parser.get_page_links()
                print(f"Found {len(links)} links")
                
    print("\nRender engine test complete!")

if __name__ == "__main__":
    test_render_engine()
