import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./feedbackflow.db")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "feedbackflow-demo")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
AI_API_KEY = os.getenv("AI_API_KEY")
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "gpt-4.1-mini")
