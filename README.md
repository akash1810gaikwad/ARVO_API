# Python API with MongoDB & MSSQL

A production-ready Python API built with FastAPI, featuring MongoDB for audit logs and MSSQL for main relational data, following MVC pattern.

## Features

- **FastAPI Framework** - Modern, fast web framework
- **Dual Database Architecture**
  - MongoDB for audit logs and flexible data
  - MSSQL for main relational data
- **MVC Pattern** - Clean separation of concerns
- **Comprehensive Logging** - JSON-formatted application logs
- **Cron Jobs** - Scheduled tasks for maintenance
- **CORS Support** - Ready for React frontend
- **Pydantic Schemas** - Request/response validation
- **SQLAlchemy ORM** - Database models and migrations
- **Async Support** - High-performance async operations

## Project Structure

```
├── app.py                  # Main application entry point
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── config/
│   ├── settings.py        # Application settings
│   └── database.py        # Database connections
├── models/
│   └── mssql_models.py    # SQLAlchemy models for MSSQL
├── schemas/
│   ├── user_schema.py     # User validation schemas
│   ├── post_schema.py     # Post validation schemas
│   └── audit_schema.py    # Audit log schemas
├── services/
│   ├── user_service.py    # User business logic
│   ├── post_service.py    # Post business logic
│   └── audit_service.py   # Audit log service
├── routes/
│   ├── user_routes.py     # User endpoints
│   ├── post_routes.py     # Post endpoints
│   └── audit_routes.py    # Audit log endpoints
├── cron/
│   └── jobs.py            # Scheduled cron jobs
├── middleware/
│   └── logging_middleware.py  # Request logging
└── utils/
    └── logger.py          # Logging configuration
```

## Setup

1. **Install Python 3.11+**

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
copy .env.example .env
```

Edit `.env` with your database credentials:
- MongoDB connection string
- MSSQL server details

4. **Install ODBC Driver for SQL Server:**
- Windows: Download from Microsoft
- Linux: `sudo apt-get install unixodbc-dev`

5. **Run the application:**
```bash
python app.py
```

Or with uvicorn:
```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Users
- `POST /api/users/` - Create user
- `GET /api/users/` - List users
- `GET /api/users/{id}` - Get user
- `PUT /api/users/{id}` - Update user
- `DELETE /api/users/{id}` - Delete user

### Posts
- `POST /api/posts/` - Create post
- `GET /api/posts/` - List posts
- `GET /api/posts/{id}` - Get post
- `GET /api/posts/user/{user_id}` - Get user posts
- `PUT /api/posts/{id}` - Update post
- `DELETE /api/posts/{id}` - Delete post

### Audit Logs
- `GET /api/audit/` - List audit logs (with filters)
- `GET /api/audit/{id}` - Get audit log

### API Logs
- `GET /api/logs/` - List API logs (with filters)
- `GET /api/logs/stats` - Get API usage statistics
- `GET /api/logs/{id}` - Get specific API log
- `DELETE /api/logs/cleanup` - Manually trigger cleanup

### System
- `GET /` - Root endpoint
- `GET /health` - Health check

## Cron Jobs

The application includes scheduled tasks:

1. **Cleanup Old API Logs** - Every 6 hours
   - Removes API logs older than 2 days
   - Keeps only recent API request/response logs

2. **Cleanup Old Audit Logs** - Daily at 2 AM
   - Removes audit logs older than 90 days

3. **Daily Report** - Daily at 8 AM
   - Generates activity summary

4. **Health Check** - Every 15 minutes
   - Monitors system health

## Logging

The application has comprehensive logging:

1. **Application Logs**
   - Console (stdout)
   - File: `logs/app.log`
   - Format: JSON with timestamp, level, and message

2. **API Request/Response Logs** (MongoDB)
   - Every API hit is logged with:
     - Request method, path, query params, body
     - Response body and status code
     - Duration, client IP, user agent
   - Automatically cleaned up after 2 days
   - View via `/api/logs/` endpoint

## Development

### Adding New Models

1. Create model in `models/mssql_models.py`
2. Create schemas in `schemas/`
3. Create service in `services/`
4. Create routes in `routes/`
5. Register router in `app.py`

### Adding Cron Jobs

Add new jobs in `cron/jobs.py` using APScheduler

## Production Deployment

1. Set `APP_ENV=production` in `.env`
2. Set `APP_DEBUG=False`
3. Use proper password hashing (bcrypt)
4. Configure SSL/TLS
5. Use production WSGI server (Gunicorn)
6. Set up reverse proxy (Nginx)
7. Configure firewall rules
8. Enable database backups

## Testing

```bash
pytest
```

## License

MIT
