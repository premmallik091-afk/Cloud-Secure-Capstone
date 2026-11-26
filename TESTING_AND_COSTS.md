# Testing Procedures and Estimated AWS Costs

## A. Automated tests (run before every deployment)
`cd backend && python -m pytest -q` covers: health check, registration/login, duplicate email, weak passwords, invalid email, wrong password, password hashing, token required, per-user note isolation (user B cannot delete user A's note), SQL-injection string on login, and security headers.
These tests use SQLite in memory, so they verify application logic, **not** the MySQL/RDS connection, Nginx, or AWS settings. Test those with section B after deploying.

## B. Manual deployment tests (fill in the Result column yourself)
| # | Test | Steps | Expected | Result / evidence |
|---|------|-------|----------|-------------------|
| 1 | HTTPS | Open `https://<IP>`; `curl -I http://<IP>` | Page loads; HTTP returns 301 to HTTPS | |
| 2 | API↔DB | `curl -k https://<IP>/api/health` | `status ok, database up` | |
| 3 | Register/login | Use the UI | Account created, notes work | |
| 4 | DB not public | From your laptop: `mysql -h <RDS-ENDPOINT> -u appuser -p` | Connection times out | |
| 5 | SG rule | RDS console: Public access = No; `db-sg` source = `web-sg` | As stated | |
| 6 | Data encrypted | RDS → Configuration shows encryption enabled | Enabled | |
| 7 | Brute-force limit | Submit 6 wrong logins in a minute | 6th gives HTTP 429 | |
| 8 | Logging | Log in, then check `/capstone/app` log group | LOGIN ok/failed lines appear | |
| 9 | Alarm | Stop `capstone` service, wait; or `stress` the CPU | Alarm/email fires | |
| 10 | Backup/restore | Take snapshot, restore to a new instance | Restored DB contains the users table | |
| 11 | No SSH | Try SSH to the public IP on port 22 | Refused/times out | |
| 12 | XSS | Add a note containing `<script>alert(1)</script>` | Shown as plain text, no popup | |

Take screenshots for each row and attach them to your submission. Do not report a test as passed unless you ran it.

## C. Estimated monthly cost (running 24/7, one region, approximate)
Prices vary by region and change over time. **Verify with the AWS Pricing Calculator for your region before deploying.** Figures below use rough on-demand rates, in USD.

| Item | Approx. monthly |
|------|-----------------|
| EC2 t3.micro (730 h) | ~$8–10 |
| EC2 EBS 8 GB gp3 | ~$0.7 |
| RDS db.t3.micro single-AZ (730 h) | ~$12–16 |
| RDS storage 20 GB gp3 | ~$2–3 |
| RDS backup storage (within allocated size) | $0 typically |
| Public IPv4 address for EC2 | ~$3.6 |
| CloudWatch logs/metrics/alarms (small volume) | ~$1–5 |
| S3 backups (a few MB), SNS email | <$1 |
| **Total (approx.)** | **~$28–40 per month** |

**Cost-saving advice for a college project:** deploy only for the demo week, stop (not delete) the instances between sessions (RDS auto-restarts after 7 days; EC2 storage and the public IP still bill), then follow the clean-up list. Newer AWS accounts may receive promotional credits and older accounts a 12-month free tier for t2/t3.micro and RDS micro; check your Billing → Free tier page for what actually applies to you. Avoid NAT Gateways (~$30+/month), Multi-AZ RDS (about double), and load balancers (~$16+/month) unless needed.
