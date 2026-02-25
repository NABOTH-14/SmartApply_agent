# worker.py
from scraper import scrape_all_jobs  # Import your main scraping function
import json
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        logger.info("Starting job scraping...")
        
        # Scrape jobs from both sources
        jobs = scrape_all_jobs({'gozambia': 3, 'greatzambiajobs': 5})
        
        # Save results to a JSON file (optional, useful for logs/debug)
        with open("jobs.json", "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Scraping done. Total unique jobs fetched: {len(jobs)}")
        
    except Exception as e:
        logger.error(f"Scraper failed: {str(e)}")