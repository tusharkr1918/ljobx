# LinkedIn Job Extractor (ljobx)

A fast and simple **command-line tool** to scrape LinkedIn job postings without needing to log in.
It uses LinkedIn’s guest APIs and provides filtering options, concurrency, and structured JSON output.

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

## 🔧 CLI Options

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

---

## 📂 Output

Results are saved as JSON under the configured `BASE_OUTPUT_DIR`:

* Timestamped file:

  ```
  senior_python_developer_jobs_20250907_232501.json
  ```
* Latest symlink (or copy if symlinks not supported):

  ```
  senior_python_developer_jobs_latest.json
  ```
