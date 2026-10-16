"""Playwright End-to-End Test Suite for KargoPilot v4.0 Central Management Panel:
Section 2 'Ağıllı Xarici Anbar və Filial Ünvan Formatlayıcısı' & 1-Click Clipboard Engine.
Includes:
- Section 2 DOM & Structural Validation
- Carrier Select Dropdown Simulation (#addr-carrier: STAREX, CAMEX, DYNAMEX, LIMAK)
- Branch Select Dropdown Simulation (#addr-branch: 28 May, Gənclik, Əhmədli, Xalqlar, Yasamal, Sumqayıt)
- Platform Toggle Buttons Simulation (#btn-plat-trendyol, #btn-plat-taobao, #btn-plat-temu, #btn-plat-amazon)
- Address Fields Breakdown (#address-fields-container with individual copy buttons)
- Full Address Block (#addr-full-block) & 'Bütün Ünvanı Kopyala' (#btn-copy-all)
- Error Boundary & Graceful Degradation Test (Invalid carrier error state)
- Bookmarklet Engine Validation (#kp-bookmarklet-link & DOM injection script)
- Section 1 Integration ("📍 Ünvanı Al" sync to Section 2)
- Fast-Cycle Concurrency / Determinism Test
"""

import asyncio
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright, expect, Page, BrowserContext

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class StepResult:
    step_id: str
    description: str
    status: str  # PASS / FAIL / WARN
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class AddressFormatterE2ETester:
    def __init__(self, base_url: str = "http://127.0.0.1:48481", output_dir: str = "C:/Users/vasif/.gemini/antigravity/scratch/test_results"):
        self.base_url = base_url
        self.output_dir = output_dir
        self.results: List[StepResult] = []
        os.makedirs(output_dir, exist_ok=True)

    def record(self, step_id: str, description: str, status: str, duration_ms: float, details: Dict[str, Any] = None, error: str = None):
        res = StepResult(
            step_id=step_id,
            description=description,
            status=status,
            duration_ms=round(duration_ms, 2),
            details=details or {},
            error=error
        )
        self.results.append(res)
        tag = "[PASS]" if status == "PASS" else ("[WARN]" if status == "WARN" else "[FAIL]")
        try:
            print(f"{tag} {step_id}: {description} ({duration_ms:.1f}ms)")
            if error:
                print(f"    Error: {error}")
        except Exception:
            print(f"[{status}] {step_id}: ({duration_ms:.1f}ms)")

    async def run_all(self):
        print(f"=== Starting KargoPilot E2E Test Battery on {self.base_url}/carriers ===")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--enable-features=ClipboardPasteContentAnalysis"
                ]
            )
            context = await browser.new_context(
                viewport={"width": 1440, "height": 900},
                permissions=["clipboard-read", "clipboard-write"]
            )
            page = await context.new_page()

            console_logs = []
            page_errors = []
            page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))

            try:
                # 1. Navigation & Section 2 Structural Validation
                await self.test_section_2_structure(page)

                # 2. Carrier Select Dropdown Simulation (#addr-carrier)
                await self.test_carrier_select_dropdown(page)

                # 3. Branch Select Dropdown Simulation (#addr-branch)
                await self.test_branch_select_dropdown(page)

                # 4. Platform Toggle Buttons Simulation
                await self.test_platform_toggle_buttons(page)

                # 5. Field Verification in #address-fields-container & Individual Copy Buttons
                await self.test_address_fields_and_copy_buttons(page)

                # 6. Full Address Block (#addr-full-block) & 'Bütün Ünvanı Kopyala' (#btn-copy-all)
                await self.test_full_block_and_copy_all(page)

                # 7. Error Boundary & Graceful Degradation Test
                await self.test_error_boundary_degradation(page)

                # 8. Section 2.5 Bookmarklet Engine & Autofill Dispatch
                await self.test_bookmarklet_engine(page)

                # 9. Integration: Section 1 '📍 Ünvanı Al' buttons sync to Section 2
                await self.test_section_1_address_selection_integration(page)

                # 10. Determinism / Race-Condition Stress Test
                await self.test_rapid_toggle_determinism(page)

                # Screenshot final state
                screenshot_path = os.path.join(self.output_dir, "carriers_section2_e2e.png")
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"Full-page screenshot saved to {screenshot_path}")

            finally:
                await context.close()
                await browser.close()

        # Save JSON results
        report_json_path = os.path.join(self.output_dir, "e2e_results.json")
        with open(report_json_path, "w", encoding="utf-8") as f:
            json.dump({
                "base_url": self.base_url,
                "timestamp": time.time(),
                "console_logs_count": len(console_logs),
                "page_errors": page_errors,
                "steps": [asdict(r) for r in self.results]
            }, f, indent=2, ensure_ascii=False)
        print(f"JSON test results written to {report_json_path}")

    async def test_section_2_structure(self, page: Page):
        t0 = time.perf_counter()
        step_id = "TASK-1.1"
        try:
            resp = await page.goto(f"{self.base_url}/carriers", wait_until="domcontentloaded", timeout=15000)
            assert resp.status == 200, f"Unexpected HTTP status {resp.status}"

            sec = page.locator("#address-engine-section")
            await expect(sec).to_be_visible(timeout=5000)

            # Check heading
            heading = sec.locator("h2")
            heading_text = await heading.inner_text()
            assert "Ağıllı Xarici Anbar və Filial Ünvan Formatlayıcısı" in heading_text, f"Heading text mismatch: {heading_text}"

            # Check 1-Click Clipboard badge
            badge_loc = sec.locator("text='1-Click Clipboard'")
            await expect(badge_loc).to_be_visible()

            # Check control elements exist
            carrier_select = page.locator("#addr-carrier")
            await expect(carrier_select).to_be_visible()

            branch_select = page.locator("#addr-branch")
            await expect(branch_select).to_be_visible()

            for btn_id in ["btn-plat-trendyol", "btn-plat-taobao", "btn-plat-temu", "btn-plat-amazon"]:
                await expect(page.locator(f"#{btn_id}")).to_be_visible()

            # Check containers
            await expect(page.locator("#address-fields-container")).to_be_visible()
            await expect(page.locator("#addr-summary-tag")).to_be_visible()
            await expect(page.locator("#addr-full-block")).to_be_visible()
            await expect(page.locator("#btn-copy-all")).to_be_visible()

            # Wait for fields to finish initial load
            await page.wait_for_selector("#address-fields-container button:has-text('Kopyala')", timeout=5000)

            self.record(step_id, "Section 2 DOM structure & initial rendering validated", "PASS", (time.perf_counter() - t0) * 1000, {
                "heading": heading_text,
                "controls": ["#addr-carrier", "#addr-branch", "#btn-plat-*", "#address-fields-container", "#addr-full-block", "#btn-copy-all"]
            })
        except Exception as e:
            self.record(step_id, "Section 2 DOM structure validation failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))
            raise

    async def test_carrier_select_dropdown(self, page: Page):
        carriers = [
            {"carrier": "STAREX", "expected_district": "Avcılar"},
            {"carrier": "CAMEX", "expected_district": "Güngören"},
            {"carrier": "DYNAMEX", "expected_district": "Başakşehir"},
            {"carrier": "LIMAK", "expected_district": "Küçükçekmece"},
        ]

        carrier_select = page.locator("#addr-carrier")
        options = await carrier_select.locator("option").all_inner_texts()
        print(f"Available carrier dropdown options: {options}")

        for item in carriers:
            t0 = time.perf_counter()
            carrier = item["carrier"]
            step_id = f"TASK-2.{carrier}"
            try:
                # Select carrier via value
                await carrier_select.select_option(carrier)

                # Deterministically wait for summary tag to update
                summary_loc = page.locator("#addr-summary-tag")
                await expect(summary_loc).to_contain_text(carrier, timeout=3000)

                # Deterministically wait for async address fetch to complete by asserting district in full block
                full_block_loc = page.locator("#addr-full-block")
                await expect(full_block_loc).to_contain_text(item["expected_district"], timeout=5000)

                # Wait for address-fields-container to contain Kopyala buttons
                await page.wait_for_selector("#address-fields-container button:has-text('Kopyala')", timeout=3000)

                full_text = await full_block_loc.inner_text()
                summary_text = await summary_loc.inner_text()

                self.record(step_id, f"Carrier select change to {carrier} triggered loadFormattedAddress() successfully", "PASS", (time.perf_counter() - t0) * 1000, {
                    "carrier": carrier,
                    "summary_tag": summary_text,
                    "full_block_district": [l for l in full_text.splitlines() if item["expected_district"] in l]
                })
            except Exception as e:
                self.record(step_id, f"Carrier select change to {carrier} failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_branch_select_dropdown(self, page: Page):
        branches = ['28 May', 'Gənclik', 'Əhmədli', 'Xalqlar', 'Yasamal', 'Sumqayıt']
        branch_select = page.locator("#addr-branch")

        # Set carrier to STAREX first
        await page.locator("#addr-carrier").select_option("STAREX")

        for branch in branches:
            t0 = time.perf_counter()
            step_id = f"TASK-3.{branch.replace(' ', '_')}"
            try:
                await branch_select.select_option(branch)

                # Deterministic wait for summary tag to contain branch
                summary_loc = page.locator("#addr-summary-tag")
                await expect(summary_loc).to_contain_text(branch, timeout=3000)

                # Deterministic wait for async fetch to update full block
                full_block_loc = page.locator("#addr-full-block")
                await expect(full_block_loc).to_contain_text(f"Təhvil Filialı: {branch}", timeout=5000)

                full_text = await full_block_loc.inner_text()
                summary_text = await summary_loc.inner_text()

                self.record(step_id, f"Branch change to '{branch}' loaded and verified in DOM", "PASS", (time.perf_counter() - t0) * 1000, {
                    "branch": branch,
                    "summary_tag": summary_text,
                    "matched_line": [l for l in full_text.splitlines() if branch in l]
                })
            except Exception as e:
                self.record(step_id, f"Branch change to '{branch}' failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_platform_toggle_buttons(self, page: Page):
        platforms = [
            {
                "id": "btn-plat-trendyol",
                "platform": "trendyol",
                "country": "TR",
                "carrier": "STAREX",
                "expected_field": "İlçe (District)",
                "expected_summary_cntry": "TR"
            },
            {
                "id": "btn-plat-taobao",
                "platform": "taobao",
                "country": "CN",
                "carrier": "STAREX",
                "expected_field": "收货人 (Recipient)",
                "expected_summary_cntry": "CN"
            },
            {
                "id": "btn-plat-temu",
                "platform": "temu",
                "country": "CN",
                "carrier": "CAMEX",
                "expected_field": "收货人 (Recipient)",
                "expected_summary_cntry": "CN"
            },
            {
                "id": "btn-plat-amazon",
                "platform": "amazon",
                "country": "US",
                "carrier": "STAREX",
                "expected_field": "Address Line 1",
                "expected_summary_cntry": "US"
            },
        ]

        for p_info in platforms:
            t0 = time.perf_counter()
            btn_id = p_info["id"]
            step_id = f"TASK-4.{p_info['platform'].upper()}"
            try:
                # Set carrier that supports country
                await page.locator("#addr-carrier").select_option(p_info["carrier"])

                btn = page.locator(f"#{btn_id}")
                await btn.click()

                # In v4.0, active styling has bg-indigo-600
                btn_class = await btn.get_attribute("class")
                assert "bg-indigo-600" in btn_class, f"Active styling (bg-indigo-600) missing on {btn_id}: {btn_class}"

                # Inactive buttons do not have bg-indigo-600
                for other in ["btn-plat-trendyol", "btn-plat-taobao", "btn-plat-temu", "btn-plat-amazon"]:
                    if other != btn_id:
                        other_class = await page.locator(f"#{other}").get_attribute("class")
                        assert "bg-indigo-600" not in other_class, f"Inactive button {other} should not have bg-indigo-600: {other_class}"

                # Verify summary tag reflects country
                summary_loc = page.locator("#addr-summary-tag")
                await expect(summary_loc).to_contain_text(p_info["expected_summary_cntry"], timeout=3000)

                # Verify fields container contains platform-specific field
                fields_container = page.locator("#address-fields-container")
                await expect(fields_container).to_contain_text(p_info["expected_field"], timeout=5000)

                summary_text = await summary_loc.inner_text()
                full_block_text = await page.locator("#addr-full-block").inner_text()

                self.record(step_id, f"Platform toggle to {p_info['platform']} ({p_info['country']}) verified styling and address reload", "PASS", (time.perf_counter() - t0) * 1000, {
                    "platform": p_info["platform"],
                    "active_class": btn_class,
                    "summary_tag": summary_text,
                    "full_block_preview": full_block_text[:100]
                })
            except Exception as e:
                self.record(step_id, f"Platform toggle to {p_info['platform']} failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_address_fields_and_copy_buttons(self, page: Page):
        # Reset to Trendyol TR with STAREX and 28 May
        await page.locator("#btn-plat-trendyol").click()
        await page.locator("#addr-carrier").select_option("STAREX")
        await page.locator("#addr-branch").select_option("28 May")

        t0 = time.perf_counter()
        step_id = "TASK-5.FIELDS_RENDER"
        try:
            # Deterministic wait: wait for TR summary, Avcılar in full block, and Ad (First Name) field
            await expect(page.locator("#addr-summary-tag")).to_contain_text("TR", timeout=5000)
            await expect(page.locator("#addr-full-block")).to_contain_text("Avcılar", timeout=5000)
            await expect(page.locator("#address-fields-container")).to_contain_text("Ad (First Name)", timeout=5000)
            await page.wait_for_selector("#address-fields-container button:has-text('Kopyala')", timeout=5000)

            expected_labels = [
                "Ad (First Name)",
                "Soyad (Last Name)",
                "İl (City)",
                "İlçe (District)",
                "Mahalle (Quarter)",
                "Açıq Ünvan (Address)",
                "Posta Kodu (ZIP)",
                "Telefon (Phone)",
                "TC / Vergi No"
            ]

            cards = await page.locator("#address-fields-container .bg-slate-950").all()
            assert len(cards) >= 9, f"Expected at least 9 field cards, found {len(cards)}"

            extracted_fields = []
            for card in cards:
                # Use resilient element-specific locators (div.text-slate-400 avoids collision with button text-[11px])
                label_el = card.locator("div.text-slate-400")
                value_el = card.locator(".select-all")
                copy_btn = card.get_by_role("button", name="Kopyala")

                label_text = await label_el.inner_text()
                val_text = await value_el.inner_text()
                btn_text = await copy_btn.inner_text()

                extracted_fields.append({
                    "label": label_text,
                    "value": val_text,
                    "btn_text": btn_text
                })

            current_labels = [f["label"] for f in extracted_fields]
            for exp in expected_labels:
                assert any(exp in cur for cur in current_labels), f"Missing expected field: {exp} among {current_labels}"

            self.record(step_id, f"Verified all {len(extracted_fields)} address fields with copy buttons rendered in #address-fields-container", "PASS", (time.perf_counter() - t0) * 1000, {
                "field_count": len(extracted_fields),
                "labels": [f["label"] for f in extracted_fields]
            })
        except Exception as e:
            self.record(step_id, "Address fields structure verification failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))
            raise

        # Test clicking individual copy buttons and clipboard behavior
        t0 = time.perf_counter()
        copy_step = "TASK-5.COPY_INDIVIDUAL"
        try:
            cards = await page.locator("#address-fields-container .bg-slate-950").all()
            tested_copies = []

            for idx in [0, 1, 5]:
                card = cards[idx]
                label_text = await card.locator("div.text-slate-400").inner_text()
                val_text = await card.locator(".select-all").inner_text()
                copy_btn = card.get_by_role("button", name="Kopyala")

                # Click copy button
                await copy_btn.click()

                # Verify toast notification in #toast-container
                toast_loc = page.locator("#toast-container div")
                await expect(toast_loc.first).to_be_visible(timeout=3000)
                toast_text = await toast_loc.first.inner_text()
                assert "kopyalandı" in toast_text.lower(), f"Toast text does not contain 'kopyalandı': {toast_text}"

                # Read clipboard text from browser context
                clipboard_content = await page.evaluate("navigator.clipboard.readText()")
                assert clipboard_content == val_text, f"Clipboard mismatch! Expected '{val_text}', got '{clipboard_content}'"

                tested_copies.append({
                    "label": label_text,
                    "value": val_text,
                    "clipboard": clipboard_content,
                    "toast": toast_text
                })
                await page.wait_for_timeout(300)

            self.record(copy_step, "Individual copy buttons successfully trigger toast and copy exact field values to clipboard", "PASS", (time.perf_counter() - t0) * 1000, {
                "tested_copies": tested_copies
            })
        except Exception as e:
            self.record(copy_step, "Individual field copy test failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_full_block_and_copy_all(self, page: Page):
        t0 = time.perf_counter()
        step_id = "TASK-6.COPY_ALL"
        try:
            # Deterministic wait: ensure full block is visible and populated with STAREX / 28 May
            full_block_el = page.locator("#addr-full-block")
            await expect(full_block_el).to_be_visible()
            await expect(full_block_el).to_contain_text("Ad Soyad:", timeout=5000)
            await expect(full_block_el).to_contain_text("Təhvil Filialı:", timeout=5000)

            full_block_content = await full_block_el.inner_text()
            assert len(full_block_content.strip()) > 30, f"Full block content too short: '{full_block_content}'"

            # Check button #btn-copy-all
            copy_all_btn = page.locator("#btn-copy-all")
            await expect(copy_all_btn).to_be_visible()
            btn_text = await copy_all_btn.inner_text()
            assert "Bütün Ünvanı Kopyala" in btn_text, f"Button text mismatch: {btn_text}"

            # Click copy all button
            await copy_all_btn.click()

            # Verify toast in #toast-container (deterministic text filter)
            toast_loc = page.locator("#toast-container div").filter(has_text="Tam ünvan bloku kopyalandı")
            await expect(toast_loc.first).to_be_visible(timeout=3000)
            toast_text = await toast_loc.first.inner_text()

            # Verify clipboard (normalize CRLF to LF for cross-platform robustness)
            clipboard_content = await page.evaluate("navigator.clipboard.readText()")
            norm_clip = clipboard_content.replace("\r\n", "\n").strip()
            norm_block = full_block_content.replace("\r\n", "\n").strip()
            assert norm_clip == norm_block, (
                f"Clipboard does not match full block!\nClipboard: {repr(norm_clip)}\nBlock: {repr(norm_block)}"
            )

            self.record(step_id, "#addr-full-block validated & #btn-copy-all successfully copied complete multi-line address block", "PASS", (time.perf_counter() - t0) * 1000, {
                "button_text": btn_text,
                "toast_text": toast_text,
                "lines_count": len(full_block_content.splitlines()),
                "full_block_preview": full_block_content[:150]
            })
        except Exception as e:
            self.record(step_id, "#addr-full-block or #btn-copy-all verification failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_error_boundary_degradation(self, page: Page):
        t0 = time.perf_counter()
        step_id = "TASK-7.ERROR_BOUNDARY"
        try:
            # Trigger error boundary by requesting non-existent carrier via page script
            await page.evaluate("""() => {
                const sel = document.getElementById('addr-carrier');
                const opt = document.createElement('option');
                opt.value = 'NONEXISTENT_CARRIER';
                opt.innerText = 'NONEXISTENT_CARRIER';
                sel.appendChild(opt);
                sel.value = 'NONEXISTENT_CARRIER';
                loadFormattedAddress();
            }""")

            fields_container = page.locator("#address-fields-container")
            await expect(fields_container).to_contain_text("xəta baş verdi", timeout=3000)
            err_text = await fields_container.inner_text()

            # Clean up the test option and restore STAREX
            await page.evaluate("""() => {
                const sel = document.getElementById('addr-carrier');
                const opt = sel.querySelector('option[value="NONEXISTENT_CARRIER"]');
                if (opt) opt.remove();
                sel.value = 'STAREX';
                loadFormattedAddress();
            }""")
            await expect(page.locator("#addr-summary-tag")).to_contain_text("STAREX", timeout=3000)
            await expect(page.locator("#addr-full-block")).to_contain_text("Avcılar", timeout=5000)

            self.record(step_id, "Graceful error message rendered upon API 400 failure without page crash", "PASS", (time.perf_counter() - t0) * 1000, {
                "rendered_error": err_text
            })
        except Exception as e:
            self.record(step_id, "Error boundary degradation test failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_bookmarklet_engine(self, page: Page):
        t0 = time.perf_counter()
        step_id = "TASK-8.BOOKMARKLET"
        try:
            bm_sec = page.locator("#bookmarklet-section")
            await expect(bm_sec).to_be_visible(timeout=3000)

            # Check bookmarklet anchor link
            bm_link = page.locator("#kp-bookmarklet-link")
            await expect(bm_link).to_be_visible()
            href_val = await bm_link.get_attribute("href")
            assert href_val.startswith("javascript:"), f"Bookmarklet link is not a javascript URI: {href_val[:50]}"
            assert "/carriers/api/address" in href_val, f"Bookmarklet does not target address API: {href_val[:80]}"

            # Check copy snippet button
            copy_bm_btn = bm_sec.get_by_role("button", name="Autofill Skriptini Kopyala")
            await expect(copy_bm_btn).to_be_visible()
            await copy_bm_btn.click()

            # Verify toast (deterministic text filter)
            toast_loc = page.locator("#toast-container div").filter(has_text="1-Klik Autofill Bookmarklet kopyalandı")
            await expect(toast_loc.first).to_be_visible(timeout=3000)
            toast_text = await toast_loc.first.inner_text()

            # Check clipboard contains javascript
            clipboard_content = await page.evaluate("navigator.clipboard.readText()")
            assert clipboard_content.startswith("javascript:(function()"), f"Clipboard does not contain bookmarklet JS: {clipboard_content[:50]}"

            self.record(step_id, "Zero-Friction 1-Click Autofill Bookmarklet link & script copy verified", "PASS", (time.perf_counter() - t0) * 1000, {
                "bookmarklet_href_preview": href_val[:70],
                "copied_snippet_len": len(clipboard_content),
                "toast_text": toast_text
            })
        except Exception as e:
            self.record(step_id, "Bookmarklet engine verification failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_section_1_address_selection_integration(self, page: Page):
        t0 = time.perf_counter()
        step_id = "TASK-9.SECTION1_INTEGRATION"
        try:
            # Find all 'Ünvanı Al' buttons in Section 1 (#carrier-cards)
            unvani_al_btns = await page.locator("#carrier-cards button:has-text('Ünvanı Al')").all()
            assert len(unvani_al_btns) >= 4, f"Expected at least 4 'Ünvanı Al' buttons in Section 1, got {len(unvani_al_btns)}"

            # Target the CAMEX card using resilient filter
            camex_card = page.locator("#carrier-cards > div").filter(has_text="CAMEX")
            camex_btn = camex_card.get_by_role("button", name="Ünvanı Al")
            await camex_btn.click()

            # Verify Section 2 #addr-carrier is now 'CAMEX'
            await expect(page.locator("#addr-carrier")).to_have_value("CAMEX", timeout=3000)

            # Verify summary tag reflects CAMEX
            await expect(page.locator("#addr-summary-tag")).to_contain_text("CAMEX", timeout=3000)

            # Deterministic wait for async fetch: verify full block contains CAMEX address details (Güngören)
            full_block_loc = page.locator("#addr-full-block")
            await expect(full_block_loc).to_contain_text("Güngören", timeout=5000)

            full_text = await full_block_loc.inner_text()
            carrier_val = await page.locator("#addr-carrier").input_value()

            self.record(step_id, "Section 1 'Ünvanı Al' button updates Section 2 carrier selection and triggers reload seamlessly", "PASS", (time.perf_counter() - t0) * 1000, {
                "active_carrier": carrier_val,
                "summary_tag": await page.locator("#addr-summary-tag").inner_text(),
                "full_block_district": [l for l in full_text.splitlines() if "Güngören" in l or "İl/İlçe" in l]
            })
        except Exception as e:
            self.record(step_id, "Section 1 to Section 2 integration test failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))

    async def test_rapid_toggle_determinism(self, page: Page):
        t0 = time.perf_counter()
        step_id = "TASK-10.DETERMINISM_RAPID_SWITCH"
        try:
            carriers = ["STAREX", "CAMEX", "DYNAMEX", "LIMAK"]
            for i in range(6):
                c = carriers[i % len(carriers)]
                await page.locator("#addr-carrier").select_option(c)

            # Final stable selection: LIMAK on Trendyol, branch Sumqayıt
            await page.locator("#btn-plat-trendyol").click()
            await page.locator("#addr-carrier").select_option("LIMAK")
            await page.wait_for_timeout(300)
            await page.locator("#addr-branch").select_option("Sumqayıt")
            await page.wait_for_timeout(200)

            # Deterministic condition wait
            await expect(page.locator("#addr-summary-tag")).to_contain_text("LIMAK", timeout=3000)
            await expect(page.locator("#addr-summary-tag")).to_contain_text("Sumqayıt", timeout=3000)
            await expect(page.locator("#addr-full-block")).to_contain_text("Təhvil Filialı: Sumqayıt", timeout=5000)
            await expect(page.locator("#addr-full-block")).to_contain_text("Küçükçekmece", timeout=5000)

            self.record(step_id, "Deterministic state convergence after rapid control cycling without race conditions", "PASS", (time.perf_counter() - t0) * 1000, {
                "final_summary": await page.locator("#addr-summary-tag").inner_text(),
                "final_full_block_line": [l for l in (await page.locator("#addr-full-block").inner_text()).splitlines() if "Sumqayıt" in l]
            })
        except Exception as e:
            self.record(step_id, "Rapid toggle determinism test failed", "FAIL", (time.perf_counter() - t0) * 1000, error=str(e))


import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_e2e_address_formatter_battery():
    """Pytest entrypoint for the complete E2E Address Formatter & Clipboard battery."""
    tester = AddressFormatterE2ETester(
        base_url="http://127.0.0.1:48481",
        output_dir="C:/Users/vasif/.gemini/antigravity/scratch/test_results"
    )
    await tester.run_all()
    failed = [r for r in tester.results if r.status == "FAIL"]
    assert len(failed) == 0, f"Failed steps: {[r.step_id for r in failed]}"


if __name__ == "__main__":
    tester = AddressFormatterE2ETester(
        base_url="http://127.0.0.1:48481",
        output_dir="C:/Users/vasif/.gemini/antigravity/scratch/test_results"
    )
    asyncio.run(tester.run_all())

