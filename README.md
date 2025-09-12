# LinkedIn Job Extractor (ljobx)

A fast and simple **command-line tool** to scrape LinkedIn job postings without needing to log in.
It uses **LinkedIn’s guest APIs**, supports **proxy rotation**, and provides rich filtering, concurrency, and structured JSON output.

---

## 🔧 Features

* ✅ Search LinkedIn jobs without authentication
* ✅ Filter by **date posted, experience level, job type, remote options**
* ✅ Concurrency & randomized delays for faster + safer scraping
* ✅ Save results to **timestamped JSON files** + `latest` symlink
* ✅ Proxy support via **YAML or remote config URLs**

---

## 🚀 Installation

Install directly from **PyPI**:

```sh
pip install ljobx
```

---

## ⚡ Usage

Run `ljobx` from the command line:

```sh
ljobx "Senior Python Developer" "Noida, India" \
      --job-type "Full-time" "Contract" \
      --experience-level "Entry level" "Associate" \
      --date-posted "Past week" \
      --remote "Hybrid" \
      --max-jobs 50 \
      --concurrency 2 \
      --delay 3 8 \
      --log-level DEBUG
```

---

## 📌 CLI Options

### Required arguments

* `keywords` → Job title or keywords to search for
* `location` → Geographical location to search in

### Filtering options (from LinkedIn API)

* `--date-posted` → `Any time`, `Past month`, `Past week`, `Past day`
* `--experience-level` → `Internship`, `Entry level`, `Associate`, `Mid-Senior level`, `Director`, `Executive`
* `--job-type` → `Full-time`, `Part-time`, `Contract`, `Temporary`, `Volunteer`, `Internship`, `Other`
* `--remote` → `On-site`, `Remote`, `Hybrid`

### Scraper settings

* `--max-jobs` → Maximum number of jobs to scrape (default: 25)
* `--concurrency` → Number of concurrent requests (default: 2)
* `--delay MIN MAX` → Random delay between requests in seconds (default: 3 8)
* `--log-level` → Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)

### Proxy configuration

* `--proxy-config FILE_OR_URL` → Path or URL to a proxy YAML config

Example config (`config.yml`):

```yaml
proxy_providers:
  - name: webshare
    config:
      api_key: "your_api_key_here"
      page_size: 10

validate_proxies: false
```

---

## 📂 Output

Results are saved as JSON under the configured output directory:

* **Timestamped file:**

  ```
  senior_python_developer_20250907_232501.json
  ```
* **Latest symlink (or copy if symlinks not supported):**

  ```
  senior_python_developer_latest.json
  ```

---

## 🛠 Example with Proxy

```sh
ljobx "Data Scientist" "Noida, Inda" \
      --max-jobs 30 \
      --proxy-config "config.yml"
```

Or use a remote config:

```sh
ljobx "SDE" "United States" \
      --proxy-config "https://path.to/your/config.yml"
```
