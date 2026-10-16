from playwright.sync_api import sync_playwright
import json

BASE_URL = "http://127.0.0.1:48481"

def test_screencast_interactions():
    results = {}
    console_errors = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        page.on("console", lambda msg: console_errors.append(f"[{msg.type}] {msg.text}") if msg.type in ["error", "warning"] else None)
        
        page.goto(f"{BASE_URL}/screencast", wait_until="networkidle")
        
        # 1. Canvas interaction
        canvas = page.locator("#screencastCanvas")
        assert canvas.count() > 0, "Canvas not found"
        box = canvas.bounding_box()
        results["canvas_bounding_box"] = box
        
        # Click on canvas center
        if box:
            center_x = box["x"] + box["width"] / 2
            center_y = box["y"] + box["height"] / 2
            page.mouse.click(center_x, center_y)
            results["canvas_clicked_at"] = {"x": center_x, "y": center_y}
        
        # 2. URL Input interaction
        nav_input = page.locator("#navUrlInput")
        assert nav_input.count() > 0, "URL input not found"
        initial_val = nav_input.input_value()
        results["initial_url_value"] = initial_val
        
        nav_input.fill("https://www.temu.com/test_page.html")
        results["updated_url_value"] = nav_input.input_value()
        
        # 3. Keyboard Input interaction
        key_input = page.locator("#keyboardInput")
        assert key_input.count() > 0, "Keyboard input not found"
        key_input.fill("HelloVerification123")
        results["text_input_value"] = key_input.input_value()
        
        # 4. Slider Assistant (+80px to +280px) interactions
        slider_results = {}
        for px in [80, 120, 160, 200, 240, 280]:
            btn = page.locator(f'button:has-text("+{px}px")')
            assert btn.count() > 0, f"Button +{px}px missing"
            # Click button
            btn.click()
            slider_results[f"+{px}px"] = {"clicked": True, "onclick": btn.get_attribute("onclick")}
        results["slider_assistant"] = slider_results
        
        # 5. Quick platform switcher tabs
        tab_targets = [
            ("Temu", "/connectors/temu/screencast", "https://www.temu.com/bgt_order_list.html"),
            ("Trendyol", "/connectors/trendyol/screencast", "https://www.trendyol.com/giris"),
            ("Taobao", "/connectors/taobao/screencast", "https://login.taobao.com/"),
            ("SmartCustoms", "/connectors/e_customs/screencast", "https://e.customs.gov.az/login"),
        ]
        
        tab_results = {}
        for label, expected_path, expected_target in tab_targets:
            tab = page.locator(f'a:has-text("{label}")[href="{expected_path}"]')
            assert tab.count() > 0, f"Tab {label} missing"
            tab.click()
            page.wait_for_load_state("networkidle")
            current_url = page.url
            current_nav_val = page.locator("#navUrlInput").input_value()
            tab_results[label] = {
                "expected_path": expected_path,
                "current_url": current_url,
                "url_input_value": current_nav_val,
                "url_matches_expected": expected_target in current_nav_val or current_nav_val == expected_target,
                "page_title": page.title()
            }
        results["platform_tabs_navigation"] = tab_results
        results["console_warnings_errors"] = console_errors
        
        browser.close()
        
    with open("C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/screencast_interactive_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("Screencast interactive tests completed successfully.")

if __name__ == "__main__":
    test_screencast_interactions()
