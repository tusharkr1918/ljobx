import streamlit as st
import pandas as pd
import asyncio
import logging
import time
import multiprocessing
import psutil
import json
import io
import csv
from queue import Empty

from streamlit_local_storage import LocalStorage

from ljobx.core.scraper import run_scraper
from ljobx.utils.const import FILTERS
from ljobx.utils.logger import QueueLogHandler, configure_logging
from ljobx.core.config_loader import ConfigLoader
from ljobx.api.proxy.proxy_manager import ProxyManager

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

def run_scraper_in_process(results_q, log_q, _search_criteria, _scraper_settings, _log_level):
    """Target function for the scraper process."""
    configure_logging(_log_level.upper())
    root_logger = logging.getLogger()
    root_logger.handlers = []
    log_handler = QueueLogHandler(log_q)
    log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
    root_logger.addHandler(log_handler)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        logging.info("Scraper process started...")
        results = loop.run_until_complete(run_scraper(search_criteria=_search_criteria, **_scraper_settings))
        results_q.put(results)
        logging.info("Scraper process finished.")
    except Exception as e:
        logging.error(f"Scraper process failed: {e}", exc_info=True)
        results_q.put(e)
    finally:
        loop.close()

def handle_proxy_upload():
    """Reads the uploaded proxy file, updates the config, and sets a flag."""
    if st.session_state.proxy_uploader is not None:
        st.session_state.proxy_config_content = st.session_state.proxy_uploader.read().decode("utf-8")
        st.session_state.just_uploaded_proxy = True # Flag to hide the "Clear" button temporarily

def main():
    local_storage = LocalStorage()

    if 'app_initialized' not in st.session_state:
        initial_state = local_storage.getItem("form_inputs")
        initial_state = json.loads(initial_state) if isinstance(initial_state, str) else initial_state or {}

        defaults = {
            "keywords": "", "location": "", "max_jobs": 5, "concurrency": 2,
            "delay_range": (3.0, 8.0), "date_posted": "Any time", "job_type": [],
            "experience_level": [], "remote": "On-site", "proxy_config_content": None,
            "log_level": "INFO"
        }

        for key, value in defaults.items():
            st.session_state[key] = initial_state.get(key, value)

        st.session_state.searching = False
        st.session_state.pid = None
        st.session_state.log_lines = []
        st.session_state.results = None
        st.session_state.status_message = None
        st.session_state.start_job = False
        st.session_state.just_uploaded_proxy = False
        st.session_state.app_initialized = True

    st.title("LinkedIn Job Extractor")
    st.markdown("An interactive UI for the `ljobx` scraping tool. Enter your search criteria and start the search.")

    with st.container(border=True):
        st.subheader("🎯 Search Criteria")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("**Keywords**", key="keywords", placeholder="e.g., Senior Python Developer")
        with col2:
            st.text_input("**Location**", key="location", placeholder="e.g., Noida, India or Remote")

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

        with st.expander("🛠️ Advanced Settings"):
            sc1, sc2 = st.columns(2)
            with sc1:
                st.slider("**Concurrency**", min_value=1, max_value=10, key="concurrency", help="Number of parallel requests...")
                st.selectbox("Log Level", options=["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL"], key="log_level")
            with sc2:
                st.slider("**Delay Range (s)**", 0.0, 20.0, key="delay_range", help="The random delay between requests...")

            st.markdown("---")
            st.subheader("🔌 Proxy Configuration")

            # Determine if the "Clear" button should be visible
            show_clear_button = st.session_state.proxy_config_content and not st.session_state.get('just_uploaded_proxy', False)

            if st.session_state.proxy_config_content:
                st.info("A proxy configuration is currently loaded.")
                if show_clear_button:
                    if st.button("Clear loaded proxy configuration"):
                        st.session_state.proxy_config_content = None
                        st.rerun()

            # Reset the flag after its value has been used for this render cycle
            st.session_state.just_uploaded_proxy = False

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

    log_placeholder = st.empty()
    results_placeholder = st.empty()
    status_placeholder = st.empty()

    if st.session_state.status_message:
        msg_type, msg_text = st.session_state.status_message
        if msg_type == "success": status_placeholder.success(msg_text)
        elif msg_type == "warning": status_placeholder.warning(msg_text)
        else: status_placeholder.error(msg_text)

    if st.session_state.results is not None and not st.session_state.results.empty:
        results_df = st.session_state.results
        with results_placeholder.container():
            st.subheader("📄 Results")
            st.dataframe(results_df)

            st.markdown("---")
            dl1, dl2 = st.columns(2)

            results_list = results_df.to_dict(orient='records')
            ts = time.strftime("%Y%m%d_%H%M%S")
            file_name_base = st.session_state.keywords.replace(' ', '_').lower()

            with dl1:
                csv_data = generate_csv_data(results_list)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_data,
                    file_name=f"{file_name_base}_{ts}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with dl2:
                json_data = json.dumps(results_list, indent=2, ensure_ascii=False).encode('utf-8')
                st.download_button(
                    label="📥 Download as JSON",
                    data=json_data,
                    file_name=f"{file_name_base}_{ts}.json",
                    mime="application/json",
                    use_container_width=True
                )

    if st.session_state.log_lines:
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
        if st.session_state.pid:
            try:
                p = psutil.Process(st.session_state.pid)
                p.terminate()
                st.warning("✅ Search stopped by user.")
            except psutil.NoSuchProcess:
                st.info("Process was already finished.")
            st.session_state.searching = False
            st.session_state.pid = None
            st.session_state.queues = None
            st.rerun()

    if st.session_state.start_job:
        manager = multiprocessing.Manager()
        results_queue = manager.Queue()
        log_queue = manager.Queue()
        st.session_state.queues = (results_queue, log_queue)

        # Configure logging for the main UI process and add a handler
        # to capture logs in the UI.
        configure_logging(st.session_state.log_level)
        root_logger = logging.getLogger()
        ui_log_handler = QueueLogHandler(log_queue)
        ui_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"))
        root_logger.addHandler(ui_log_handler)

        proxies = []
        if st.session_state.proxy_config_content:
            try:
                # This will now be logged to the UI
                logging.info("Loading proxy configuration...")
                config_data = ConfigLoader.load(st.session_state.proxy_config_content)
                proxies = asyncio.run(ProxyManager.get_proxies_from_config(config_data, validate=config_data.get("validate_proxies", True)))
                if not proxies:
                    # This will also be logged to the UI
                    logging.warning("No working proxies found. The scraper will run without proxies.")
            except (ValueError, FileNotFoundError) as e:
                # And this error will be logged to the UI
                logging.error(f"Failed to load proxies: {e}")
                st.error(f"Failed to load proxies: {e}") # Also show a streamlit error
                st.session_state.searching = False
                st.rerun()

        # Remove the handler from the main process so it doesn't interfere
        # with the scraper's own logging.
        root_logger.removeHandler(ui_log_handler)

        search_criteria = {
            'keywords': st.session_state.keywords, 'location': st.session_state.location,
            'date_posted': st.session_state.date_posted if st.session_state.date_posted != "Any time" else None,
            'job_type': st.session_state.job_type, 'experience_level': st.session_state.experience_level,
            'remote': st.session_state.remote if st.session_state.remote != "On-site" else None,
        }
        delay_min, delay_max = st.session_state.delay_range
        scraper_settings = {
            "max_jobs": st.session_state.max_jobs, "concurrency_limit": st.session_state.concurrency,
            "delay": {"min_val": int(delay_min), "max_val": int(delay_max)}, "proxies": proxies
        }

        # This process will set up its OWN logging, as before.
        p = multiprocessing.Process(target=run_scraper_in_process, args=(results_queue, log_queue, search_criteria, scraper_settings, st.session_state.log_level))
        p.start()
        st.session_state.pid = p.pid
        st.session_state.start_job = False
        st.rerun()


    if st.session_state.searching:
        results_queue, log_queue = st.session_state.queues
        try:
            while True:
                log_line = log_queue.get_nowait()
                st.session_state.log_lines.append(log_line)
        except Empty:
            pass

        if st.session_state.pid:
            if not psutil.pid_exists(st.session_state.pid):
                try:
                    final_output = results_queue.get_nowait()
                    if isinstance(final_output, Exception):
                        st.session_state.status_message = ("error", f"An error occurred: {final_output}")
                        st.session_state.results = pd.DataFrame()
                    elif final_output:
                        st.session_state.status_message = ("success", f"✅ Search complete! Found {len(final_output)} jobs.")
                        st.session_state.results = pd.DataFrame(final_output)
                    else:
                        st.session_state.status_message = ("warning", "Search complete. No jobs found.")
                        st.session_state.results = pd.DataFrame()
                except Empty:
                    st.session_state.status_message = ("warning", "Process finished unexpectedly with no results.")
                    st.session_state.results = pd.DataFrame()
                st.session_state.searching = False
                st.session_state.pid = None
                st.session_state.queues = None
                st.rerun()
            else:
                time.sleep(1)
                st.rerun()
        else:
            time.sleep(1)
            st.rerun()

    current_state = {
        key: st.session_state[key] for key in [
            "keywords", "location", "max_jobs", "concurrency", "delay_range",
            "date_posted", "job_type", "experience_level", "remote",
            "proxy_config_content", "log_level"
        ] if key in st.session_state
    }
    local_storage.setItem("form_inputs", json.dumps(current_state))

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()