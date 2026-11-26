# SecureNotes – Secure Three-Tier Web Application on AWS
Cloud Computing Capstone Project

A small but complete app (register, login, private notes) used to demonstrate **secure cloud architecture**:

| Tier | Technology | Where it runs |
|------|-----------|---------------|
| 1. Presentation | HTML, CSS, JavaScript served by **Nginx** (HTTPS) | EC2, public subnet |
| 2. Application | **Python Flask** REST API via Gunicorn | Same EC2, listening on localhost only |
| 3. Data | **MySQL 8 on Amazon RDS** | Private subnets, no internet route |

![Architecture](docs/architecture.svg)

## Folder structure
```
capstone/
├── README.md
├── backend/            Flask API (app.py, config.py, wsgi.py, requirements.txt, .env.example, tests/)
├── frontend/           index.html, style.css, app.js
├── database/schema.sql Tables + least-privilege DB user
├── deploy/             nginx.conf, capstone.service, cloudwatch-agent.json, backup.sh
└── docs/               DEPLOYMENT.md, SECURITY_REPORT.md, TESTING_AND_COSTS.md, architecture.svg
```

## Run locally (no AWS needed)
```bash
cd backend
python3 -m venv venv && source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_hex(32))")
export DATABASE_URL=sqlite:///dev.db                     # uses SQLite instead of MySQL
python -m pytest -q                                      # run the automated tests
gunicorn --bind 127.0.0.1:8000 wsgi:app                  # API on :8000
```
For the UI locally, serve `frontend/` and proxy `/api` to port 8000 (easiest: use the Nginx setup in `docs/DEPLOYMENT.md`, or a tiny dev proxy). The API alone can be tried with `curl http://127.0.0.1:8000/api/health`.

## Security features (summary)
Password hashing (salted, via Werkzeug) · JWT sessions that expire · input validation · SQLAlchemy parameterised queries (SQL-injection safe) · per-user data isolation · login/registration rate limiting (app + Nginx) · security headers and CSP · HTTPS · private encrypted RDS reachable only from the web security group · IAM role instead of access keys · SSH closed (SSM Session Manager) · CloudWatch logs and alarms · automated + manual backups.

## Documents
1. `docs/DEPLOYMENT.md` – step-by-step AWS setup
2. `docs/TESTING_AND_COSTS.md` – test procedures and estimated charges
3. `docs/SECURITY_REPORT.md` – risk assessment and NIST CSF mapping for submission

## Honest limitations
Nginx and Flask share one EC2 instance (cheapest option; logically separate tiers, one failure domain). No load balancer, WAF or Multi-AZ database by default – the security report lists these as recommended upgrades.
