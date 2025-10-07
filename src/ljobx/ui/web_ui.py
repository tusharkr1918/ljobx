import argparse
import asyncio
import csv
import io
import json
import logging
import math
import multiprocessing
import sys
import time
from queue import Empty

import pandas as pd
import streamlit as st
from streamlit_local_storage import LocalStorage

from ljobx.api.proxy.proxy_manager import ProxyManager
from ljobx.core.config import config
from ljobx.core.config_loader import ConfigLoader
from ljobx.core.scraper import run_scraper
from ljobx.utils.const import FILTERS
from ljobx.utils.logger import QueueLogHandler, setup_root_logger

st.set_page_config(page_title="ljobx | LinkedIn Job Extractor", page_icon="🔎", layout="centered")
st.markdown("""
    <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2.3rem;
        }
        .stElementContainer hr {
            display: none !important;
        }
        div.stCode {
            max-height: 300px;
            overflow-y: auto;
        }
        .st-emotion-cache-1w723zb {
            max-width: 936px
        }
    </style>
    """, unsafe_allow_html=True)


# --- Helper functions integrated from existing cli.py ---

def _flatten_dict(d: dict, parent_key: str = '', sep: str = '_') -> dict:
    """Flattens a nested dictionary."""
    items = {}
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = str(v).strip().replace("\n", "; ") if v is not None else ""
    return items

def generate_csv_data(results: list) -> bytes:
    """
    Generates a CSV byte string from results with ordered and flattened columns,
    ready for st.download_button.
    """
    if not results:
        return b""

    flat_results = [_flatten_dict(res) for res in results]
    all_keys = set(key for res in flat_results for key in res.keys())
    all_keys.discard('recruiter')

    preferred_order = [
        'job_id', 'title', 'company', 'location', 'posted_date', 'applicants',
        'salary_range', 'apply_url', 'apply_is_easy_apply', 'recruiter_name',
        'recruiter_title', 'recruiter_profile_url', 'description'
    ]

    ordered_keys = [key for key in preferred_order if key in all_keys]
    remaining_keys = sorted(list(all_keys - set(ordered_keys)))
    final_ordered_keys = ordered_keys + remaining_keys

    overrides = {
        "apply_is_easy_apply": "EASY_APPLY",
        "recruiter_profile_url": "RECRUITER_PROFILE",
    }
    final_headers = [overrides.get(h, h.upper()) for h in final_ordered_keys]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(final_headers)
    for res in flat_results:
        row = [res.get(key, "") for key in final_ordered_keys]
        writer.writerow(row)

    return output.getvalue().encode("utf-8-sig")

def run_scraper_in_process(results_q, log_q, progress_q, _search_criteria, _scraper_settings, _log_level):
    """Target function for the scraper process."""

    # Configure the logger for THIS SUBPROCESS.
    # It cannot inherit the configuration from the main process so ya.
    log_level = logging.getLevelNamesMapping()[_log_level.upper()]
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []

    formatter = logging.Formatter(
        '[%(asctime)s] - %(levelname)s [%(threadName)s] - %(message)s (%(filename)s:%(lineno)d - %(name)s)',
        '%Y-%m-%d %H:%M:%S'
    )

    queue_handler = QueueLogHandler(log_q)
    queue_handler.setFormatter(formatter)
    root_logger.addHandler(queue_handler)

    file_handler = logging.handlers.RotatingFileHandler( # pyright: ignore[reportAttributeAccessIssue]
        filename=config.LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        logging.info("Scraper process started...")
        results, stats = loop.run_until_complete(
            run_scraper(search_criteria=_search_criteria, progress_queue=progress_q, **_scraper_settings)
        )
        results_q.put({'data': results, 'stats': stats})
        logging.info("Scraper process finished.")
    except Exception as e:
        logging.error(f"Scraper process failed: {e}", exc_info=True)
        results_q.put(e)
    finally:
        loop.close()

def handle_proxy_upload():
    """Reads the uploaded proxy file, updates the config, and sets relevant flags."""
    if st.session_state.proxy_uploader is not None:
        st.session_state.proxy_config_content = st.session_state.proxy_uploader.read().decode("utf-8")
        st.session_state.just_uploaded_proxy = True
        st.session_state.using_default_proxy = False


# noinspection PyBroadException
def main():
    # --- MOVED LOGGER SETUP TO THE TOP ---
    # This ensures the logger is configured before any other code runs.
    setup_root_logger(logging.INFO)

    # --- Argument Parsing for Basic Mode Overrides ---
    parser = argparse.ArgumentParser()
    parser.add_argument("--basic", action="store_true")
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--delay", type=int, nargs=2, default=None)
    parser.add_argument("--log-level", type=str, default=None)
    parser.add_argument("--proxy-config", type=str, default=None)

    args, _ = parser.parse_known_args(sys.argv[1:])
    basic_mode = args.basic
    local_storage = LocalStorage()

    # --- Initialize Session State ---
    if 'app_initialized' not in st.session_state:
        initial_state = local_storage.getItem("form_inputs")
        initial_state = json.loads(initial_state) if isinstance(initial_state, str) else initial_state or {}

        # --- Proxy Configuration Loading ---
        proxy_from_storage = initial_state.get("proxy_config_content")
        using_default = False
        final_proxy_content = proxy_from_storage

        default_content_on_disk = None
        logging.info(f"Checking for default proxy config at: {config.DEFAULT_PROXY_CONFIG_PATH}")
        if config.DEFAULT_PROXY_CONFIG_PATH.exists():
            try:
                default_content_on_disk = config.DEFAULT_PROXY_CONFIG_PATH.read_text()
                logging.info("Default proxy configuration found at the system path.")
            except Exception as e:
                logging.error(f"Found default proxy config but failed to read it: {e}")
                pass
        else:
            logging.info("No default proxy configuration found at the system path.")

        if proxy_from_storage:
            if proxy_from_storage == default_content_on_disk:
                using_default = True
        elif default_content_on_disk:
            final_proxy_content = default_content_on_disk
            using_default = True

        st.session_state.proxy_config_content = final_proxy_content
        st.session_state.using_default_proxy = using_default

        # --- Set Default Values ---
        defaults = {
            "keywords": "", "location": "", "max_jobs": 5,
            "concurrency": 2, "delay_range": (3.0, 8.0), "log_level": "INFO",
            "date_posted": "Any time", "job_type": [],
            "experience_level": [], "remote": "On-site",
            "exact_search": True,
        }

        for key, value in defaults.items():
            st.session_state[key] = initial_state.get(key, value)

        # --- Initialize remaining state variables ---
        st.session_state.searching = False
        st.session_state.scraper_process = None
        st.session_state.log_lines = []
        st.session_state.results = None
        st.session_state.status_message = None
        st.session_state.start_job = False
        st.session_state.just_uploaded_proxy = False
        st.session_state.app_initialized = True
        st.session_state.progress = 0
        st.session_state.progress_phase = 0
        st.session_state.total_jobs_found = 0
        st.session_state.pages_processed = 0
        st.session_state.jobs_processed = 0

    # --- Overrides for Basic Mode ---
    if basic_mode:
        concurrency_to_use = 2
        delay_to_use = (3.0, 8.0)
        log_level_to_use = "INFO"

        if config.DEFAULT_PROXY_CONFIG_PATH.exists() or args.proxy_config:
            concurrency_to_use = 5
            delay_to_use = (2.0, 4.0)

        st.session_state.concurrency = args.concurrency if args.concurrency is not None else concurrency_to_use
        st.session_state.delay_range = (float(args.delay[0]), float(args.delay[1])) if args.delay is not None else delay_to_use
        st.session_state.log_level = args.log_level if args.log_level is not None else log_level_to_use

        if args.proxy_config:
            st.session_state.proxy_config_override = args.proxy_config
    
    # Update the logger level if it was changed by the user in the UI
    log_level_from_state = st.session_state.get("log_level", "INFO")
    logging.getLogger().setLevel(log_level_from_state.upper())


    st.title("LinkedIn Job Extractor")
    st.markdown("An interactive UI for the `ljobx` scraping tool. Enter your search criteria and start the search.")

    with st.container(border=True):
        st.subheader("🎯 Search Criteria")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("**Keywords**", key="keywords", placeholder="e.g., Senior Python Developer")
            st.checkbox("Exact Search (searches for exact keywords)", key="exact_search")
        with col2:
            st.text_input("**Location** (city, state, country)", key="location", placeholder="e.g., Noida, India or Remote")

        st.subheader("📊 Filters")
        f1, f2 = st.columns(2)
        with f1:
            date_posted_options = list(FILTERS["date_posted"]["options"].keys())
            st.selectbox("Date Posted", options=date_posted_options, key="date_posted")
            st.multiselect("Job Type", options=FILTERS["job_type"]["options"].keys(), key="job_type")
        with f2:
            st.multiselect("Experience Level", options=FILTERS["experience_level"]["options"].keys(), key="experience_level")
            remote_options = list(FILTERS["remote"]["options"].keys())
            st.selectbox("Remote Options", options=remote_options, key="remote")

        st.subheader("⚙️ Scraper Settings")
        st.number_input("**Max Jobs to Scrape**", min_value=1, max_value=1000, key="max_jobs")

        if not basic_mode:
            with st.expander("🛠️ Advanced Settings"):
                sc1, sc2 = st.columns(2)
                with sc1:
                    st.slider("**Concurrency**", min_value=1, max_value=10, key="concurrency", help="Number of parallel requests...")
                    st.selectbox("Log Level", options=["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"], key="log_level")
                with sc2:
                    st.slider("**Delay Range (s)**", 0.0, 20.0, key="delay_range", help="The random delay between requests...")

                st.markdown("---")
                st.subheader("🔌 Proxy Configuration")
                if st.session_state.proxy_config_content:
                    if st.session_state.get('using_default_proxy'):
                        st.success("✅ Using the system's default proxy configuration.")
                    else:
                        st.info("ℹ️ Using a user-uploaded proxy configuration.")
                    if not st.session_state.get('using_default_proxy'):
                        if st.button("Restore to default proxy settings"):
                            try:
                                stored_settings_str = local_storage.getItem("form_inputs")
                                stored_settings = json.loads(stored_settings_str) if stored_settings_str else {}
                                if "proxy_config_content" in stored_settings:
                                    del stored_settings["proxy_config_content"]
                                    local_storage.setItem("form_inputs", json.dumps(stored_settings))
                            except Exception as e:
                                st.error(f"Could not update local storage: {e}")
                            default_content_on_disk = None
                            if config.DEFAULT_PROXY_CONFIG_PATH.exists():
                                try:
                                    default_content_on_disk = config.DEFAULT_PROXY_CONFIG_PATH.read_text()
                                except Exception:
                                    pass
                            st.session_state.proxy_config_content = default_content_on_disk
                            st.session_state.using_default_proxy = True if default_content_on_disk else False
                            st.rerun()
                st.file_uploader(
                    "**Upload a new Proxy Configuration File**",
                    type=['yml', 'yaml'],
                    key="proxy_uploader",
                    on_change=handle_proxy_upload
                )

    b1, b2 = st.columns(2)
    with b1:
        start_search = st.button("🟢 Start Search", disabled=st.session_state.searching, use_container_width=True)
    with b2:
        stop_search = st.button("🔴 Stop Search", disabled=not st.session_state.searching, use_container_width=True)

    st.markdown("---")

    progress_placeholder = st.empty()
    log_placeholder = st.empty()
    results_placeholder = st.empty()
    status_placeholder = st.empty()

    if st.session_state.searching:
        progress_text = "Initializing..."
        if st.session_state.progress_phase == 1:
            total_pages = math.ceil(st.session_state.max_jobs / 10)
            progress_text = f"Phase 2/3: Searching for jobs... (Page {st.session_state.pages_processed}/{total_pages})"
        elif st.session_state.progress_phase == 2:
            progress_text = f"Phase 3/3: Scraping job details... ({st.session_state.jobs_processed}/{st.session_state.total_jobs_found})"
        progress_placeholder.progress(st.session_state.progress / 100, progress_text)

    if st.session_state.status_message:
        msg_type, msg_text = st.session_state.status_message
        if msg_type == "success": status_placeholder.success(msg_text)
        elif msg_type == "warning": status_placeholder.warning(msg_text)
        else: status_placeholder.error(msg_text)

    # --- Displaying results ---
    if st.session_state.results is not None and not st.session_state.results.empty:
        results_df = st.session_state.results
        with results_placeholder.container():
            st.subheader("📄 Results")
            results_list_for_display = results_df.to_dict(orient='records')
            flat_results = [_flatten_dict(res) for res in results_list_for_display]
            if flat_results:
                all_keys = set(key for res in flat_results for key in res.keys())
                all_keys.discard('recruiter')
                preferred_order = [
                    'job_id', 'title', 'company', 'location', 'posted_date', 'applicants',
                    'salary_range', 'apply_url', 'apply_is_easy_apply', 'recruiter_name',
                    'recruiter_title', 'recruiter_profile_url', 'description'
                ]
                ordered_keys = [key for key in preferred_order if key in all_keys]
                remaining_keys = sorted(list(all_keys - set(ordered_keys)))
                final_ordered_keys = ordered_keys + remaining_keys
                display_df = pd.DataFrame(flat_results, columns=final_ordered_keys)
                overrides = { "apply_is_easy_apply": "EASY_APPLY", "recruiter_profile_url": "RECRUITER_PROFILE", }
                display_df = display_df.rename(columns=overrides)
                display_df.columns = [h.upper() for h in display_df.columns]

                st.dataframe(
                    display_df,
                    column_config={
                        "APPLY_URL": st.column_config.LinkColumn("Apply Link"),
                        "RECRUITER_PROFILE": st.column_config.LinkColumn("Recruiter Profile")
                    }
                )
            else:
                st.dataframe(results_df)

            st.markdown("---")
            if basic_mode:
                results_list = results_df.to_dict(orient='records')
                ts = time.strftime("%Y%m%d_%H%M%S")
                file_name_base = st.session_state.keywords.replace(' ', '_').lower()
                csv_data = generate_csv_data(results_list)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_data,
                    file_name=f"{file_name_base}_{ts}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                dl1, dl2 = st.columns(2)
                results_list = results_df.to_dict(orient='records')
                ts = time.strftime("%Y%m%d_%H%M%S")
                file_name_base = st.session_state.keywords.replace(' ', '_').lower()
                with dl1:
                    csv_data = generate_csv_data(results_list)
                    st.download_button(label="📥 Download as CSV", data=csv_data, file_name=f"{file_name_base}_{ts}.csv", mime="text/csv", use_container_width=True)
                with dl2:
                    json_data = json.dumps(results_list, indent=2, ensure_ascii=False).encode('utf-8')
                    st.download_button(label="📥 Download as JSON", data=json_data, file_name=f"{file_name_base}_{ts}.json", mime="application/json", use_container_width=True)


    if not basic_mode and st.session_state.log_lines:
        with log_placeholder.container():
            st.subheader("📜 Live Log")
            st.code("\n".join(st.session_state.log_lines[-200:]), language="log")

    if start_search:
        if not st.session_state.keywords or not st.session_state.location:
            st.error("Please provide both Keywords and Location.")
        else:
            st.session_state.log_lines = []
            st.session_state.results = None
            st.session_state.status_message = None
            st.session_state.searching = True
            st.session_state.start_job = True
            st.rerun()

    if stop_search:
        if st.session_state.scraper_process:
            st.session_state.scraper_process.terminate()
            st.warning("✅ Search stopped by user.")
            st.session_state.searching = False
            st.session_state.scraper_process = None
            st.session_state.queues = None
            st.rerun()

    if st.session_state.start_job:
        manager = multiprocessing.Manager()
        results_queue = manager.Queue()
        log_queue = manager.Queue()
        progress_queue = manager.Queue()
        st.session_state.queues = (results_queue, log_queue, progress_queue)

        st.session_state.progress = 0
        st.session_state.progress_phase = 0
        st.session_state.total_jobs_found = 0
        st.session_state.pages_processed = 0
        st.session_state.jobs_processed = 0

        log_level = st.session_state.log_level
        concurrency = st.session_state.concurrency
        delay_range = st.session_state.delay_range
        
        proxies = []
        proxy_config_to_use = st.session_state.get("proxy_config_override") or st.session_state.proxy_config_content

        if proxy_config_to_use:
            try:
                logging.info("Loading proxy configuration...")
                config_data = ConfigLoader.load(proxy_config_to_use)
                proxies = asyncio.run(ProxyManager.get_proxies_from_config(config_data, validate=config_data.get("validate_proxies", True)))
                if not proxies:
                    logging.warning("No working proxies found. The scraper will run without proxies.")
            except (ValueError, FileNotFoundError) as e:
                logging.error(f"Failed to load proxies: {e}")
                st.error(f"Failed to load proxies: {e}")
                st.session_state.searching = False
                st.rerun()

        # --- Check for basic mode with no proxies ---
        if basic_mode and len(proxies) <= 1:
            logging.warning("Basic mode with no proxies detected. Overriding settings for stability.")
            concurrency = 2
            delay_range = (3.0, 8.0)
            st.session_state.status_message = (
                "warning",
                "Running in safe mode for stability. No proxies were found or loaded. \nIf searches feel slow, please contact the DevOps team for a performance boost."
            )

        keywords_to_search = st.session_state.keywords
        if st.session_state.exact_search:
            keywords_to_search = f'"{keywords_to_search}"'

        search_criteria = {
            'keywords': keywords_to_search, 'location': st.session_state.location,
            'date_posted': st.session_state.date_posted if st.session_state.date_posted != "Any time" else None,
            'job_type': st.session_state.job_type, 'experience_level': st.session_state.experience_level,
            'remote': st.session_state.remote if st.session_state.remote != "On-site" else None,
        }

        delay_min, delay_max = delay_range
        scraper_settings = {
            "max_jobs": st.session_state.max_jobs, "concurrency_limit": concurrency,
            "delay": {"min_val": int(delay_min), "max_val": int(delay_max)}, "proxies": proxies
        }

        p = multiprocessing.Process(target=run_scraper_in_process, args=(results_queue, log_queue, progress_queue, search_criteria, scraper_settings, log_level))
        p.start()
        st.session_state.scraper_process = p
        st.session_state.start_job = False
        st.rerun()


    if st.session_state.searching:
        results_queue, log_queue, progress_queue = st.session_state.queues
        try:
            while True:
                log_line = log_queue.get_nowait()
                st.session_state.log_lines.append(log_line)
        except Empty:
            pass
        try:
            while True:
                progress_update = progress_queue.get_nowait()
                if progress_update == "INIT":
                    st.session_state.progress = 5
                    st.session_state.progress_phase = 1
                elif progress_update == "PAGE":
                    if st.session_state.progress_phase == 1:
                        st.session_state.pages_processed += 1
                        total_pages = math.ceil(st.session_state.max_jobs / 10)
                        if total_pages > 0:
                            progress_for_pages = (st.session_state.pages_processed / total_pages) * 25
                            st.session_state.progress = 5 + int(progress_for_pages)
                elif isinstance(progress_update, str) and progress_update.startswith("PAGE_END"):
                    st.session_state.total_jobs_found = int(progress_update.split(":")[1])
                    st.session_state.progress = 30
                    st.session_state.progress_phase = 2
                elif progress_update == "JOB":
                    if st.session_state.progress_phase == 2 and st.session_state.total_jobs_found > 0:
                        st.session_state.jobs_processed += 1
                        progress_for_jobs = (st.session_state.jobs_processed / st.session_state.total_jobs_found) * 70
                        st.session_state.progress = 30 + int(progress_for_jobs)
        except Empty:
            pass

        # --- Process completion check ---
        process = st.session_state.get('scraper_process')
        if process:
            if not process.is_alive():
                st.session_state.progress = 100
                progress_placeholder.progress(1.0, "Search complete!")
                try:
                    final_output = results_queue.get_nowait()
                    if isinstance(final_output, Exception):
                        st.session_state.status_message = ("error", f"An error occurred: {final_output}")
                        st.session_state.results = pd.DataFrame()

                    elif isinstance(final_output, dict):
                        results_data = final_output.get('data', [])
                        stats = final_output.get('stats', {'success': 0, 'failures': 0})
                        total_reqs = stats.get('success', 0) + stats.get('failures', 0)

                        if results_data:
                            st.session_state.status_message = ("success", f"✅ Search complete! Found {len(results_data)} jobs.")
                        else:
                            st.session_state.status_message = ("warning", "Search complete. No jobs found.")

                        if total_reqs > 0:
                            failure_rate = stats.get('failures', 0) / total_reqs
                            if failure_rate >= 0.4:
                                st.session_state.status_message = (
                                    "warning",
                                    "Search completed, but several connection errors occurred. The proxies may not be functioning properly. \nPlease consider contacting the DevOps team."
                                )
                        st.session_state.results = pd.DataFrame(results_data)

                    else:
                        st.session_state.status_message = ("warning", "Search complete. No jobs found.")
                        st.session_state.results = pd.DataFrame()

                except Empty:
                    st.session_state.status_message = ("warning", "Process finished unexpectedly with no results.")
                    st.session_state.results = pd.DataFrame()

                st.session_state.searching = False
                st.session_state.scraper_process = None
                st.session_state.queues = None
                st.rerun()
            else:
                time.sleep(0.5)
                st.rerun()
        else:
            if st.session_state.searching:
                st.session_state.searching = False
                st.rerun()

    keys_to_save = [
        "keywords", "location", "max_jobs", "date_posted", "job_type",
        "experience_level", "remote", "log_level", "exact_search"
    ]

    if not basic_mode:
        keys_to_save.extend(["concurrency", "delay_range", "proxy_config_content"])

    current_state = {
        key: st.session_state[key] for key in keys_to_save if key in st.session_state
    }
    local_storage.setItem("form_inputs", json.dumps(current_state))


if __name__ == '__main__':
    multiprocessing.set_start_method('spawn', force=True)
    multiprocessing.freeze_support()
    main()