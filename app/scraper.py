import requests
from bs4 import BeautifulSoup
import time
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseJobScraper:
    """Base class for job scrapers"""
    def __init__(self, delay: float = 1.0):
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def fetch_jobs(self, max_pages: int = 3) -> List[Dict]:
        """To be implemented by child classes"""
        raise NotImplementedError

class GoZambiaScraper(BaseJobScraper):
    """Scraper for GoZambia.com job listings"""
    
    BASE_URL = "https://www.gozambia.com"
    JOBS_URL = "https://www.gozambia.com/jobs"
    
    def fetch_jobs(self, max_pages: int = 3) -> List[Dict]:
        """Fetch job listings from multiple pages"""
        all_jobs = []
        
        for page in range(1, max_pages + 1):
            try:
                logger.info(f"GoZambia: Fetching page {page}...")
                jobs = self._fetch_page(page)
                all_jobs.extend(jobs)
                
                if len(jobs) < 20:
                    break
                    
                time.sleep(self.delay)
                
            except Exception as e:
                logger.error(f"GoZambia error on page {page}: {str(e)}")
                continue
        
        return all_jobs
    
    def _fetch_page(self, page: int) -> List[Dict]:
        """Fetch a single page of job listings"""
        url = f"{self.JOBS_URL}?page={page}"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        job_cards = soup.find_all('div', class_='job-listing')
        
        jobs = []
        for card in job_cards:
            try:
                job = self._parse_job_card(card)
                if job:
                    jobs.append(job)
            except Exception as e:
                logger.error(f"Error parsing GoZambia job card: {str(e)}")
                continue
        
        return jobs
    
    def _parse_job_card(self, card) -> Optional[Dict]:
        """Parse individual job card"""
        try:
            title_elem = card.find('h3', class_='job-title')
            if not title_elem:
                return None
            
            link = title_elem.find('a')
            title = link.text.strip() if link else title_elem.text.strip()
            relative_url = link.get('href') if link else None
            full_url = urljoin(self.BASE_URL, relative_url) if relative_url else None
            
            company_elem = card.find('div', class_='job-company')
            company = company_elem.text.strip() if company_elem else "Unknown"
            
            location_elem = card.find('div', class_='job-location')
            location = location_elem.text.strip() if location_elem else None
            
            desc_elem = card.find('div', class_='job-description')
            description = desc_elem.text.strip() if desc_elem else ""
            
            # Fetch full description if URL available
            if full_url:
                full_description = self._fetch_job_description(full_url)
                if full_description:
                    description = full_description
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description,
                'url': full_url,
                'source': 'gozambia'
            }
            
        except Exception as e:
            logger.error(f"Error in GoZambia _parse_job_card: {str(e)}")
            return None
    
    def _fetch_job_description(self, url: str) -> Optional[str]:
        """Fetch full job description from job detail page"""
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            desc_elem = soup.find('div', class_='job-description-full')
            
            if desc_elem:
                return desc_elem.text.strip()
            
            content = soup.find('div', class_='content')
            if content:
                return content.text.strip()
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching GoZambia job description from {url}: {str(e)}")
            return None

class GreatZambiaJobsScraper(BaseJobScraper):
    """Scraper for GreatZambiaJobs.com"""
    
    BASE_URL = "https://www.greatzambiajobs.com"
    JOBS_URL = "https://www.greatzambiajobs.com/jobs/"
    
    def fetch_jobs(self, max_pages: int = 5) -> List[Dict]:
        """Fetch job listings from GreatZambiaJobs"""
        all_jobs = []
        
        # The site shows many jobs on a single page with pagination
        # We'll scrape the main page and follow pagination links
        try:
            # Start with first page
            jobs = self._fetch_page(self.JOBS_URL)
            all_jobs.extend(jobs)
            
            # Try to find and follow pagination
            next_page = self._get_next_page(self.JOBS_URL)
            page_count = 1
            
            while next_page and page_count < max_pages:
                time.sleep(self.delay)
                logger.info(f"GreatZambiaJobs: Fetching page {page_count + 1}...")
                
                jobs = self._fetch_page(next_page)
                all_jobs.extend(jobs)
                
                next_page = self._get_next_page(next_page)
                page_count += 1
                
        except Exception as e:
            logger.error(f"GreatZambiaJobs scraping error: {str(e)}")
        
        logger.info(f"GreatZambiaJobs: Total jobs fetched: {len(all_jobs)}")
        return all_jobs
    
    def _fetch_page(self, url: str) -> List[Dict]:
        """Fetch a single page of job listings"""
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        jobs = []
        
        # Find job listings - they appear in various formats
        # Method 1: Look for job cards/containers
        job_containers = soup.find_all(['div', 'tr'], class_=re.compile(r'job|listing|row|card', re.I))
        
        if not job_containers:
            # Method 2: Look for links that might be job listings
            job_links = soup.find_all('a', href=re.compile(r'/job/|/jobs/|/position/', re.I))
            if job_links:
                for link in job_links[:50]:  # Limit to avoid duplicates
                    job = self._parse_job_from_link(link, url)
                    if job and job not in jobs:
                        jobs.append(job)
        
        for container in job_containers[:30]:  # Limit to first 30 per page
            try:
                job = self._parse_job_container(container)
                if job and job not in jobs:
                    jobs.append(job)
            except Exception as e:
                continue
        
        # If we still don't have jobs, try a more general approach
        if not jobs:
            jobs = self._generic_job_extraction(soup, url)
        
        return jobs
    
    def _parse_job_container(self, container) -> Optional[Dict]:
        """Parse a potential job container element"""
        try:
            # Try to find title and link
            title_elem = container.find(['h2', 'h3', 'h4', 'a'], 
                                       string=re.compile(r'.*', re.I),
                                       recursive=True)
            
            if not title_elem:
                return None
            
            # Get title text
            title = title_elem.get_text().strip()
            if len(title) < 3 or "apply" in title.lower():
                return None
            
            # Get URL
            url = None
            if title_elem.name == 'a':
                url = title_elem.get('href')
            else:
                link = container.find('a', href=True)
                if link:
                    url = link.get('href')
            
            if url and not url.startswith('http'):
                url = urljoin(self.BASE_URL, url)
            
            # Try to find company
            company = "Unknown"
            company_elem = container.find(string=re.compile(r'company|employer|by', re.I))
            if company_elem:
                company_text = company_elem.parent.get_text() if company_elem.parent else ""
                company_match = re.search(r'(?:company|employer|by)[:\s]+([A-Za-z\s&]+)', company_text, re.I)
                if company_match:
                    company = company_match.group(1).strip()
            
            # Try to find location
            location = None
            location_elem = container.find(string=re.compile(r'location|based|place|lusaka|kitwe|ndola|copperbelt', re.I))
            if location_elem:
                location_text = location_elem.parent.get_text() if location_elem.parent else ""
                location_match = re.search(r'(?:location|based|place)[:\s]+([A-Za-z\s,]+)', location_text, re.I)
                if location_match:
                    location = location_match.group(1).strip()
                else:
                    # Just extract city names
                    cities = re.findall(r'(Lusaka|Kitwe|Ndola|Copperbelt|Livingstone|Kabwe)', location_text, re.I)
                    if cities:
                        location = ', '.join(set(cities))
            
            # Get description
            description = container.get_text(separator=' ', strip=True)
            description = re.sub(r'\s+', ' ', description)
            
            # Fetch full description if we have a URL
            if url and '/job/' in url:
                full_desc = self._fetch_job_description(url)
                if full_desc:
                    description = full_desc
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': description[:5000],  # Limit length
                'url': url,
                'source': 'greatzambiajobs'
            }
            
        except Exception as e:
            logger.error(f"Error parsing GreatZambiaJobs container: {str(e)}")
            return None
    
    def _parse_job_from_link(self, link, base_url) -> Optional[Dict]:
        """Parse job from a link element"""
        try:
            href = link.get('href', '')
            if not href or not any(x in href.lower() for x in ['/job/', '/jobs/', '/position/']):
                return None
            
            title = link.get_text().strip()
            if len(title) < 5 or any(x in title.lower() for x in ['apply', 'click', 'more']):
                return None
            
            url = urljoin(self.BASE_URL, href)
            
            # Try to get context from parent
            parent = link.parent
            context = parent.get_text() if parent else ""
            
            # Extract potential company and location
            company = "Unknown"
            location = None
            
            company_match = re.search(r'(?:at|with|company)[:\s]+([A-Za-z\s&]+)', context, re.I)
            if company_match:
                company = company_match.group(1).strip()
            
            location_match = re.search(r'(?:in|at)[:\s]+(Lusaka|Kitwe|Ndola|Copperbelt|Zambia)', context, re.I)
            if location_match:
                location = location_match.group(1)
            
            return {
                'title': title,
                'company': company,
                'location': location,
                'description': context[:2000],
                'url': url,
                'source': 'greatzambiajobs'
            }
            
        except Exception as e:
            logger.error(f"Error parsing GreatZambiaJobs link: {str(e)}")
            return None
    
    def _generic_job_extraction(self, soup, url) -> List[Dict]:
        """Generic fallback method to extract job listings"""
        jobs = []
        
        # Look for any text that might be job titles
        text = soup.get_text()
        
        # Find patterns that look like job titles (often followed by company names)
        job_patterns = [
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:at|with|-)\s+([A-Za-z\s&]+)',
            r'(?:Job Title|Position)[:\s]+([^\\n]+)',
            r'([^\\n]+)\s+(?:Full-time|Part-time|Contract)'
        ]
        
        for pattern in job_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:20]:  # Limit to 20 matches
                if isinstance(match, tuple):
                    title = match[0]
                    company = match[1] if len(match) > 1 else "Unknown"
                else:
                    title = match
                    company = "Unknown"
                
                if len(title) > 5 and "apply" not in title.lower():
                    jobs.append({
                        'title': title.strip(),
                        'company': company.strip(),
                        'location': 'Zambia',
                        'description': f"Position: {title} at {company}",
                        'url': url,
                        'source': 'greatzambiajobs'
                    })
        
        return jobs
    
    def _get_next_page(self, current_url: str) -> Optional[str]:
        """Get next page URL from pagination links"""
        try:
            response = self.session.get(current_url, timeout=5)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for next page link
            next_links = soup.find_all('a', string=re.compile(r'next|›|»|>', re.I))
            if next_links:
                href = next_links[0].get('href')
                if href:
                    return urljoin(self.BASE_URL, href)
            
            # Look for pagination with page numbers
            pagination = soup.find(['div', 'ul'], class_=re.compile(r'pagination|pages|pager', re.I))
            if pagination:
                current_page = None
                # Extract current page number from URL or text
                page_match = re.search(r'[?&]page=(\d+)', current_url)
                if page_match:
                    current_page = int(page_match.group(1))
                else:
                    # Try to find current page from text
                    current_span = pagination.find('span', class_=re.compile(r'current|active', re.I))
                    if current_span:
                        try:
                            current_page = int(current_span.text.strip())
                        except:
                            pass
                
                if current_page:
                    # Look for link to next page
                    next_page_link = pagination.find('a', string=str(current_page + 1))
                    if next_page_link:
                        href = next_page_link.get('href')
                        if href:
                            return urljoin(self.BASE_URL, href)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next page: {str(e)}")
            return None
    
    def _fetch_job_description(self, url: str) -> Optional[str]:
        """Fetch full job description from job detail page"""
        try:
            time.sleep(self.delay)
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for description container
            desc_containers = soup.find_all(['div', 'section'], 
                                           class_=re.compile(r'description|details|content|job-body', re.I))
            
            for container in desc_containers:
                text = container.get_text(separator=' ', strip=True)
                if len(text) > 200:  # Likely the description
                    return text[:8000]  # Limit length
            
            # Fallback to main content
            main_content = soup.find('main') or soup.find('article') or soup.find('body')
            if main_content:
                return main_content.get_text(separator=' ', strip=True)[:8000]
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching GreatZambiaJobs description from {url}: {str(e)}")
            return None

def scrape_all_jobs(max_pages_per_source: dict = None) -> List[Dict]:
    """
    Main function to scrape jobs from all sources
    
    Args:
        max_pages_per_source: Dict with source names and max pages to scrape
                             e.g., {'gozambia': 3, 'greatzambiajobs': 5}
    """
    if max_pages_per_source is None:
        max_pages_per_source = {
            'gozambia': 3,
            'greatzambiajobs': 5
        }
    
    all_jobs = []
    
    # Scrape from GoZambia
    try:
        gozambia_scraper = GoZambiaScraper()
        gozambia_jobs = gozambia_scraper.fetch_jobs(max_pages_per_source.get('gozambia', 3))
        all_jobs.extend(gozambia_jobs)
        logger.info(f"Scraped {len(gozambia_jobs)} jobs from GoZambia")
    except Exception as e:
        logger.error(f"Failed to scrape GoZambia: {str(e)}")
    
    # Scrape from GreatZambiaJobs
    try:
        greatzambia_scraper = GreatZambiaJobsScraper()
        greatzambia_jobs = greatzambia_scraper.fetch_jobs(max_pages_per_source.get('greatzambiajobs', 5))
        all_jobs.extend(greatzambia_jobs)
        logger.info(f"Scraped {len(greatzambia_jobs)} jobs from GreatZambiaJobs")
    except Exception as e:
        logger.error(f"Failed to scrape GreatZambiaJobs: {str(e)}")
    
    # Remove duplicates by URL (if URLs exist)
    unique_jobs = {}
    for job in all_jobs:
        if job.get('url'):
            unique_jobs[job['url']] = job
        else:
            # Use title+company as key if no URL
            key = f"{job['title']}_{job['company']}"
            unique_jobs[key] = job
    
    final_jobs = list(unique_jobs.values())
    logger.info(f"Total unique jobs scraped: {len(final_jobs)}")
    
    return final_jobs

# For backward compatibility
def scrape_gozambia_jobs(max_pages: int = 3) -> List[Dict]:
    """Legacy function for GoZambia only"""
    scraper = GoZambiaScraper()
    return scraper.fetch_jobs(max_pages)