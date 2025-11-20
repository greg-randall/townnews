import os
import json
import nodriver as uc
import asyncio
import time
import random
from datetime import datetime
from tqdm import tqdm

async def collect_news(domains_file="townnews.txt"):
    """
    Collects news articles from a list of TownNews CMS domains using nodriver.
    """
    # Create the main directory for raw news data if it doesn't exist
    if not os.path.exists("raw_news_data"):
        os.makedirs("raw_news_data")

    # Create a directory for the current date
    date_str = datetime.now().strftime("%Y-%m-%d")
    date_dir = os.path.join("raw_news_data", date_str)
    if not os.path.exists(date_dir):
        os.makedirs(date_dir)

    # Create a directory for the current timestamp
    timestamp_str = str(int(time.time()))
    timestamp_dir = os.path.join(date_dir, timestamp_str)
    os.makedirs(timestamp_dir)

    summary = {
        "collection_timestamp": timestamp_str,
        "collection_date": date_str,
        "results": []
    }

    try:
        with open(domains_file, 'r') as f:
            domains = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: '{domains_file}' not found.")
        return

    browser = await uc.start()

    for domain in tqdm(domains, desc="Collecting news", unit="domain"):
        page = None
        try:
            url = f"https://{domain}/search/?l=100&f=json"
            # use new_tab=True for isolation between requests
            page = await browser.get(url, new_tab=True)

            # Wait for the page to load - give it time to render
            await page.sleep(3)

            # Try to wait for body to be present
            try:
                await page.select('body', timeout=10)
            except Exception:
                pass  # Continue even if body selector times out

            content = await page.get_content()

            data = None
            try:
                # First, assume content is pure JSON
                data = json.loads(content)
            except json.JSONDecodeError:
                # If not, assume it's HTML with embedded JSON.
                # A simple way to extract it without a new dependency.
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = content[start_idx:end_idx]
                    data = json.loads(json_str)
                else:
                    # If we can't find it, raise an error to be caught below
                    raise ValueError("Could not extract JSON from page content.")

            # Sanitize domain for filename
            filename = domain.replace(".", "_") + ".json"
            filepath = os.path.join(timestamp_dir, filename)

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)

            summary["results"].append({
                "domain": domain,
                "status": "success",
                "article_count": data.get("total", 0),
                "file_path": filepath
            })
            print(f"Successfully collected data from {domain}")

        except Exception as e:
            if 'content' in locals() and content:
                debug_dir = "debug_pages"
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)
                safe_domain = domain.replace(".", "_")
                with open(os.path.join(debug_dir, f"{safe_domain}.html"), "w") as f:
                    f.write(content)
                print(f"Saved page content for {domain} to debug_pages/{safe_domain}.html")

            summary["results"].append({
                "domain": domain,
                "status": "error",
                "error_message": str(e)
            })
            print(f"Error collecting data from {domain}: {e}")
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass  # Ignore errors when closing page

            # Random delay between 3 and 15 seconds for stealth
            delay = random.uniform(3, 15)
            print(f"Waiting {delay:.1f} seconds before next domain...")
            await asyncio.sleep(delay)


    if browser:
        try:
            await browser.stop()
        except Exception:
            pass  # Ignore errors when stopping browser

    # Write summary file
    summary_filepath = os.path.join(timestamp_dir, "_collection_summary.json")
    with open(summary_filepath, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nCollection complete. Summary written to {summary_filepath}")

async def main():
    await collect_news()

if __name__ == "__main__":
    uc.loop().run_until_complete(main())