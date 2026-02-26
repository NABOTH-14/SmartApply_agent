import os
import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin
import re

# ===============================
# Configuration (Railway Ready)
# ===============================

SCRAPER_DELAY = float(os.getenv("SCRAPER_DELAY", 1.0))
GOZAMBIA_MAX_PAGES = int(os.getenv("GOZAMBIA_MAX_PAGES", 3))
GREATZAMBIA_MAX_PAGES = int(os.getenv("GREATZAMBIA_MAX_PAGES", 5))
MAX_DESCRIPTION_LENGTH = int(os.getenv("MAX_DESCRIPTION_LENGTH", 4000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


# ===============================
# Base Scraper
# ===============================

class BaseJobScraper:
    def __init__(self, delay: float = SCRAPER_DELAY):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0 Safari/537.36"
            )
        })

    def fetch_jobs(self, max_pages: int) -> List[Dict]:
        raise NotImplementedError

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text).strip()
        return text[:MAX_DESCRIPTION_LENGTH]


# ===============================
# GoZambia Scraper
# ===============================

class GoZambiaScraper(BaseJobScraper):

    BASE_URL = "https://www.gozambia.com"
    JOBS_URL = "https://www.gozambia.com/jobs"

    def fetch_jobs(self, max_pages: int = GOZAMBIA_MAX_PAGES) -> List[Dict]:
        all_jobs = []

        for page in range(1, max_pages + 1):
            try:
                logger.info(f"[GoZambia] Fetching page {page}")
                jobs = self._fetch_page(page)
                all_jobs.extend(jobs)

                if not jobs:
                    break

                time.sleep(self.delay)

            except Exception as e:
                logger.error(f"[GoZambia] Page {page} error: {e}")

        return all_jobs

    def _fetch_page(self, page: int) -> List[Dict]:
        url = f"{self.JOBS_URL}?page={page}"
        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        job_cards = soup.find_all("div", class_=re.compile("job", re.I))

        jobs = []

        for card in job_cards:
            job = self._parse_job_card(card)
            if job:
                jobs.append(job)

        return jobs

    def _parse_job_card(self, card) -> Optional[Dict]:
        try:
            title_elem = card.find(["h2", "h3", "a"])
            if not title_elem:
                return None

            title = self._clean_text(title_elem.get_text())
            link = title_elem.find("a") or title_elem
            relative_url = link.get("href")
            full_url = urljoin(self.BASE_URL, relative_url) if relative_url else None

            company_elem = card.find(string=re.compile("company|employer", re.I))
            company = self._clean_text(company_elem.parent.get_text()) if company_elem else "Unknown"

            location_elem = card.find(string=re.compile("lusaka|kitwe|ndola|zambia", re.I))
            location = self._clean_text(location_elem.parent.get_text()) if location_elem else None

            description = self._clean_text(card.get_text())

            if full_url:
                full_desc = self._fetch_job_description(full_url)
                if full_desc:
                    description = full_desc

            return {
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": full_url,
                "source": "gozambia"
            }

        except Exception as e:
            logger.debug(f"[GoZambia] Parse error: {e}")
            return None

    def _fetch_job_description(self, url: str) -> Optional[str]:
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            content = soup.find("div", class_=re.compile("description|content", re.I))
            if content:
                return self._clean_text(content.get_text())

            return None

        except Exception as e:
            logger.debug(f"[GoZambia] Detail fetch error: {e}")
            return None


# ===============================
# GreatZambiaJobs Scraper
# ===============================

class GreatZambiaJobsScraper(BaseJobScraper):

    BASE_URL = "https://www.greatzambiajobs.com"
    JOBS_URL = "https://www.greatzambiajobs.com/jobs/"

    def fetch_jobs(self, max_pages: int = GREATZAMBIA_MAX_PAGES) -> List[Dict]:
        all_jobs = []
        next_page = self.JOBS_URL
        page_count = 0

        while next_page and page_count < max_pages:
            try:
                logger.info(f"[GreatZambiaJobs] Fetching page {page_count + 1}")
                jobs = self._fetch_page(next_page)
                all_jobs.extend(jobs)

                next_page = self._get_next_page(next_page)
                page_count += 1

                time.sleep(self.delay)

            except Exception as e:
                logger.error(f"[GreatZambiaJobs] Error: {e}")
                break

        return all_jobs

    def _fetch_page(self, url: str) -> List[Dict]:
        response = self.session.get(url, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        jobs = []

        job_links = soup.find_all("a", href=re.compile(r"/job/|/jobs/", re.I))

        for link in job_links[:40]:
            title = self._clean_text(link.get_text())
            if len(title) < 4:
                continue

            job_url = urljoin(self.BASE_URL, link["href"])

            jobs.append({
                "title": title,
                "company": "Unknown",
                "location": "Zambia",
                "description": title,
                "url": job_url,
                "source": "greatzambiajobs"
            })

        return jobs

    def _get_next_page(self, current_url: str) -> Optional[str]:
        try:
            response = self.session.get(current_url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            next_link = soup.find("a", string=re.compile("next|›|»", re.I))
            if next_link and next_link.get("href"):
                return urljoin(self.BASE_URL, next_link["href"])

            return None

        except Exception:
            return None


# ===============================
# Master Function
# ===============================

def scrape_all_jobs(max_pages_per_source: dict = None) -> List[Dict]:

    if max_pages_per_source is None:
        max_pages_per_source = {
            "gozambia": GOZAMBIA_MAX_PAGES,
            "greatzambiajobs": GREATZAMBIA_MAX_PAGES
        }

    all_jobs = []

    try:
        gozambia = GoZambiaScraper()
        all_jobs.extend(gozambia.fetch_jobs(max_pages_per_source["gozambia"]))
    except Exception as e:
        logger.error(f"GoZambia failed: {e}")

    try:
        greatzambia = GreatZambiaJobsScraper()
        all_jobs.extend(greatzambia.fetch_jobs(max_pages_per_source["greatzambiajobs"]))
    except Exception as e:
        logger.error(f"GreatZambiaJobs failed: {e}")

    # Deduplicate by URL
    unique_jobs = {job["url"]: job for job in all_jobs if job.get("url")}

    logger.info(f"Total unique jobs scraped: {len(unique_jobs)}")

    return list(unique_jobs.values())