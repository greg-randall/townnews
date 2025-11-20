# TownNews Scraper and Normalizer

This project contains scripts to collect and normalize news articles from websites using the TownNews CMS.

## Workflow

1.  **Collect**: `collect_news.py` reads a list of domains from `townnews.txt` and scrapes the latest articles from their JSON search feeds. The raw JSON data is saved in the `raw_news_data/` directory, organized by date and timestamp.
2.  **Normalize**: `normalize_news.py` processes the raw data, cleans it, converts HTML content to Markdown, and standardizes the data structure. The final normalized JSON files are saved in the `../normalized_news/` directory.

## Prerequisites

- Python 3
- Required Python packages

Install the dependencies with pip:
```bash
pip install nodriver tqdm python-dateutil markdownify
```

## Usage

1.  **Create `townnews.txt`**: In the same directory as the scripts, create a file named `townnews.txt`. Add one TownNews domain per line.

    ```
    fictionaldailypress.com
    statelinegazette.com
    townvillechronicle.com
    ```

2.  **Run the Collection Script**:
    ```bash
    python collect_news.py
    ```
    This will create the `raw_news_data/` directory and populate it with JSON files from the specified domains.

3.  **Run the Normalization Script**:
    ```bash
    python normalize_news.py
    ```
    This will process the raw data and save the clean, standardized JSON files into a `normalized_news` directory (located one level above the project directory).

## Data Format

The normalization script outputs JSON files where each file contains an array of article objects. The structure of these objects is defined in `normalized_news_standard.md`.

Key fields in the normalized data include:
- `url`: The full URL to the original article.
- `title`: The article headline.
- `article_text`: The full article content in Markdown format.
- `source_domain`: The domain the article was scraped from.
- `first_seen_timestamp_gmt`: The Unix timestamp (UTC) when the article was first scraped.
- `publication_timestamp_gmt`: The Unix timestamp (UTC) of the article's publication.
- `author`: The article's author, if available.
- `keywords`: A list of tags, categories, and sections.

## Directory Structure

```
.
├── townnews/
│   ├── collect_news.py             # Step 1: Collects raw data
│   ├── normalize_news.py           # Step 2: Normalizes raw data
│   ├── townnews.txt                # User-created list of domains
│   ├── raw_news_data/              # Output of collect_news.py
│   │   └── 2025-11-20/
│   │       └── 1668960000/
│   │           ├── corsicanadailysun_com.json
│   │           └── _collection_summary.json
│   └── normalized_news_standard.md # Data format documentation
│
└── normalized_news/                # Output of normalize_news.py
    ├── townnews_corsicanadailysun_com.json
    └── _normalization_summary.json
```
