import os
import json
import html
import re
import hashlib
from datetime import datetime
from pathlib import Path
from dateutil import parser as date_parser

from markdownify import markdownify as md


def get_url_hash(url):
    """
    Generate MD5 hash of URL for use as filename.

    Args:
        url: Article URL string

    Returns:
        MD5 hash as hex string
    """
    if not url:
        return None
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def normalize_article(article_data, source_domain, scrape_timestamp):
    """
    Normalize a single article from TownNews format to standardized format.

    Args:
        article_data: Dict containing the raw article data
        source_domain: String domain name of the source
        scrape_timestamp: Unix timestamp when this scrape run started

    Returns:
        Dict with standardized fields
    """
    # Extract and decode content
    content_parts = article_data.get("content", [])
    prologue = article_data.get("prologue") or ""

    # Filter content parts to only include strings (some entries may be dicts or lists)
    def extract_text(item):
        """Recursively extract text from content items."""
        if isinstance(item, str):
            return item
        elif isinstance(item, dict):
            # Try to extract text from dict values
            text_parts = []
            for value in item.values():
                if isinstance(value, str):
                    text_parts.append(value)
                elif isinstance(value, (list, dict)):
                    extracted = extract_text(value)
                    if extracted:
                        text_parts.append(extracted)
            return " ".join(text_parts)
        elif isinstance(item, list):
            # Process list items
            text_parts = []
            for subitem in item:
                extracted = extract_text(subitem)
                if extracted and isinstance(extracted, str):
                    text_parts.append(extracted)
            return " ".join(text_parts)
        return ""

    filtered_content = []
    for item in content_parts:
        text = extract_text(item)
        if text:
            filtered_content.append(text)

    # Combine all content parts into one text
    raw_text = prologue + " " + " ".join(filtered_content)

    # HTML decode the text
    decoded_text = html.unescape(raw_text)

    # Convert HTML to Markdown
    markdown_text = md(decoded_text, heading_style="ATX")

    # Extract publication date and create Unix timestamp
    starttime = article_data.get("starttime", {})
    pub_date_original = starttime.get("iso8601") or starttime.get("rfc2822")

    # Parse to Unix timestamp (GMT)
    pub_timestamp_gmt = None
    if pub_date_original:
        try:
            parsed_date = date_parser.parse(pub_date_original)
            pub_timestamp_gmt = int(parsed_date.timestamp())
        except Exception:
            # If parsing fails, try using the UTC timestamp directly if available
            utc_timestamp = starttime.get("utc")
            if utc_timestamp:
                try:
                    # TownNews UTC timestamps appear to be in milliseconds
                    pub_timestamp_gmt = int(utc_timestamp) // 1000
                except (ValueError, TypeError):
                    pass

    # Extract authors
    authors_list = article_data.get("authors", [])
    byline = article_data.get("byline", "")

    # Prefer structured authors list, fall back to byline
    if authors_list:
        # Authors can be either strings or dicts with author info
        author_names = []
        for author_item in authors_list:
            if isinstance(author_item, str):
                author_names.append(author_item)
            elif isinstance(author_item, dict):
                # Try to extract name from dict (prefer full_name, then combine first/last)
                name = (author_item.get("full_name") or
                       f"{author_item.get('first_name', '')} {author_item.get('last_name', '')}".strip() or
                       author_item.get("screen_name"))
                if name:
                    author_names.append(name)
        author = ", ".join(author_names) if author_names else None
    elif byline:
        author = byline
    else:
        author = None

    # Combine keywords and sections into a single keywords field
    keywords_list = article_data.get("keywords", [])
    sections_list = article_data.get("sections", [])
    # Merge both, removing duplicates while preserving order
    all_keywords = []
    seen = set()
    for keyword in keywords_list + sections_list:
        if keyword and keyword not in seen:
            all_keywords.append(keyword)
            seen.add(keyword)

    # Build standardized article
    normalized = {
        "url": article_data.get("url"),
        "title": article_data.get("title"),
        "article_text": markdown_text,
        "source_domain": source_domain,
        "publication_date": pub_date_original,
        "publication_timestamp_gmt": pub_timestamp_gmt,
        "first_seen_timestamp_gmt": scrape_timestamp,
        "author": author,
        "keywords": all_keywords
    }

    return normalized


def normalize_townnews_file(input_filepath, output_dir, scrape_timestamp=None):
    """
    Process a single TownNews JSON file and write normalized articles to individual files.

    Args:
        input_filepath: Path to the raw JSON file
        output_dir: Base directory for normalized output
        scrape_timestamp: Unix timestamp when this data was scraped (extracted from directory name)

    Returns:
        Dict with statistics: articles_new, articles_skipped, errors
    """
    with open(input_filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # If no scrape timestamp provided, try to extract from directory structure
    # Format: raw_news_data/2025-11-20/1763657957/file.json
    if scrape_timestamp is None:
        path_parts = Path(input_filepath).parts
        for part in path_parts:
            # Look for unix timestamp (10 digits)
            if part.isdigit() and len(part) == 10:
                scrape_timestamp = int(part)
                break
        # Fallback to current time if not found
        if scrape_timestamp is None:
            scrape_timestamp = int(datetime.now().timestamp())

    # Extract domain from filename (e.g., athensreview_com.json -> athensreview.com)
    filename = os.path.basename(input_filepath)
    domain = filename.replace(".json", "").replace("_", ".")

    # Create domain-specific subdirectory
    domain_dir = os.path.join(output_dir, domain)
    os.makedirs(domain_dir, exist_ok=True)

    # Track statistics
    stats = {
        "articles_new": 0,
        "articles_skipped": 0,
        "articles_skipped_image_type": 0,
        "errors": 0
    }

    # Process all articles in the "rows" field
    rows = data.get("rows", [])

    for article in rows:
        try:
            # Skip image-only items (just photos with captions)
            if article.get("type") == "image":
                stats["articles_skipped_image_type"] += 1
                continue

            # Get URL hash for filename
            url = article.get("url")
            url_hash = get_url_hash(url)

            if not url_hash:
                stats["errors"] += 1
                continue

            # Check if article already exists
            output_filepath = os.path.join(domain_dir, f"{url_hash}.json")
            if os.path.exists(output_filepath):
                stats["articles_skipped"] += 1
                continue

            # Normalize and write article
            normalized = normalize_article(article, domain, scrape_timestamp)

            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(normalized, f, indent=2, ensure_ascii=False)

            stats["articles_new"] += 1

        except Exception as e:
            print(f"Error normalizing article from {domain}: {e}")
            stats["errors"] += 1
            continue

    return stats


def process_all_raw_data(raw_data_dir="raw_news_data", output_dir="../normalized_news"):
    """
    Process all raw TownNews data and output normalized JSON files.

    Args:
        raw_data_dir: Directory containing raw_news_data
        output_dir: Directory to write normalized data (one level up)
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Track overall statistics
    overall_stats = {
        "files_processed": 0,
        "articles_new": 0,
        "articles_skipped": 0,
        "articles_skipped_image_type": 0,
        "errors": 0
    }

    # Walk through all date/timestamp directories
    for date_dir in Path(raw_data_dir).iterdir():
        if not date_dir.is_dir():
            continue

        for timestamp_dir in date_dir.iterdir():
            if not timestamp_dir.is_dir():
                continue

            # Track statistics for this timestamp directory
            timestamp_stats = {
                "files_processed": 0,
                "articles_new": 0,
                "articles_skipped": 0,
                "articles_skipped_image_type": 0,
                "errors": 0
            }

            # Process each JSON file in the timestamp directory
            for json_file in timestamp_dir.glob("*.json"):
                # Skip summary files
                if json_file.name.startswith("_"):
                    continue

                try:
                    print(f"Processing {json_file}...")
                    file_stats = normalize_townnews_file(json_file, output_dir)

                    timestamp_stats["files_processed"] += 1
                    timestamp_stats["articles_new"] += file_stats["articles_new"]
                    timestamp_stats["articles_skipped"] += file_stats["articles_skipped"]
                    timestamp_stats["articles_skipped_image_type"] += file_stats["articles_skipped_image_type"]
                    timestamp_stats["errors"] += file_stats["errors"]

                    print(f"  ✓ New: {file_stats['articles_new']}, Skipped: {file_stats['articles_skipped']}, Images: {file_stats['articles_skipped_image_type']}, Errors: {file_stats['errors']}")

                except Exception as e:
                    print(f"  ✗ Error processing {json_file}: {e}")
                    timestamp_stats["errors"] += 1

            # Write summary for this timestamp directory
            if timestamp_stats["files_processed"] > 0:
                summary_path = timestamp_dir / "_normalization_summary.json"
                summary = {
                    "timestamp": datetime.now().isoformat(),
                    "source": "townnews",
                    "statistics": timestamp_stats
                }

                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(summary, f, indent=2)

                print(f"  → Summary written to {summary_path}")

            # Update overall statistics
            overall_stats["files_processed"] += timestamp_stats["files_processed"]
            overall_stats["articles_new"] += timestamp_stats["articles_new"]
            overall_stats["articles_skipped"] += timestamp_stats["articles_skipped"]
            overall_stats["articles_skipped_image_type"] += timestamp_stats["articles_skipped_image_type"]
            overall_stats["errors"] += timestamp_stats["errors"]

    print(f"\n=== Normalization Complete ===")
    print(f"Files processed: {overall_stats['files_processed']}")
    print(f"Articles new: {overall_stats['articles_new']}")
    print(f"Articles skipped (already exists): {overall_stats['articles_skipped']}")
    print(f"Articles skipped (image type): {overall_stats['articles_skipped_image_type']}")
    print(f"Errors: {overall_stats['errors']}")


if __name__ == "__main__":
    process_all_raw_data()
