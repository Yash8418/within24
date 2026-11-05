import os
import warnings

DEV_SECRET = "dev-only-secret-change-me"

SECRET_KEY = os.getenv("SECRET_KEY", DEV_SECRET)
if SECRET_KEY == DEV_SECRET:
    warnings.warn("SECRET_KEY is not set; using an insecure development key.", stacklevel=1)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))

# Comma-separated list of frontend origins allowed to call the API.
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
