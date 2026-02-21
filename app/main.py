from app.scraper import scrape_all_jobs

@app.post("/run_pipeline", response_model=schemas.PipelineResponse)
async def run_pipeline(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    max_pages_gozambia: int = 3,
    max_pages_greatzambia: int = 5
):
    """Run the complete job matching pipeline with multiple job sources"""
    try:
        logger.info("Starting job matching pipeline with multiple sources...")
        
        # Step 1: Fetch jobs from all sources
        logger.info("Fetching jobs from all sources...")
        jobs = scrape_all_jobs({
            'gozambia': max_pages_gozambia,
            'greatzambiajobs': max_pages_greatzambia
        })
        
        if not jobs:
            return schemas.PipelineResponse(
                status="completed",
                jobs_fetched=0,
                matches_found=0,
                emails_sent=0,
                message="No jobs found to process from any source"
            )
        
        logger.info(f"Fetched {len(jobs)} total jobs from all sources")
        
        # Step 2: Match jobs for all users
        logger.info("Matching jobs for users...")
        matches = matcher.match_all_users(db, jobs)
        
        total_matches = sum(len(user_matches) for user_matches in matches.values())
        logger.info(f"Found {total_matches} matches for {len(matches)} users")
        
        # Step 3: Send email alerts
        logger.info("Sending email alerts...")
        emails_sent = email_sender.send_alerts_for_matches(db, matches)
        
        # Log source statistics
        source_counts = {}
        for job in jobs:
            source = job.get('source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        logger.info(f"Jobs by source: {source_counts}")
        logger.info(f"Sent {emails_sent} email alerts")
        
        return schemas.PipelineResponse(
            status="completed",
            jobs_fetched=len(jobs),
            matches_found=total_matches,
            emails_sent=emails_sent,
            message=f"Successfully processed {len(jobs)} jobs from {len(source_counts)} sources, found {total_matches} matches, sent {emails_sent} emails"
        )
        
    except Exception as e:
        logger.error(f"Error in pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))