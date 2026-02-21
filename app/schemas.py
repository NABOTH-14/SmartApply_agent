from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserSignup(BaseModel):
    name: str
    email: EmailStr

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class JobSchema(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: str
    url: str
    
    class Config:
        from_attributes = True

class JobAlertSchema(BaseModel):
    job: JobSchema
    match_score: float
    email_sent: bool
    
    class Config:
        from_attributes = True

class PipelineResponse(BaseModel):
    status: str
    jobs_fetched: int
    matches_found: int
    emails_sent: int
    message: str