import os
import logging
import psycopg2
import numpy as np
from dotenv import load_dotenv
from scraper import scrape_all_jobs
from openai import OpenAI
from smtplib import SMTP
from email.message import EmailMessage

# =========================
# Load Environment
# =========================
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CV_FOLDER = os.getenv("CV_FOLDER", "cvs")
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", 0.75))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# =========================
# OpenAI Client (Optional)
# =========================
openai_client = None
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
    logger.info("OpenAI matching enabled.")
else:
    logger.warning("OPENAI_API_KEY not set. AI matching disabled.")


# =========================
# Database
# =========================
def connect_db():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id SERIAL PRIMARY KEY,
        title TEXT,
        company TEXT,
        location TEXT,
        description TEXT,
        url TEXT UNIQUE,
        source TEXT,
        matched_users TEXT,
        created_at TIMESTAMP DEFAULT NOW()
    )
    """)
    conn.commit()
    return conn, cursor


# =========================
# Email Sender
# =========================
def send_email(to_email, job_list):
    if not job_list or not EMAIL_USER or not EMAIL_PASS:
        return

    msg = EmailMessage()
    msg["Subject"] = f"SmartApply Job Matches ({len(job_list)})"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email

    content = "Here are your job matches:\n\n"
    for job in job_list:
        content += (
            f"{job['title']} at {job['company']} "
            f"({job.get('location', 'N/A')})\n"
            f"{job['url']}\n\n"
        )

    msg.set_content(content)

    try:
        with SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.error(f"Email failed for {to_email}: {e}")


# =========================
# CV Loader
# =========================
def load_cvs():
    cvs = {}
    if not os.path.exists(CV_FOLDER):
        logger.warning("CV folder not found.")
        return cvs

    for file in os.listdir(CV_FOLDER):
        if file.endswith(".txt"):
            email = file.replace(".txt", "")
            with open(os.path.join(CV_FOLDER, file), "r", encoding="utf-8") as f:
                cvs[email] = f.read()

    logger.info(f"Loaded {len(cvs)} CV(s)")
    return cvs


# =========================
# Embeddings
# =========================
def create_embedding(text):
    response = openai_client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:2000]  # Free-tier safe limit
    )
    return np.array(response.data[0].embedding)


def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# =========================
# Main Worker
# =========================
def main():
    logger.info("Starting SmartApply worker (Free-tier optimized)...")

    if not DATABASE_URL:
        logger.error("DATABASE_URL not set.")
        return

    cvs = load_cvs()
    if not cvs:
        logger.info("No CVs found. Exiting.")
        return

    jobs = scrape_all_jobs()
    logger.info(f"Total jobs scraped: {len(jobs)}")

    conn, cursor = connect_db()

    # Get existing job URLs to avoid re-processing
    cursor.execute("SELECT url FROM jobs;")
    existing_urls = {row[0] for row in cursor.fetchall()}
    logger.info(f"{len(existing_urls)} jobs already stored.")

    # Embed CVs once
    cv_embeddings = {}
    if openai_client:
        for email, cv_text in cvs.items():
            try:
                cv_embeddings[email] = create_embedding(cv_text)
            except Exception as e:
                logger.error(f"Failed to embed CV {email}: {e}")

    new_jobs_processed = 0

    for job in jobs:

        if job["url"] in existing_urls:
            continue  # Skip old jobs

        new_jobs_processed += 1
        matched_users = []

        if openai_client:
            try:
                job_embedding = create_embedding(job["description"])
            except Exception as e:
                logger.error(f"Failed to embed job: {e}")
                continue

            for email, cv_vector in cv_embeddings.items():
                similarity = cosine_similarity(job_embedding, cv_vector)
                if similarity >= MATCH_THRESHOLD:
                    matched_users.append(email)

        cursor.execute("""
        INSERT INTO jobs (title, company, location, description, url, source, matched_users)
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (url) DO NOTHING
        """, (
            job["title"],
            job["company"],
            job.get("location"),
            job["description"][:2000],
            job["url"],
            job["source"],
            ",".join(matched_users)
        ))

        for email in matched_users:
            send_email(email, [job])

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"Processed {new_jobs_processed} NEW jobs.")
    logger.info("Worker completed successfully.")


if __name__ == "__main__":
    main()