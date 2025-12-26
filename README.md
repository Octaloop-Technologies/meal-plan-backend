# Meal Plan API

**Standalone Backend API Server** - Can be copied, installed, and run independently.

## Quick Start

```bash
# 1. Copy this folder anywhere
# 2. Navigate to the folder
cd api

# 3. Install and run (Windows)
.\start.ps1

# Or (Linux/Mac)
chmod +x start.sh
./start.sh

# Or manually:
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env  # Edit .env with your configuration

# Start the API server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Requirements

- Python 3.8+
- MongoDB (local or cloud)
- pip

## Configuration

1. Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

2. Edit `.env` with your configuration:
   - `MONGODB_URL` - MongoDB connection string
   - `SHOPIFY_SHOP_DOMAIN` - Your Shopify shop domain
   - `SECRET_KEY` - JWT secret key (min 32 characters)
   - `ADMIN_API_KEY` - Admin API key for admin endpoints
   - `OPENAI_API_KEY` - OpenAI API key (optional)
   - `ALLOWED_ORIGINS` - Comma-separated list of allowed CORS origins

## Running

### Development
```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Production
```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `MONGODB_URL` - MongoDB connection string
- `MONGODB_DB_NAME` - Database name
- `SECRET_KEY` - JWT secret key
- `ADMIN_API_KEY` - Admin API key
- `OPENAI_API_KEY` - OpenAI API key (optional)
- `ALLOWED_ORIGINS` - CORS allowed origins

## Features

- FastAPI-based REST API
- MongoDB database with Beanie ODM
- JWT authentication
- OpenAI integration for meal suggestions
- PDF generation for meal plans
- Shopify integration
- CORS enabled for multiple clients

## Deployment

This API can be deployed independently on:
- Heroku
- AWS Lambda (with Mangum)
- Google Cloud Run
- Azure App Service
- DigitalOcean App Platform
- Self-hosted server

**Important**: Set all environment variables in your deployment platform.

## CORS Configuration

The API accepts requests from origins specified in `ALLOWED_ORIGINS`. Default includes:
- `http://localhost:3000` (Frontend)
- `http://localhost:3001` (Admin)
- `https://*.myshopify.com` (Shopify stores)

## Dependencies

All dependencies are listed in `requirements.txt`. Install with:
```bash
pip install -r requirements.txt
```

## Standalone Operation

This API is **fully independent**:
- ✅ No dependencies on frontend or admin folders
- ✅ Can be copied and run anywhere
- ✅ All configuration via environment variables
- ✅ Self-contained startup scripts

## Support

For issues or questions, check the main project README or contact the development team.
