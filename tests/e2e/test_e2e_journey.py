import json
import time
import os
import requests
from playwright.sync_api import sync_playwright, expect

BASE_URL = "http://127.0.0.1:48481"
REPORT = {}

def test_orders_page(page):
    print("\n--- [TEST 1 & 2] /orders Page & Invoice buttons ---")
    results = {}
    
    # Navigate to /orders
    response = page.goto(f"{BASE_URL}/orders", wait_until="networkidle")
    results["page_load_status"] = response.status
    results["page_url"] = page.url
    
    # 1. Search filter input
    search_input = page.locator('input[name="q"]')
    results["search_input_present"] = search_input.count() > 0
    if results["search_input_present"]:
        results["search_placeholder"] = search_input.get_attribute("placeholder")
    
    # 2. Platform filter options
    platform_select = page.locator('select[name="platform"]')
    results["platform_select_present"] = platform_select.count() > 0
    if results["platform_select_present"]:
        options = platform_select.locator("option").all_inner_texts()
        option_values = [platform_select.locator("option").nth(i).get_attribute("value") for i in range(platform_select.locator("option").count())]
        results["platform_options"] = list(zip(option_values, options))
    
    # 3. Order list rendering
    table = page.locator("table")
    results["table_present"] = table.count() > 0
    
    headers = [th.inner_text().strip() for th in page.locator("table th").all()]
    results["table_headers"] = headers
    
    rows = page.locator("table tbody tr")
    results["order_rows_count"] = rows.count()
    
    orders_sample = []
    for i in range(min(5, rows.count())):
        row = rows.nth(i)
        tds = [td.inner_text().strip().replace("\n", " ") for td in row.locator("td").all()]
        orders_sample.append(tds)
    results["orders_sample"] = orders_sample
    
    # Test Search Interaction
    with page.expect_navigation(wait_until="networkidle"):
        search_input.fill("STAREX")
        page.keyboard.press("Enter")
    
    filtered_rows = page.locator("table tbody tr").count()
    results["search_filter_query"] = "STAREX"
    results["search_filtered_count"] = filtered_rows
    results["search_filtered_url"] = page.url
    
    # Reset search / back to all orders
    page.goto(f"{BASE_URL}/orders", wait_until="networkidle")
    
    # Test Platform Filter Interaction (e.g. Temu)
    with page.expect_navigation(wait_until="networkidle"):
        page.select_option('select[name="platform"]', value="Temu")
    
    temu_rows = page.locator("table tbody tr").count()
    results["platform_filter_temu_count"] = temu_rows
    results["platform_filter_temu_url"] = page.url
    
    # Return to all orders
    page.goto(f"{BASE_URL}/orders", wait_until="networkidle")
    
    # 4. Test Invoice buttons
    invoice_links = page.locator('a[href^="/invoices/"]:not([href$="/pdf"])')
    pdf_links = page.locator('a[href^="/invoices/"][href$="/pdf"]')
    
    results["invoice_html_links_count"] = invoice_links.count()
    results["invoice_pdf_links_count"] = pdf_links.count()
    
    invoice_details = {}
    if invoice_links.count() > 0:
        first_invoice_href = invoice_links.first.get_attribute("href")
        results["first_invoice_href"] = first_invoice_href
        
        # Test HTTP GET for HTML invoice
        inv_resp = requests.get(f"{BASE_URL}{first_invoice_href}")
        invoice_details["html_status"] = inv_resp.status_code
        invoice_details["html_content_type"] = inv_resp.headers.get("content-type")
        invoice_details["html_has_title"] = "İnvoys" in inv_resp.text or "INVOICE" in inv_resp.text or "Faktura" in inv_resp.text
        invoice_details["html_length"] = len(inv_resp.text)
        
        # Visit via Playwright
        page.goto(f"{BASE_URL}{first_invoice_href}", wait_until="networkidle")
        invoice_details["page_title"] = page.title()
        invoice_details["h1_text"] = page.locator("h1").first.inner_text() if page.locator("h1").count() > 0 else "None"
        page.screenshot(path="C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/invoice_html.png")
    
    if pdf_links.count() > 0:
        first_pdf_href = pdf_links.first.get_attribute("href")
        results["first_pdf_href"] = first_pdf_href
        
        # Test HTTP GET for PDF invoice
        pdf_resp = requests.get(f"{BASE_URL}{first_pdf_href}")
        invoice_details["pdf_status"] = pdf_resp.status_code
        invoice_details["pdf_content_type"] = pdf_resp.headers.get("content-type")
        invoice_details["pdf_is_valid_binary"] = pdf_resp.content.startswith(b"%PDF")
        invoice_details["pdf_size_bytes"] = len(pdf_resp.content)
    
    results["invoice_verification"] = invoice_details
    REPORT["orders_and_invoices"] = results
    return results

def test_customs_page(page):
    print("\n--- [TEST 3] /customs Page & Manual Modal & DGK Sync ---")
    results = {}
    
    response = page.goto(f"{BASE_URL}/customs", wait_until="networkidle")
    results["page_load_status"] = response.status
    results["page_url"] = page.url
    
    # 1. Declarations table
    table = page.locator("table")
    results["table_present"] = table.count() > 0
    headers = [th.inner_text().strip() for th in page.locator("table th").all()]
    results["table_headers"] = headers
    
    rows = page.locator("table tbody tr")
    results["declaration_rows_count"] = rows.count()
    decl_sample = []
    for i in range(min(5, rows.count())):
        row = rows.nth(i)
        tds = [td.inner_text().strip().replace("\n", " ") for td in row.locator("td").all()]
        decl_sample.append(tds)
    results["declaration_sample"] = decl_sample
    
    # 2. SmartCustoms DGK sync button
    # Let's find sync button(s)
    sync_buttons = page.locator('button:has-text("Sinxronlaşdır"), button:has-text("Portal İlə Sinxronlaşdır")')
    results["sync_buttons_count"] = sync_buttons.count()
    if sync_buttons.count() > 0:
        results["sync_button_texts"] = [b.inner_text().strip() for b in sync_buttons.all()]
        
        # Test clicking sync button or checking POST /customs/sync endpoint
        # We can check endpoint via requests
        sync_resp = requests.post(f"{BASE_URL}/customs/sync", allow_redirects=False)
        results["sync_endpoint_status"] = sync_resp.status_code
        results["sync_endpoint_location"] = sync_resp.headers.get("location")
    
    # 3. Undeclared order dropdown for manual declarations (#manual-modal)
    # Check button to open modal
    manual_modal_btn = page.locator('button:has-text("Qaralama Bəyannamə Tərtib Et")')
    results["manual_modal_btn_present"] = manual_modal_btn.count() > 0
    
    modal = page.locator('#manual-modal')
    results["modal_present"] = modal.count() > 0
    results["modal_hidden_initially"] = "hidden" in (modal.get_attribute("class") or "")
    
    if manual_modal_btn.count() > 0:
        manual_modal_btn.click()
        page.wait_for_timeout(300)
        results["modal_visible_after_click"] = "hidden" not in (modal.get_attribute("class") or "")
        
        # Check select element
        order_select = page.locator('#modal-order-select')
        results["modal_order_select_present"] = order_select.count() > 0
        if order_select.count() > 0:
            opts = [order_select.locator("option").nth(i).inner_text().strip() for i in range(order_select.locator("option").count())]
            opt_vals = [order_select.locator("option").nth(i).get_attribute("value") for i in range(order_select.locator("option").count())]
            results["modal_order_options"] = list(zip(opt_vals, opts))
        
        # Close modal
        close_btn = modal.locator('button:has-text("Ləğv Et")')
        if close_btn.count() > 0:
            close_btn.click()
            page.wait_for_timeout(300)
            results["modal_hidden_after_close"] = "hidden" in (modal.get_attribute("class") or "")
            
    page.screenshot(path="C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/customs_page.png")
    REPORT["customs"] = results
    return results

def test_connectors_page(page):
    print("\n--- [TEST 4] /connectors Page & Cards & Re-Auth Links ---")
    results = {}
    
    response = page.goto(f"{BASE_URL}/connectors", wait_until="networkidle")
    results["page_load_status"] = response.status
    results["page_url"] = page.url
    
    # Find all connector cards
    # Each card in grid has a platform heading
    cards = page.locator('.grid > div.bg-slate-900\\/90')
    results["cards_count"] = cards.count()
    
    platforms_found = {}
    for i in range(cards.count()):
        c = cards.nth(i)
        title_el = c.locator("h2")
        if title_el.count() == 0:
            continue
        p_name = title_el.inner_text().strip()
        badge_el = c.locator('span.uppercase')
        status = badge_el.inner_text().strip() if badge_el.count() > 0 else "UNKNOWN"
        reauth_link = c.locator('a[href*="/screencast"]')
        reauth_href = reauth_link.get_attribute("href") if reauth_link.count() > 0 else None
        
        platforms_found[p_name] = {
            "status_badge": status,
            "reauth_href": reauth_href,
            "has_reauth_btn": reauth_link.count() > 0
        }
    
    results["platforms_detected"] = platforms_found
    
    # Check specific required platforms: Temu, Trendyol, Taobao, SmartCustoms
    target_platforms = ["Temu", "Trendyol", "Taobao", "SmartCustoms"]
    results["target_platform_checks"] = {}
    for tp in target_platforms:
        matched = {k: v for k, v in platforms_found.items() if tp.lower() in k.lower()}
        results["target_platform_checks"][tp] = matched if matched else "NOT_FOUND_IN_GRID"
        
    page.screenshot(path="C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/connectors_page.png")
    REPORT["connectors"] = results
    return results

def test_screencast_page(page):
    print("\n--- [TEST 5] /screencast Page & Canvas & Slider & Tabs ---")
    results = {}
    
    response = page.goto(f"{BASE_URL}/screencast", wait_until="networkidle")
    results["page_load_status"] = response.status
    results["page_url"] = page.url
    
    # 1. Canvas container
    canvas = page.locator('#screencastCanvas')
    results["canvas_present"] = canvas.count() > 0
    if canvas.count() > 0:
        results["canvas_tag"] = canvas.evaluate("el => el.tagName")
        results["canvas_width"] = canvas.evaluate("el => el.width")
        results["canvas_height"] = canvas.evaluate("el => el.height")
        results["canvas_classes"] = canvas.get_attribute("class")
    
    # 2. URL input
    nav_url = page.locator('#navUrlInput')
    results["url_input_present"] = nav_url.count() > 0
    if nav_url.count() > 0:
        results["url_input_val"] = nav_url.input_value()
    
    # 3. Text input
    key_input = page.locator('#keyboardInput')
    results["text_input_present"] = key_input.count() > 0
    if key_input.count() > 0:
        results["text_input_placeholder"] = key_input.get_attribute("placeholder")
    
    # 4. Slider assistant (+80px to +280px)
    slider_steps = ["+80px", "+120px", "+160px", "+200px", "+240px", "+280px"]
    found_slider_buttons = {}
    for step in slider_steps:
        btn = page.locator(f'button:has-text("{step}")')
        present = btn.count() > 0
        onclick = btn.get_attribute("onclick") if present else None
        found_slider_buttons[step] = {"present": present, "onclick": onclick}
    results["slider_assistant_buttons"] = found_slider_buttons
    
    # 5. Quick platform switcher tabs
    tabs = page.locator('a[href^="/connectors/"][href$="/screencast"]')
    results["platform_tabs_count"] = tabs.count()
    tab_list = []
    for i in range(tabs.count()):
        t = tabs.nth(i)
        tab_list.append({
            "text": t.inner_text().strip(),
            "href": t.get_attribute("href")
        })
    results["platform_tabs"] = tab_list
    
    # Test tab navigation (e.g. click Taobao tab)
    taobao_tab = page.locator('a[href="/connectors/taobao/screencast"]')
    if taobao_tab.count() > 0:
        taobao_tab.click()
        page.wait_for_load_state("networkidle")
        results["tab_click_taobao_url"] = page.url
        results["tab_click_taobao_title"] = page.title()
    
    page.screenshot(path="C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/screencast_page.png")
    REPORT["screencast"] = results
    return results

def run_all_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        
        try:
            test_orders_page(page)
            test_customs_page(page)
            test_connectors_page(page)
            test_screencast_page(page)
        finally:
            browser.close()
            
    with open("C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/e2e_results.json", "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2, ensure_ascii=False)
    print("\nTests complete. Results saved to C:/Users/vasif/.gemini/antigravity/scratch/e2e_tests/e2e_results.json")

if __name__ == "__main__":
    run_all_tests()
