import os
from app.main import app  # Import FastAPI app from the subfolder

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True  # Optional: auto-reload for dev
    )