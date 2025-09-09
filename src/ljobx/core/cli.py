import argparse
import asyncio
import json
import shutil
import time
from pathlib import Path

from ljobx.utils import logger
from ljobx.utils.const import FILTERS
from ljobx.core.config import config
from ljobx.core.scraper import run_scraper
from ljobx.core.proxy_loader import ConfigLoader
from ljobx.api.proxy.proxy_manager import ProxyRouter


def main():
    """Parses command-line arguments and runs the LinkedIn job scraper."""

    epilog_example = """
Example Usage:
  ljobx "Senior Python Developer" "Noida, India" --max-jobs 50 --log-level DEBUG
  ljobx "Data Scientist" "Remote" --job-type "Full-time" --proxy-config "config.yml"
  ljobx "SDE" "United States" --proxy-config "https://path.to/your/config.yml"
"""

    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job postings using its internal API.",
        epilog=epilog_example,
        formatter_class=argparse.RawTextHelpFormatter
    )

    required_group = parser.add_argument_group("Required Arguments")
    required_group.add_argument("keywords", type=str, help="Job title or keywords to search for.")
    required_group.add_argument("location", type=str, help="Geographical location to search in.")

    filter_group = parser.add_argument_group("Filtering Options")
    for key, param_config in FILTERS.items():
        flag_name = f"--{key.replace('_', '-')}"
        help_text = f"Filter by {key.replace('_', ' ')}.\nChoices: {', '.join(param_config['options'].keys())}"
        if param_config['allowMultiple']:
            filter_group.add_argument(
                flag_name, type=str, choices=param_config['options'].keys(),
                nargs='+', metavar='OPTION', help=help_text
            )
        else:
            filter_group.add_argument(flag_name, type=str, choices=param_config['options'].keys(), help=help_text)

    scraper_group = parser.add_argument_group("Scraper Settings")
    scraper_group.add_argument("--max-jobs", type=int, default=25,
                               help="Maximum number of jobs to scrape (default: 25).")
    scraper_group.add_argument("--concurrency", type=int, default=2,
                               help="Number of concurrent requests for job details (default: 2).")
    scraper_group.add_argument("--delay", type=int, nargs=2, metavar=("MIN", "MAX"), default=[3, 8],
                               help="Min and max delay in seconds between concurrent requests (default: 1 8).")
    scraper_group.add_argument("--log-level", type=str, default="INFO",
                               choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                               help="Set logging level (default: INFO)")
    scraper_group.add_argument("--proxy-config", type=str, default=None, metavar="FILE_OR_URL",
                               help="Path or URL to the proxy configuration YAML file.")
    scraper_group.add_argument("--output-path", type=str, default=None,
                               help=f"Path to save output files (default: {config.BASE_DIR}).")

    args = parser.parse_args()

    # Initialize logger
    logger.setup_logger(args.log_level)
    log = logger.get_logger(__name__)

    output_dir = Path(args.output_path) if args.output_path else config.BASE_DIR

    # --- Log Message ---
    search_criteria = {
        key: value for key, value in vars(args).items()
        if value is not None and key in FILTERS
    }
    search_criteria['keywords'] = args.keywords
    search_criteria['location'] = args.location

    scraper_settings = {
        "max_jobs": args.max_jobs,
        "concurrency_limit": args.concurrency,
        "delay": {"min_val": args.delay[0], "max_val": args.delay[1]},
    }

    run_config = {
        "Search Criteria": search_criteria,
        "Scraper Settings": scraper_settings,
        "System Settings": {
            "log_level": args.log_level,
            "proxy_config_path": args.proxy_config,
            "output_path": str(output_dir)
        }
    }

    log.info(
        "\n--- LJOBX Configuration ---\n%s\n-----------------------------",
        json.dumps(run_config, indent=4, default=str)
    )

    proxies = []
    if args.proxy_config:
        log.info(f"Loading proxies from '{args.proxy_config}'...")
        try:
            config_data = ConfigLoader.load(args.proxy_config)
            proxies = asyncio.run(ProxyRouter.get_proxies_from_config(config_data, validate=config_data.get("validate_proxies", True)))
            if not proxies:
                log.warning("No working proxies found from the provided configuration. The scraper will run without proxies.")
        except (ValueError, FileNotFoundError) as e:
            log.error(f"Failed to load proxies: {e}")
            return

    scraper_settings["proxies"] = proxies
    results = asyncio.run(
        run_scraper(search_criteria=search_criteria, **scraper_settings)
    )

    if results:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = search_criteria['keywords'].lower().replace(' ', '_')
        filename = f"{base_name}_{timestamp}.json"
        output_path = output_dir / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        log.info(f"Successfully extracted {len(results)} jobs -> saved to {output_path}")

        latest_path = output_dir / f"{base_name}_latest.json"
        try:
            if latest_path.exists() or latest_path.is_symlink():
                latest_path.unlink()
            latest_path.symlink_to(output_path.name)
            log.info(f"Symlink updated -> {latest_path} -> {output_path.name}")
        except (OSError, NotImplementedError):
            shutil.copy2(output_path, latest_path)
            log.warning(f"Symlink not supported, copied instead -> {latest_path}")


if __name__ == "__main__":
    main()

