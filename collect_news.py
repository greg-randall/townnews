import os
import json
import time
import asyncio
from datetime import datetime
from nodriver_helper import NodriverBrowser, fetch_json_from_urls

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

    # Build list of URLs from domains
    urls = [f"https://{domain}/search/?l=100&f=json" for domain in domains]

    # Define callbacks to save data as we fetch it
    def on_success(url, data, index):
        domain = domains[index]

        # Sanitize domain for filename
        filename = domain.replace(".", "_") + ".json"
        filepath = os.path.join(timestamp_dir, filename)

        # Save JSON immediately
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        # Update summary
        summary["results"].append({
            "domain": domain,
            "status": "success",
            "article_count": data.get("total", 0),
            "file_path": filepath
        })

    def on_error(url, error, content, index):
        domain = domains[index]

        # Update summary
        summary["results"].append({
            "domain": domain,
            "status": "error",
            "error_message": error
        })

    # Use context manager for browser lifecycle
    async with NodriverBrowser() as browser:
        # Fetch all URLs using single browser instance with callbacks
        await fetch_json_from_urls(
            browser,
            urls,
            wait_time=3.0,
            selector='body',
            selector_timeout=10.0,
            delay_range=(3.0, 15.0),
            debug_dir="debug_pages",
            on_success=on_success,
            on_error=on_error,
            progress_desc="Collecting news"
        )

    # Write summary file
    summary_filepath = os.path.join(timestamp_dir, "_collection_summary.json")
    with open(summary_filepath, 'w') as f:
        json.dump(summary, f, indent=2)

    print(f"\nCollection complete. Summary written to {summary_filepath}")

async def main():
    await collect_news()

if __name__ == "__main__":
    asyncio.run(main())