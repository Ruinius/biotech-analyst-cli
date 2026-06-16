#!/usr/bin/env python3
"""
Direct ChinaDrugTrials (NMPA CDE Clinical Trials) Sourcing Utility
Uses Playwright in stealth mode with WAF bypass capabilities to query official clinical trials database.
Zero mocks. Raises explicit exceptions on connection, WAF block, or empty results.
"""

import argparse
import json
import os
import sys
import time


def fetch_cde_direct(term, proxy_url=None):
    print(f"Initiating ChinaDrugTrials direct search for: '{term}'...")
    if proxy_url:
        print(f"Routing traffic through proxy: {proxy_url}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print("Error: Playwright library is not installed.", file=sys.stderr)
        raise RuntimeError(
            "Playwright is required to perform direct ChinaDrugTrials queries."
        ) from e

    try:
        with sync_playwright() as p:
            print("Launching stealth Chromium browser instance...")
            browser_args = {
                "headless": True,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                ],
            }
            if proxy_url:
                browser_args["proxy"] = {"server": proxy_url}

            browser = p.chromium.launch(**browser_args)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )

            page = context.new_page()

            # Anti-WAF injection
            page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page.add_init_script("window.chrome = { runtime: {} };")

            target_url = "https://www.chinadrugtrials.org.cn/index.html"
            print(f"Navigating to official database: {target_url}")
            response = page.goto(target_url, timeout=25000)

            if not response or response.status not in [200, 202]:
                status_code = response.status if response else "No Response"
                raise RuntimeError(
                    f"Failed to load ChinaDrugTrials portal. WAF blocked session with status: {status_code}"
                )

            page.wait_for_load_state("networkidle")
            time.sleep(3)

            # 1. Locate search input and fill it
            print("Locating query input field on ChinaDrugTrials portal...")
            search_input = page.locator(
                "input[name='keywords'], input.indexSearchInput"
            ).first
            search_input.wait_for(state="visible", timeout=10000)
            search_input.fill(term)
            time.sleep(1)

            # 2. Execute search by pressing Enter
            print("Executing search on live database...")
            search_input.press("Enter")

            # 3. Wait for search results page to load and populate the data grid
            print("Waiting for search results page to load...")
            page.wait_for_load_state("networkidle")
            time.sleep(5)

            # 4. Scrape the data grid rows
            records = []
            rows = page.locator("table tr, .table_list tr, .list_table tr, tr").all()
            print(f"Registry table parsed. Found {len(rows)} potential table rows.")

            for row in rows:
                try:
                    cols = row.locator("td").all_text_contents()
                    if len(cols) >= 6:
                        # Map ChinaDrugTrials Search Result Column Schema:
                        # Col 0: Index (序号)
                        # Col 1: Registration Number (登记号, e.g. CTR20191408)
                        # Col 2: Trial Status (试验状态, e.g. 进行中)
                        # Col 3: Drug Name (药物名称, e.g. 阿司匹林肠溶片)
                        # Col 4: Indication (适应症, e.g. 心肌梗塞)
                        # Col 5: Title (试验通俗题目, e.g. 生物等效性研究)
                        reg_num = cols[1].strip()
                        status = cols[2].strip()
                        drug_name = cols[3].strip()
                        indication = cols[4].strip()
                        title = cols[5].strip()

                        is_header = reg_num in [
                            "登记号",
                            "No.",
                            "Acceptance Number",
                            "",
                        ]
                        if reg_num and not is_header:
                            records.append(
                                {
                                    "acceptance_number": reg_num,
                                    "drug_name": f"{drug_name} ({title})",
                                    "company": f"Indication Target: {indication}",
                                    "date": "N/A (CDE Registered)",
                                    "status": status,
                                    "breakthrough_therapy": "Yes"
                                    if "突破性" in status or "突破性" in "".join(cols)
                                    else "No",
                                }
                            )
                except Exception:
                    pass

            browser.close()

            # Strict validation: raise explicit error if no real records are found, preventing silent/invisible failures
            if not records:
                raise ValueError(
                    f"No authentic ChinaDrugTrials records found matching term: '{term}'."
                )

            return {
                "source": "ChinaDrugTrials Direct Search",
                "term": term,
                "records": records,
            }
    except Exception as e:
        print(
            f"Error executing live Playwright ChinaDrugTrials query: {e}",
            file=sys.stderr,
        )
        raise RuntimeError(
            f"Playwright Direct ChinaDrugTrials search failed: {e}"
        ) from e


def main():
    parser = argparse.ArgumentParser(
        description="Query ChinaDrugTrials Official Portal directly with WAF bypass capabilities"
    )
    parser.add_argument(
        "--term", required=True, help="Search term (e.g., drug name or target)"
    )
    parser.add_argument(
        "--output", default="tmp/china_direct_out.json", help="Path to save raw JSON"
    )
    parser.add_argument(
        "--proxy", help="Optional proxy URL (e.g. http://127.0.0.1:8888)"
    )

    args = parser.parse_args()

    out_dir = os.path.dirname(args.output)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    try:
        data = fetch_cde_direct(args.term, proxy_url=args.proxy)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(
            f"Successfully saved ChinaDrugTrials direct search results to: {args.output}"
        )
    except Exception as e:
        print(f"Fatal error during ChinaDrugTrials query: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
