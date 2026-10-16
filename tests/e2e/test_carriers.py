import json
import requests
from bs4 import BeautifulSoup
import sys
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE_URL = "http://127.0.0.1:48481"

def test_carriers_journey():
    results = {}
    r = requests.get(f"{BASE_URL}/carriers")
    results["status"] = r.status_code
    soup = BeautifulSoup(r.text, "html.parser")
    results["title"] = soup.title.string.strip() if soup.title else ""
    
    # Check bookmarklet
    bookmarklet = soup.find("a", href=lambda h: h and "javascript:" in h)
    results["bookmarklet_present"] = bookmarklet is not None
    if bookmarklet:
        results["bookmarklet_text"] = bookmarklet.get_text(strip=True)
        results["bookmarklet_code_len"] = len(bookmarklet["href"])
        results["bookmarklet_snippet"] = bookmarklet["href"][:120]
        
    # Check carriers API address
    addr_resp = requests.get(f"{BASE_URL}/carriers/api/address?carrier=STAREX&country=TR")
    results["address_api_status"] = addr_resp.status_code
    if addr_resp.status_code == 200:
        results["address_api_json"] = addr_resp.json()
        
    # Check modal and interactive controls on /carriers using Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{BASE_URL}/carriers", wait_until="networkidle")
        
        # Test copy buttons
        copy_buttons = page.locator('button[onclick*="copyToClipboard"]')
        results["copy_buttons_count"] = copy_buttons.count()
        if copy_buttons.count() > 0:
            # Grant clipboard permissions
            page.context.grant_permissions(["clipboard-read", "clipboard-write"])
            copy_buttons.first.click()
            page.wait_for_timeout(300)
            toast = page.locator('#toast-container')
            results["toast_visible_after_copy"] = toast.locator("div").count() > 0
            if results["toast_visible_after_copy"]:
                results["toast_message"] = toast.locator("div").first.inner_text().strip()
                
        # Test country origin switcher buttons (TR, CN, US)
        origin_tabs = page.locator('a[href*="country="], button[data-origin]')
        results["origin_tabs_count"] = origin_tabs.count()
        
        page.screenshot(path="C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/carriers_page.png")
        browser.close()
        
    with open("C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/carriers_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Carriers & bookmarklet verification complete.")

if __name__ == "__main__":
    test_carriers_journey()
