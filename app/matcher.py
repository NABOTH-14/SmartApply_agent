import os
import json
import numpy as np
from openai import OpenAI
from typing import List, Dict, Tuple
import logging
from sqlalchemy.orm import Session
from app import models
from app.utils import clean_text, truncate_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobMatcher:
    """AI-powered job matcher using OpenAI embeddings"""
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.embedding_model = "text-embedding-3-small"
        self.similarity_threshold = 0.7
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using OpenAI API"""
        try:
            cleaned_text = clean_text(text)
            truncated_text = truncate_text(cleaned_text)
            
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=truncated_text
            )
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            raise
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings"""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    def match_jobs_for_user(self, db: Session, user_id: int, jobs: List[Dict]) -> List[Tuple[Dict, float]]:
        """Match jobs for a specific user"""
        # Get user and their CV embedding
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user or not user.cv_text:
            logger.warning(f"User {user_id} has no CV text")
            return []
        
        cv_embedding_data = db.query(models.CVEmbedding).filter(
            models.CVEmbedding.user_id == user_id
        ).first()
        
        if not cv_embedding_data:
            # Generate and store CV embedding
            cv_embedding = self.get_embedding(user.cv_text)
            cv_embedding_data = models.CVEmbedding(
                user_id=user_id,
                embedding=json.dumps(cv_embedding)
            )
            db.add(cv_embedding_data)
            db.commit()
        else:
            cv_embedding = json.loads(cv_embedding_data.embedding)
        
        # Get existing alerts to avoid duplicates
        existing_alerts = db.query(models.JobAlert).filter(
            models.JobAlert.user_id == user_id
        ).all()
        existing_job_ids = {alert.job_id for alert in existing_alerts}
        
        # Match jobs
        matches = []
        for job_data in jobs:
            # Check if job already exists in DB
            existing_job = db.query(models.Job).filter(
                models.Job.url == job_data['url']
            ).first()
            
            if existing_job and existing_job.id in existing_job_ids:
                continue  # Skip already alerted jobs
            
            # Get or create job
            if not existing_job:
                # Get embedding for job
                job_embedding = self.get_embedding(
                    f"{job_data['title']} {job_data['description']}"
                )
                
                job = models.Job(
                    title=job_data['title'],
                    company=job_data['company'],
                    location=job_data.get('location'),
                    description=job_data['description'],
                    url=job_data['url'],
                    embedding=json.dumps(job_embedding)
                )
                db.add(job)
                db.flush()
                job_id = job.id
                job_embedding_list = job_embedding
            else:
                job_id = existing_job.id
                job_embedding_list = json.loads(existing_job.embedding) if existing_job.embedding else None
            
            if job_embedding_list:
                # Compute similarity
                similarity = self.compute_similarity(cv_embedding, job_embedding_list)
                
                if similarity >= self.similarity_threshold:
                    matches.append((job_data, similarity))
                    
                    # Create alert record
                    alert = models.JobAlert(
                        user_id=user_id,
                        job_id=job_id,
                        match_score=similarity,
                        email_sent=False
                    )
                    db.add(alert)
        
        db.commit()
        return matches
    
    def match_all_users(self, db: Session, jobs: List[Dict]) -> Dict[int, List[Tuple[Dict, float]]]:
        """Match jobs for all users"""
        users = db.query(models.User).filter(models.User.cv_text.isnot(None)).all()
        
        all_matches = {}
        for user in users:
            logger.info(f"Matching jobs for user {user.id} ({user.email})")
            matches = self.match_jobs_for_user(db, user.id, jobs)
            if matches:
                all_matches[user.id] = matches
                logger.info(f"Found {len(matches)} matches for user {user.id}")
        
        return all_matches