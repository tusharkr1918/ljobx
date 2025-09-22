[![PyPI Downloads](https://static.pepy.tech/personalized-badge/ljobx?period=total&units=INTERNATIONAL_SYSTEM&left_color=BLACK&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/ljobx)

[](https://pepy.tech/projects/ljobx)

# LinkedIn Job Extractor (ljobx)

A fast, simple tool to scrape LinkedIn job postings without needing to log in. It can be used as a powerful **command-line script** for automation or as an **interactive web interface** for easy scrapping. It uses LinkedIn’s public APIs, supports flexible proxy configurations, and saves results to JSON or CSV.

The GitHub repository can be found at: [tusharkr1918/ljobx](https://github.com/tusharkr1918/ljobx)

### ✨ Features

* **Dual Interface**: Use it as a powerful **command-line tool** for scripting or as an **interactive web UI**.
* **Simplified UI Mode**: Launch the web interface with a `--basic` flag for a cleaner, more streamlined experience that's perfect for less technical users.
* **No Login Needed**: Scrapes public job postings anonymously.
* **Advanced Filtering**: Filter by date, experience level, job type, and remote options.
* **Concurrent Scraping**: Fetches multiple jobs at once with randomized delays.
* **Flexible Proxy Support**: Load proxies from API providers (like Webshare) or directly from your own local text files.
* **Structured Output**: Save results as clean, timestamped `JSON` or `CSV` files.
* **Latest Symlink**: Automatically creates a `_latest` file pointing to the newest results.

### 📥 Installation

You can install the tool in two ways, depending on your needs.

#### Standard Install (CLI Only)

For just the command-line tool, a standard installation is all you need:

```bash
pip install ljobx
```

#### Full Install (CLI + Web Interface)

To use the interactive web UI, install the package with the `[ui]` extra. This will download the additional libraries needed, like Streamlit.

```bash
pip install 'ljobx[ui]'
```

*(Note: The quotes are important for some shells like zsh.)*

### 🚀 Usage

The tool can be run as a command-line script or as a web application.

#### Command-Line (CLI)

Provide a search query and a location. Use flags for more control.

```bash
# Basic search saving to CSV
ljobx "Software Engineer" "Remote" --to-csv

# Advanced search with multiple filters
ljobx "Senior Python Developer" "Noida, India" \
      --job-type "Full-time" \
      --date-posted "Past week" \
      --max-jobs 50 \
      --concurrency 2 \
      --delay 3 8
```

#### Web Interface (UI)

If you performed a full installation, you can launch the Streamlit web interface.

```bash
# Launch the full-featured web UI
ljobx-ui

# Launch the simplified web UI with fewer options
ljobx-ui --basic
```

For a finer-tuned experience, override the basic UI defaults to adjust concurrency and delay based on your proxy configuration.

```bash
# Launch the basic UI with higher concurrency for faster scraping
ljobx-ui --basic --concurrency 5 --delay 2 4
```

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

### 🔌 Proxy Configuration

The tool offers a powerful and flexible proxy system configured via a YAML file.

**Example `config.yml`:**

```yaml
# --- API Providers (Optional) ---
# Fetches proxies from a supported provider's API.
proxy_providers:
  - name: webshare
    config:
      api_key: "YOUR_WEBSHARE_API_KEY"
      page_size: 100 
      max_pages: 5

# --- Local Files (Optional) ---
# Loads proxies directly from your own text files.
proxies_files:
  - path: "/path/to/your/socks_proxies.txt"
    protocol: "socks5"
```

#### Server & Deployment Usage (Default Proxy Config)

When you run `ljobx` or `ljobx-ui`, it automatically looks for a file named `proxy_config.yml` in a default system location. This is the **recommended method for servers and deployed applications**.

Simply create your `proxy_config.yml` file in the correct directory, and the tool will use it automatically without needing the `--proxy-config` flag.

* **Linux/macOS:** `~/.config/ljobx/proxy_config.yml`
* **Windows:** `C:\Users\<YourUser>\AppData\Roaming\ljobx\proxy_config.yml`

This method is ideal for services like Streamlit Community Cloud, as you can place your configuration file (using API providers, not local file paths) in the repository, and the deployed app will pick it up automatically.

#### Loading Proxies from Files (`proxies_files`)

This feature gives you full control over your proxy lists but is best for local use. The system follows these rules:

* **Default Protocol:** If you specify a `protocol` (e.g., `"socks5"` or `"https"`), it will be automatically added to any proxy in that file that doesn't already have one.
* **No Default Protocol:** If you only provide the `path`, the tool expects every line in the file to be a complete proxy URL (e.g., `socks5://user:pass@ip:port`).
* **Security Filter:** The tool will **always** ignore any proxy that starts with insecure `http://`.

**Command:**

```bash
ljobx "Java Developer" "Delhi, India" --proxy-config "config.yml"
```

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