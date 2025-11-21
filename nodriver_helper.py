import nodriver as uc
import asyncio
import json
import random
import os
from typing import List, Dict, Optional, Tuple


class NodriverBrowser:
    """
    Context manager for nodriver browser lifecycle management.
    Ensures proper cleanup even if errors occur.

    Usage:
        async with NodriverBrowser() as browser:
            results = await fetch_json_from_urls(browser, urls)
    """

    def __init__(self):
        self.browser = None

    async def __aenter__(self):
        self.browser = await uc.start()
        return self.browser

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.browser:
            try:
                await self.browser.stop()
            except Exception:
                pass  # Ignore errors when stopping browser
        return False


def sanitize_filename(text: str) -> str:
    """
    Sanitize text for use in filenames by replacing problematic characters.

    Args:
        text: Text to sanitize (e.g., domain name)

    Returns:
        Sanitized string safe for use in filenames
    """
    return text.replace(".", "_").replace("/", "_").replace(":", "_")


def extract_json_from_content(content: str) -> dict:
    """
    Extract JSON from page content. Tries pure JSON first, then falls back
    to extracting JSON embedded in HTML content.

    Args:
        content: Raw page content (JSON or HTML with embedded JSON)

    Returns:
        Parsed JSON as dictionary

    Raises:
        ValueError: If JSON cannot be extracted or parsed
        json.JSONDecodeError: If JSON is malformed
    """
    try:
        # First, assume content is pure JSON
        return json.loads(content)
    except json.JSONDecodeError:
        # If not, assume it's HTML with embedded JSON
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        if start_idx != -1 and end_idx != 0:
            json_str = content[start_idx:end_idx]
            return json.loads(json_str)
        else:
            raise ValueError("Could not extract JSON from page content.")


async def fetch_json_from_urls(
    browser,
    urls: List[str],
    wait_time: float = 3.0,
    selector: str = 'body',
    selector_timeout: float = 10.0,
    delay_range: Tuple[float, float] = (3.0, 15.0),
    debug_dir: Optional[str] = "debug_pages"
) -> List[Dict]:
    """
    Fetch and parse JSON content from multiple URLs using a single browser instance.
    Each URL is opened in a new tab for isolation, then closed after processing.

    Args:
        browser: Active nodriver browser instance
        urls: List of URLs to fetch
        wait_time: Seconds to wait after page load (default: 3.0)
        selector: CSS selector to wait for (default: 'body')
        selector_timeout: Timeout for selector wait in seconds (default: 10.0)
        delay_range: Tuple of (min, max) seconds for random delay between requests (default: 3-15)
        debug_dir: Directory to save failed page content for debugging (default: 'debug_pages', None to disable)

    Returns:
        List of result dictionaries, one per URL:
        - Success: {"url": str, "status": "success", "data": dict}
        - Error: {"url": str, "status": "error", "error": str, "content": str (optional)}
    """
    results = []

    for i, url in enumerate(urls):
        page = None
        content = None

        try:
            # Open URL in new tab for isolation
            page = await browser.get(url, new_tab=True)

            # Wait for page to load
            await page.sleep(wait_time)

            # Try to wait for selector (continue even if it times out)
            try:
                await page.select(selector, timeout=selector_timeout)
            except Exception:
                pass  # Continue even if selector times out

            # Get page content
            content = await page.get_content()

            # Parse JSON from content
            data = extract_json_from_content(content)

            results.append({
                "url": url,
                "status": "success",
                "data": data
            })

        except Exception as e:
            # Save debug content if enabled and content was captured
            if debug_dir and content:
                if not os.path.exists(debug_dir):
                    os.makedirs(debug_dir)

                # Create safe filename from URL
                safe_name = sanitize_filename(url)
                debug_path = os.path.join(debug_dir, f"{safe_name}.html")

                with open(debug_path, "w") as f:
                    f.write(content)

            results.append({
                "url": url,
                "status": "error",
                "error": str(e),
                "content": content if content else None
            })

        finally:
            # Close the tab
            if page:
                try:
                    await page.close()
                except Exception:
                    pass  # Ignore errors when closing page

            # Apply random delay between requests (but not after the last one)
            if i < len(urls) - 1:
                delay = random.uniform(delay_range[0], delay_range[1])
                await asyncio.sleep(delay)

    return results
