# Security and Compliance Report
**Project:** SecureNotes – Secure Three-Tier Web Application on AWS
**Course:** - **Cloud Computing Capstone**  
**Student Name** - **Gaurav sharma**
**Roll No** - **2401410041**
**Btech CSE Cyber Security**

## 1. Executive summary
This project deploys a three-tier web application (Nginx frontend, Flask API, MySQL on RDS) in an AWS VPC and applies layered controls: network segmentation, least-privilege IAM and database access, encryption in transit and at rest, logging/alerting and backup. Section 6 maps controls to the NIST Cybersecurity Framework (CSF) 2.0. This is a student demonstration system, not a certified or audited production environment; Section 7 lists known gaps.

## 2. Scope and architecture
Components: EC2 (Nginx + Gunicorn/Flask) in a public subnet; RDS MySQL in two private subnets; Internet Gateway; security groups; IAM instance role; CloudWatch; S3 for logical backups. See `architecture.svg`. Trust boundaries: Internet → EC2 (HTTPS only); EC2 → RDS (3306 from `web-sg` only); administrators → EC2 (SSM Session Manager, IAM-authenticated).

## 3. Assets
| Asset | Sensitivity | Notes |
|-------|-------------|-------|
| User accounts (name, email, password hash) | High (personal data) | Passwords never stored in plain text |
| User notes | Medium–High | Private per user |
| JWT signing key, DB credentials | Critical | In `/etc/capstone.env`, mode 600, not in code |
| Logs | Medium | Contain emails and IPs; restrict access, 14-day retention |
| Backups/snapshots | High | Encrypted |

## 4. Threat analysis and risk assessment
Likelihood (L) and Impact (I) scored 1 (low) – 3 (high); rating = L × I (1–2 Low, 3–4 Medium, 6–9 High). Scores are the author's judgement for a small public demo and should be justified in your viva.

| ID | Threat | L | I | Inherent | Control(s) implemented | Residual |
|----|--------|---|---|----------|------------------------|----------|
| R1 | SQL injection | 2 | 3 | 6 High | SQLAlchemy parameterised queries; input validation; least-privilege DB user | Low |
| R2 | Credential brute force / stuffing | 3 | 2 | 6 High | Rate limit 5/min per IP (app) + Nginx limit; password policy; hashed passwords; failed-login logging and alarm | Medium (no MFA/lockout) |
| R3 | Stolen/forged session token | 2 | 3 | 6 High | Signed JWT, 2 h expiry, HTTPS, token kept in sessionStorage, strict CSP | Medium (XSS would expose token) |
| R4 | XSS | 2 | 2 | 4 Medium | `textContent` rendering, CSP `script-src 'self'`, nosniff | Low |
| R5 | Database exposed to Internet | 2 | 3 | 6 High | RDS private subnets, Public access = No, `db-sg` allows only `web-sg` | Low |
| R6 | Data interception | 2 | 3 | 6 High | HTTPS (TLS 1.2+), HSTS, TLS to RDS (`REQUIRE SSL`, CA bundle) | Low (self-signed cert in demo gives warnings, use certbot with a domain) |
| R7 | Stolen disk/snapshot data | 1 | 3 | 3 Medium | EBS and RDS encryption (KMS) | Low |
| R8 | Server compromise via SSH | 2 | 3 | 6 High | No port 22; SSM Session Manager; IMDSv2; no long-term access keys | Low |
| R9 | Over-privileged IAM | 2 | 3 | 6 High | Role limited to SSM, CloudWatch agent and one S3 prefix; MFA on admin | Low |
| R10 | Data loss / corruption | 2 | 3 | 6 High | RDS 7-day backups + PITR, manual snapshots, S3 dumps; tested restore | Low–Medium (single-AZ) |
| R11 | DoS / resource exhaustion | 2 | 2 | 4 Medium | Nginx rate limit, body size limit, CloudWatch alarms | Medium (no WAF/CDN) |
| R12 | Unpatched software | 3 | 2 | 6 High | Amazon Linux updates (`dnf update`), pinned dependencies; schedule reviews | Medium |
| R13 | Secrets leakage | 2 | 3 | 6 High | `.env` outside repo, mode 600; `.env.example` has no real values | Low–Medium |
| R14 | Single point of failure | 3 | 2 | 6 High | Backups and restore procedure only | High (accepted for cost) |
| R15 | Unexpected AWS bill | 2 | 2 | 4 Medium | Budget alerts, clean-up checklist | Low |

## 5. Security controls in more detail
* **Network:** only 80/443 exposed; DB in subnets with no internet route; Gunicorn bound to 127.0.0.1.
* **Identity:** IAM role for the server, MFA for human users, no access keys on the instance, application accounts separated from the RDS master account.
* **Application:** password policy, hashing, JWT expiry, owner checks on every note query, generic login errors, security headers.
* **Data:** encryption at rest and in transit; DB account without DDL privileges.
* **Monitoring:** application, Nginx, auth logs and RDS error/slow logs in CloudWatch; alarms on CPU, status checks, storage, connections and failed logins.
* **Recovery:** documented backup and restore procedure (RTO/RPO to be measured in your drill).

## 6. NIST CSF 2.0 mapping
| Function | Category (examples) | How this project addresses it |
|----------|--------------------|-------------------------------|
| **GOVERN (GV)** | Risk management strategy, roles, supply chain | Risk register (Section 4) with ratings; budget limits; pinned dependency versions; documented shared-responsibility with AWS |
| **IDENTIFY (ID)** | Asset management, risk assessment | Asset table (Section 3); architecture diagram; threat/risk analysis |
| **PROTECT (PR)** | Identity & access (PR.AA), data security (PR.DS), platform security (PR.PS), infrastructure resilience (PR.IR) | IAM roles + MFA; password hashing and JWT; encryption at rest/in transit; security groups and subnet isolation; hardened Nginx and systemd unit; patching process |
| **DETECT (DE)** | Continuous monitoring, adverse event analysis | CloudWatch logs, metrics, alarms, failed-login metric filter; RDS log exports |
| **RESPOND (RS)** | Incident management, analysis, mitigation | SNS alert emails; runbook below; ability to block IPs via security group, rotate secrets, restart or isolate the instance |
| **RECOVER (RC)** | Incident recovery plan execution | RDS automated backups/PITR, snapshots, S3 dumps, restore procedure and drill |

**Basic incident runbook:** (1) alarm received → (2) review `/capstone/app` and Nginx logs → (3) contain (tighten security group, stop service, rotate `SECRET_KEY`/DB password) → (4) eradicate and patch → (5) restore from backup if data affected → (6) record lessons learned.

## 7. Known limitations and recommended improvements
No MFA for application users; no account lockout or email verification; rate-limit counters are per Gunicorn worker (in-memory); single AZ and single EC2 instance; no AWS WAF, GuardDuty, CloudTrail alert rules or AWS Config rules enabled (recommended: turn on CloudTrail and GuardDuty); JWT in sessionStorage is exposed if XSS occurs (httpOnly cookies + CSRF protection would be stronger); the self-signed demo certificate is not trusted by browsers; logs contain emails (personal data). Note that this report maps to NIST CSF as a self-assessment; it is not a formal compliance certification.

## 8. Test evidence
Insert your completed table from `TESTING_AND_COSTS.md` (Section B) with screenshots. Automated test output: run `python -m pytest -q` and paste the result.

## 9. References
NIST Cybersecurity Framework 2.0 (2024); AWS Well-Architected Framework – Security Pillar; AWS Shared Responsibility Model; OWASP Top 10.
