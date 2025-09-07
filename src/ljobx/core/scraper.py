import asyncio
import json
import random
from typing import Dict, List, Any

from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote
from ljobx.api.client import ApiClient
from ljobx.utils.const import FILTERS
from ljobx.utils.logger import get_logger

logger = get_logger(__name__)


def clean_text(text: str | None) -> str | None:
    """Strip leading/trailing whitespace from a string."""
    return text.strip() if text else None


class LinkedInScraper:
    """
    Scrapes LinkedIn jobs using a direct API approach with a powerful query builder.
    """

    def __init__(self, concurrency_limit: int = 5, delay: int = 1):
        self.client = ApiClient(concurrency_limit=concurrency_limit, delay=delay)

    @classmethod
    def build_search_query(cls, criteria: Dict[str, Any]) -> Dict[str, str]:
        """Constructs a dictionary of query parameters for the LinkedIn jobs API."""
        query_params: Dict[str, str] = {}
        for key in ['keywords', 'location', 'start']:
            if key in criteria:
                query_params[key] = str(criteria[key])

        for key, user_values in criteria.items():
            if key in FILTERS:
                param_meta = FILTERS[key]
                param_key = param_meta['param']
                options_map = param_meta['options']

                values = user_values if isinstance(user_values, list) else [user_values]

                api_values = [
                    str(options_map.get(v))
                    for v in values
                    if v in options_map and options_map.get(v) is not None
                ]
                if api_values:
                    query_params[param_key] = ",".join(api_values)

        return query_params

    @staticmethod
    def _parse_job_details(job: Dict[str, Any], html_content: str | Dict) -> Dict[str, Any]:
        """Parses the HTML of a job details page to extract structured data."""
        details = {"job_id": job["job_id"]}
        if isinstance(html_content, dict) and 'error' in html_content:
            logger.warning(
                "Could not fetch details for '%s' at '%s' (ID: %s). Reason: %s",
                job.get('title', 'N/A'),
                job.get('company', 'N/A'),
                job.get('job_id'),
                html_content.get('error', 'Unknown'),
            )
            return {**details, **html_content}

        soup = BeautifulSoup(html_content, "html.parser")

        top_card = soup.find("section", class_="top-card-layout")
        if top_card:
            location_el = top_card.find("span", class_="topcard__flavor--bullet")
            details["location"] = clean_text(location_el.get_text()) if location_el else None

            posted_date_el = top_card.find("span", class_="posted-time-ago__text")
            details["posted_date"] = clean_text(posted_date_el.get_text()) if posted_date_el else None

            apps_fig = top_card.find("figcaption", class_="num-applicants__caption")
            details["applicants"] = clean_text(apps_fig.get_text()) if apps_fig else None

        desc_div = soup.find("div", class_="show-more-less-html__markup")

        # noinspection PyArgumentList
        description = desc_div.get_text(separator='\n', strip=True) if desc_div else None
        details["description"] = description

        logger.info(
            "Parsed: %s | %s | %s...",
            job.get('company', 'N/A'),
            job.get('title', 'N/A'),
            (description[:75].replace('\n', ' ') if description else "No description found"),
        )

        apply_details: Dict[str, Any] = {}
        apply_el = soup.find("code", id="applyUrl")
        if apply_el and apply_el.string:
            raw_url = apply_el.string.strip().strip('"')
            try:
                parsed = urlparse(raw_url)
                query = parse_qs(parsed.query)
                apply_details["url"] = unquote(query['url'][0]) if 'url' in query and query['url'] else raw_url
            except (KeyError, IndexError, ValueError):
                apply_details["url"] = raw_url
            apply_details["is_easy_apply"] = False
        else:
            job_link_el = top_card.find("a", class_="topcard__link") if top_card else None
            apply_details["url"] = job_link_el.get('href') if job_link_el else None
            apply_details["is_easy_apply"] = True

        details["apply"] = apply_details if apply_details.get("url") else None

        salary_range_el = soup.find("div", class_="salary compensation__salary")
        details["salary_range"] = clean_text(salary_range_el.get_text()) if salary_range_el else None

        recruiter_section = soup.find("div", class_="message-the-recruiter")
        if recruiter_section:
            recruiter_details: Dict[str, str | None] = {}
            name_el = recruiter_section.find("h3", class_="base-main-card__title")
            recruiter_details["name"] = clean_text(name_el.get_text()) if name_el else None

            title_el = recruiter_section.find("h4", class_="base-main-card__subtitle")
            recruiter_details["title"] = clean_text(title_el.get_text()) if title_el else None

            profile_el = recruiter_section.find("a", class_="base-card__full-link")
            recruiter_details["profile_url"] = profile_el.get('href') if profile_el else None

            details["recruiter"] = recruiter_details
        else:
            details["recruiter"] = None

        return details

    async def _get_and_parse_details(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches and parses the details for a single job."""
        html_content = await self.client.get_job_details(job["job_id"])
        return self._parse_job_details(job, html_content)

    async def run(self, search_criteria: Dict[str, Any], max_jobs: int = 50) -> List[Dict[str, Any]]:
        """Executes the full scraping pipeline."""
        validated_query = self.build_search_query(search_criteria)
        logger.info("Starting fetch with validated query parameters: %s", json.dumps(validated_query, indent=2))

        all_jobs: List[Dict[str, str]] = []
        start_index = 0

        while len(all_jobs) < max_jobs:
            current_criteria = {**search_criteria, 'start': start_index}
            query_params = self.build_search_query(current_criteria)
            html_content = await self.client.get_job_list(query_params)

            if not html_content:
                logger.info("No more job listings found. Ending scrape.")
                break

            soup = BeautifulSoup(html_content, "html.parser")
            job_cards = soup.find_all("div", class_="base-search-card")

            if not job_cards:
                logger.info("Reached the end of job listings.")
                break

            for card in job_cards:
                urn = card.get("data-entity-urn", "")
                title_el = card.find("h3", class_="base-search-card__title")
                company_el = card.find("h4", class_="base-search-card__subtitle")

                if urn and title_el and company_el:
                    all_jobs.append({
                        "job_id": urn.split(":")[-1],
                        "title": clean_text(title_el.get_text()),
                        "company": clean_text(company_el.get_text())
                    })

            start_index += len(job_cards)

        logger.info("Found %d total jobs. Now fetching details...", len(all_jobs))

        target_jobs = all_jobs[:max_jobs]
        detail_tasks = [self._get_and_parse_details(job) for job in target_jobs]
        details_results = await asyncio.gather(*detail_tasks)

        details_map = {res["job_id"]: res for res in details_results if "job_id" in res}

        final_results: List[Dict[str, Any]] = []
        for job in target_jobs:
            details = details_map.get(job["job_id"])
            if details:
                job.update(details)
                final_results.append(job)

        await self.client.close()
        return final_results


async def run_scraper(
        search_criteria: Dict[str, Any],
        max_jobs: int = 25,
        concurrency_limit: int = 5,
        delay: Dict[str, int] | None = None
) -> List[Dict[str, Any]]:
    """
    A convenient wrapper to initialize and run the LinkedIn scraper.
    """
    if delay is None:
        delay = {"min_val": 1, "max_val": 3}

    logger.info("Starting scraper for keywords: '%s'", search_criteria.get('keywords', 'N/A'))
    random_delay = random.randint(delay["min_val"], delay["max_val"])
    scraper = LinkedInScraper(concurrency_limit, random_delay)
    return await scraper.run(search_criteria=search_criteria, max_jobs=max_jobs)