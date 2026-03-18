# Mini Web Application

Flask, HTML/JavaScript, MySQL, and Docker based starter project.

## Stack

- Backend: Flask
- Frontend: HTML, CSS, Vanilla JavaScript
- Database: MySQL 8
- Runtime: Docker Compose

## Run

1. Copy `.env.example` to `.env`
2. Start services:

```bash
docker compose up --build
```

3. Open `http://localhost:5000`

## Structure

```text
app/
  static/
    css/
    js/
  templates/
  __init__.py
  config.py
  db.py
  routes.py
database/
  init/
app.py
Dockerfile
docker-compose.yml
requirements.txt
```
