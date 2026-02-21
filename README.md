# SmartApply Agent - AI-Powered Job Matching

SmartApply Agent is an automated job matching system that scrapes jobs from GoZambia.com, uses AI to match them with user CVs, and sends email alerts for high-quality matches.

## Features

- 📝 User signup with CV upload (PDF/TXT)
- 🔍 Automated job scraping from GoZambia.com
- 🤖 AI-powered matching using OpenAI embeddings
- 📧 Email alerts for matches ≥ 70% similarity
- 💾 PostgreSQL database for persistent storage
- 🚀 Ready for deployment on Railway

## Prerequisites

- Python 3.11+
- PostgreSQL database
- OpenAI API key
- Gmail account (for sending emails)

## Local Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/smartapply-agent.git
   cd smartapply-agent