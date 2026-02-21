from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    cv_text = Column(Text, nullable=True)
    cv_filename = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    cv_embeddings = relationship("CVEmbedding", back_populates="user", uselist=False)
    job_alerts = relationship("JobAlert", back_populates="user")

class CVEmbedding(Base):
    __tablename__ = "cv_embeddings"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    embedding = Column(Text, nullable=False)  # Store as JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="cv_embeddings")

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=False)
    url = Column(String, unique=True, nullable=False)
    embedding = Column(Text, nullable=True)  # Store as JSON string
    posted_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    alerts = relationship("JobAlert", back_populates="job")

class JobAlert(Base):
    __tablename__ = "job_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    job_id = Column(Integer, ForeignKey("jobs.id"))
    match_score = Column(Float, nullable=False)
    email_sent = Column(Boolean, default=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="job_alerts")
    job = relationship("Job", back_populates="alerts")
    
    # Ensure unique user-job pairs
    __table_args__ = (UniqueConstraint('user_id', 'job_id', name='unique_user_job'),)