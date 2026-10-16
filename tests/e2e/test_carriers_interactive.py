from playwright.sync_api import sync_playwright
import json

BASE_URL = "http://127.0.0.1:48481"

def test_carriers_interactive():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        context.grant_permissions(["clipboard-read", "clipboard-write"])
        page = context.new_page()
        
        page.goto(f"{BASE_URL}/carriers", wait_until="networkidle")
        
        # 1. Test #token-modal
        token_btn = page.locator('button[onclick*="openTokenModal"]').first
        token_modal = page.locator('#token-modal')
        results["token_modal_initially_hidden"] = "hidden" in (token_modal.get_attribute("class") or "")
        
        token_btn.click()
        page.wait_for_timeout(300)
        results["token_modal_opened"] = "hidden" not in (token_modal.get_attribute("class") or "")
        
        # Close token modal
        page.locator('#token-modal button:has-text("İmtina")').click()
        page.wait_for_timeout(300)
        results["token_modal_closed"] = "hidden" in (token_modal.get_attribute("class") or "")
        
        # 2. Test #predeclare-modal
        predeclare_btn = page.locator('button:has-text("1-Kliklə Ön Bəyan")')
        predeclare_modal = page.locator('#predeclare-modal')
        results["predeclare_modal_initially_hidden"] = "hidden" in (predeclare_modal.get_attribute("class") or "")
        
        predeclare_btn.click()
        page.wait_for_timeout(300)
        results["predeclare_modal_opened"] = "hidden" not in (predeclare_modal.get_attribute("class") or "")
        
        # Close predeclare modal
        page.locator('#predeclare-modal button:has-text("Bağla")').click()
        page.wait_for_timeout(300)
        results["predeclare_modal_closed"] = "hidden" in (predeclare_modal.get_attribute("class") or "")
        
        # 3. Test copy full address button & Toast
        copy_btn = page.locator('button:has-text("Bütün Ünvanı Kopyala")')
        copy_btn.click()
        page.wait_for_timeout(400)
        toast = page.locator('#toast-container')
        results["toast_triggered"] = toast.locator("div").count() > 0
        if results["toast_triggered"]:
            results["toast_text"] = toast.locator("div").first.inner_text().strip()
            
        # 4. Test platform switcher buttons (Trendyol, Taobao, Temu, Amazon)
        platforms = ["CN · Taobao", "Temu", "US · Amazon", "TR · Trendyol"]
        switcher_results = {}
        for plat in platforms:
            btn = page.locator(f'button:has-text("{plat}")')
            btn.click()
            page.wait_for_timeout(300)
            active_btn_class = btn.get_attribute("class")
            switcher_results[plat] = {"active": "bg-indigo-600" in active_btn_class}
        results["platform_switchers"] = switcher_results
        
        browser.close()
        
    with open("C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/carriers_interactive_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Carriers interactive verification complete.")

if __name__ == "__main__":
    test_carriers_interactive()
