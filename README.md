# LinkedIn Job Extractor (ljobx)

A fast, simple **command-line tool** to scrape LinkedIn job postings without needing to log in. It uses LinkedIn’s public APIs, supports proxy rotation, and saves results to JSON or CSV.

-----

### ✨ Features

* **No Login Needed**: Scrapes public job postings anonymously.
* **Advanced Filtering**: Filter by date, experience level, job type, and remote options.
* **Concurrent Scraping**: Fetches multiple jobs at once with randomized delays.
* **Proxy Support**: Use proxies to avoid rate-limiting on distributed requests.
* **Structured Output**: Save results as clean, timestamped `JSON` or `CSV` files.
* **Latest Symlink**: Automatically creates a `_latest` file pointing to the newest results.

-----

### 📥 Installation

```sh
pip install ljobx
```

-----

### 🚀 Usage

Provide a search query and a location. Use flags for more control.

```sh
# Basic search saving to CSV
ljobx "Software Engineer" "Remote" --to-csv

# Advanced search with multiple filters
ljobx "Senior Python Developer" "Noida, India" \
      --job-type "Full-time" \
      --date-posted "Past week" \
      --max-jobs 50 \
      --concurrency 5
```

-----

### ⚙️ CLI Options

**Required Arguments:**

* `keywords`: The job title or skill to search for.
* `location`: The geographical location (e.g., "Noida, India", "Remote").

**Filtering Options:**

* `--date-posted`: `Any time`, `Past month`, `Past week`, `Past 24 hours`
* `--experience-level`: `Internship`, `Entry level`, `Associate`, `Mid-Senior level`, etc.
* `--job-type`: `Full-time`, `Contract`, `Part-time`, etc.
* `--remote`: `On-site`, `Remote`, `Hybrid`

**Scraper Settings:**

* `--max-jobs`: Max number of jobs to scrape (Default: `25`).
* `--concurrency`: Number of parallel requests (Default: `2`).
* `--delay MIN MAX`: Random delay range in seconds (Default: `3 8`).
* `--to-csv`: Save output as a CSV file instead of JSON.
* `--proxy-config FILE_OR_URL`: Path or URL to a proxy YAML config.

> 💡 **A Note on Performance**: It's highly recommended to adjust `--concurrency` and `--delay` based on your proxy setup.
>
>   * **With many working proxies**, you can be more aggressive for faster scraping (e.g., `--concurrency 10 --delay 1 3`).
>   * **With few or no proxies**, you must be conservative to avoid getting blocked. **It's safest to use the default values.**

-----

### 🔌 Proxy Configuration

Proxy support is configured via a YAML file passed with the `--proxy-config` flag. Currently, **Webshare.io** is the only supported provider.

**Example `config.yml`:**

```yaml
proxy_providers:
  - name: webshare # Currently the only supported provider
    config:
      api_key: "YOUR_API_KEY_HERE"

validate_proxies: false # Optional: skip proxy validation
```

**Command:**

```sh
ljobx "Java Developer" "Delhi, India" --proxy-config "config.yml"
```

-----

### 📂 Output & Data Fields

Results are saved as timestamped `JSON` or `CSV` files (e.g., `keywords_YYYYMMDD_HHMMSS.json`), with a `_latest` symlink for easy access.

The scraper extracts the following data for each job:

* `job_id`
* `title`
* `company`
* `location`
* `posted_date`
* `applicants` (if available)
* `salary_range` (if available)
* `description`
* `apply` (URL and whether it's an "Easy Apply")
* `recruiter` (Name, Title, and Profile URL, if available)