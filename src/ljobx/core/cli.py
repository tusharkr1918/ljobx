import argparse
import asyncio
import json
import shutil
import time

from ljobx.utils import logger
from ljobx.utils.const import FILTERS
from ljobx.core.config import config
from ljobx.core.scraper import run_scraper

def main():
    """Parses command-line arguments and runs the LinkedIn job scraper."""

    epilog_example = """
Example Usage:
  ljobx "Senior Python Developer" "Noida, India" --job-type "Full-time" "Contract" --date-posted "Past week" --max-jobs 50 --concurrency 2 --delay 3 8 --log-level DEBUG
"""

    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job postings using its internal API.",
        epilog=epilog_example,
        formatter_class=argparse.RawTextHelpFormatter
    )

    # Required arguments
    required_group = parser.add_argument_group("Required Arguments")
    required_group.add_argument("keywords", type=str, help="Job title or keywords to search for.")
    required_group.add_argument("location", type=str, help="Geographical location to search in.")

    # Filtering options
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

    # Scraper settings
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

    args = parser.parse_args()

    logger.setup_logger(args.log_level)
    log = logger.get_logger(__name__)
    log.info(f"Scraper starting for '{args.keywords}' in '{args.location}'")

    scraper_settings = {
        "max_jobs": args.max_jobs,
        "concurrency_limit": args.concurrency,
        "delay": {"min_val": args.delay[0], "max_val": args.delay[1]}
    }

    search_criteria = {
        key: value for key, value in vars(args).items()
        if value is not None and key not in ["max_jobs", "concurrency", "delay", "log_level"]
    }

    print("--- Scraper Configuration ---")
    print(f"Search Criteria: {search_criteria}")
    print(f"Scraper Settings: {scraper_settings}")
    print("-----------------------------\n")

    # Run scraper
    results = asyncio.run(
        run_scraper(search_criteria=search_criteria, **scraper_settings)
    )

    if results:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = search_criteria['keywords'].lower().replace(' ', '_')
        filename = f"{base_name}_jobs_{timestamp}.json"
        output_path = config.BASE_OUTPUT_DIR / filename

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        log.info(f"Successfully extracted {len(results)} jobs -> saved to {output_path}")

        latest_path = config.BASE_OUTPUT_DIR / f"{base_name}_jobs_latest.json"
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
