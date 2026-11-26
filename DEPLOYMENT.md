# AWS Deployment Guide (AWS Console, beginner-friendly)

Pick one region (e.g. **ap-south-1 Mumbai**) and use it for everything. Names below are suggestions.
> ⚠️ Charges: EC2, RDS, public IPv4 and storage cost money once any free credits are used. **Section 10** deletes everything. See `TESTING_AND_COSTS.md`.

## 0. Prepare your AWS account
1. Sign in as the root user once, enable **MFA** (Account → Security credentials).
2. Create an IAM admin user (IAM → Users) with MFA, and use that from now on. Billing → **Budgets** → create a monthly budget (e.g. $15) with email alerts.

## 1. VPC and subnets
VPC → *Create VPC* → **VPC and more** is quickest, but it creates a NAT Gateway (paid). Build manually instead:
1. Create VPC `capstone-vpc`, CIDR `10.0.0.0/16`.
2. Subnets: `public-a` 10.0.1.0/24 (AZ a), `private-a` 10.0.2.0/24 (AZ a), `private-b` 10.0.3.0/24 (AZ b). RDS needs subnets in two AZs.
3. Create an **Internet Gateway** and attach it to the VPC.
4. Route tables: `public-rt` with `0.0.0.0/0 → IGW`, associate with `public-a`. Leave the private subnets on the default table (local route only = no internet).
5. Public subnet → Actions → Edit settings → enable *auto-assign public IPv4*.

## 2. Security groups (VPC → Security groups)
| Name | Inbound rule | Why |
|------|-------------|-----|
| `web-sg` | TCP 80 and 443 from `0.0.0.0/0` | public web traffic |
| `db-sg` | TCP 3306, **source = web-sg** | only the web server can reach MySQL |
No SSH rule: you will connect with Session Manager.

## 3. IAM role for the EC2 instance
IAM → Roles → Create → trusted entity *EC2*. Attach `AmazonSSMManagedInstanceCore` and `CloudWatchAgentServerPolicy`. Name it `capstone-ec2-role`. (For backups to S3, later add an inline policy allowing `s3:PutObject` on your backup bucket only.)

## 4. RDS MySQL (private)
1. RDS → Subnet groups → create `capstone-db-subnets` with `private-a` and `private-b`.
2. Create database → MySQL 8.0 → template **Free tier / Dev-Test**, single-AZ, `db.t3.micro`, 20 GB gp3 storage.
3. Master username `admin`, strong password (store it in a password manager).
4. Connectivity: VPC `capstone-vpc`, subnet group above, **Public access: No**, security group `db-sg`.
5. Additional configuration: initial DB name `capstone`, **encryption enabled**, backup retention **7 days**, enable deletion protection for the demo's final state, enable log exports (error, slow query) to CloudWatch.
6. Wait for *Available* and copy the **endpoint**.

## 5. Launch the EC2 web/app server
EC2 → Launch instance: Amazon Linux 2023, `t3.micro`, no key pair needed (SSM), network `capstone-vpc` / `public-a`, auto-assign public IP, security group `web-sg`, IAM instance profile `capstone-ec2-role`, storage 8 GB gp3 **encrypted**, metadata: **IMDSv2 required**. Connect via *Connect → Session Manager*.

## 6. Install software (on the instance)
```bash
sudo dnf install -y python3-pip nginx mariadb105 git amazon-cloudwatch-agent openssl
sudo useradd -r capstone
sudo mkdir -p /opt/capstone /var/www/capstone /var/log/capstone /etc/ssl/rds
sudo chown capstone:capstone /var/log/capstone
```
Get the code onto the server (e.g. push the project to a private GitHub repo and `git clone` it into `/opt/capstone`; or upload a zip to S3 and `aws s3 cp` it). Then:
```bash
cd /opt/capstone
sudo python3 -m venv venv && sudo venv/bin/pip install -r backend/requirements.txt
sudo cp -r frontend/* /var/www/capstone/
sudo curl -o /etc/ssl/rds/global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

## 7. Create the database schema
Edit the password in `database/schema.sql`, then:
```bash
mysql -h <RDS-ENDPOINT> -u admin -p --ssl-ca=/etc/ssl/rds/global-bundle.pem < database/schema.sql
```
Delete the shell history line afterwards (`history -c`).

## 8. Configure and start the application
```bash
sudo cp backend/.env.example /etc/capstone.env && sudo chmod 600 /etc/capstone.env
sudo nano /etc/capstone.env        # set SECRET_KEY, DB_HOST, DB_PASSWORD
sudo cp deploy/capstone.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now capstone
curl http://127.0.0.1:8000/api/health        # expect {"database":"up","status":"ok"}
```
If it shows `down`, check `sudo journalctl -u capstone -n 50` and that `db-sg` allows `web-sg`.

## 9. HTTPS with Nginx
**Demo (no domain):** self-signed certificate. Browsers show a warning, but traffic is encrypted.
```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout /etc/nginx/ssl/selfsigned.key -out /etc/nginx/ssl/selfsigned.crt -subj "/CN=capstone-demo"
sudo cp deploy/nginx.conf /etc/nginx/conf.d/capstone.conf
sudo nginx -t && sudo systemctl enable --now nginx
```
Open `https://<EC2-public-IP>`. **Trusted certificate:** point a domain's A record to the instance's Elastic IP, install certbot (`sudo dnf install -y certbot python3-certbot-nginx`), set `server_name`, run `sudo certbot --nginx -d your.domain`. (An ALB + ACM certificate is the managed alternative but adds a monthly load-balancer charge.)

## 10. CloudWatch monitoring
```bash
sudo cp deploy/cloudwatch-agent.json /opt/aws/amazon-cloudwatch-agent/etc/config.json
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -s -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json
```
Console checks: CloudWatch → Log groups (`/capstone/app`, `/capstone/nginx-access`, `/capstone/ssh-auth`).
Create alarms (CloudWatch → Alarms) with an SNS topic that emails you: EC2 `CPUUtilization > 80%` for 10 min, `StatusCheckFailed > 0`, RDS `CPUUtilization > 80%`, RDS `FreeStorageSpace` low, RDS `DatabaseConnections` high. Optional metric filter on `/capstone/app` for the text `LOGIN failed` with an alarm at e.g. 10 per 5 minutes (brute-force signal). Verify `/capstone/ssh-auth` before relying on it; the log file name differs between OS images.

## 11. Backup and recovery
* **Automatic:** RDS keeps daily snapshots for 7 days plus transaction logs (point-in-time restore).
* **Manual snapshot:** RDS → Databases → Actions → *Take snapshot* (before changes and before the demo).
* **Logical backup:** create a private S3 bucket (block public access, default encryption), add the S3 permission to the EC2 role, set `S3_BUCKET`, and schedule `deploy/backup.sh` with cron (`0 2 * * * S3_BUCKET=<bucket> /opt/capstone/deploy/backup.sh`).
* **Recovery drill:** RDS → Snapshots → *Restore snapshot* creates a **new** instance (same VPC/subnet group/`db-sg`); update `DB_HOST` in `/etc/capstone.env` and `sudo systemctl restart capstone`. Record how long it took for your report.

## 12. Clean up (stop charges)
Delete in this order: EC2 instance → RDS instance (decline final snapshot unless you want it) and manual snapshots → release any Elastic IP → S3 bucket contents and bucket → CloudWatch log groups → VPC (subnets, IGW, route tables, security groups) → SNS topic. Check Billing the next day.
