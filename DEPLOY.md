# Deploy — The Tuesday Man

Step-by-step guide to put the app on a fresh Linux server.

---

## 1. Buy a server

**Recommended:** DigitalOcean Basic Droplet — **Toronto region**
(closest to Royal Ottawa Golf Club, minimises booking latency)

| Size | RAM | Cost | Notes |
|------|-----|------|-------|
| Basic 1 GB | 1 vCPU · 1 GB · 25 GB SSD | **~$6 USD/mo** | ✅ enough for this app |

Sign up at digitalocean.com → Create Droplet → Ubuntu 24.04 LTS → Toronto → $6 plan.
Add your SSH key during creation.

---

## 2. Domain / subdomain

You need a domain so certbot can issue a free HTTPS certificate.
Add a DNS **A record** pointing to your droplet's IP before running certbot.

Example: `tuesday.bronson.ai → <droplet-IP>`

---

## 3. First login & basic hardening

```bash
ssh root@<droplet-IP>

# Create a dedicated app user
adduser tuesdayman
usermod -aG sudo tuesdayman

# Switch to that user for everything below
su - tuesdayman
```

---

## 4. Install system packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git
```

---

## 5. Clone the repo

```bash
sudo mkdir -p /opt/tuesdayman
sudo chown tuesdayman:tuesdayman /opt/tuesdayman
cd /opt/tuesdayman
git clone https://github.com/mahtabBronson-ai/The-Tuesday-Man .
```

---

## 6. Python environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install firefox
playwright install-deps firefox
```

---

## 7. Create the data directory & encryption key

The `data/` folder holds secrets that are **not** in the repo.

```bash
mkdir -p data/screenshots
# Generate a fresh Fernet encryption key
python3 -c "from cryptography.fernet import Fernet; open('data/.encryption_key','wb').write(Fernet.generate_key())"
chmod 600 data/.encryption_key
```

---

## 8. Install & start the systemd service

```bash
sudo cp the-tuesday-man.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable the-tuesday-man
sudo systemctl start the-tuesday-man

# Check it started
sudo systemctl status the-tuesday-man
```

The Flask app is now running on `127.0.0.1:5000`.

---

## 9. Configure nginx + HTTPS

Replace `YOUR_DOMAIN` in `nginx.conf` with your actual domain, then:

```bash
sudo cp nginx.conf /etc/nginx/sites-available/tuesdayman
# Edit YOUR_DOMAIN in the file
sudo nano /etc/nginx/sites-available/tuesdayman

sudo ln -s /etc/nginx/sites-available/tuesdayman /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Issue a free Let's Encrypt certificate
sudo certbot --nginx -d YOUR_DOMAIN

sudo systemctl reload nginx
```

Martin can now open `https://YOUR_DOMAIN` in his browser.

---

## 10. First-time app setup

Open `https://YOUR_DOMAIN` in a browser.
The setup wizard will ask for:
- Golf club email + password (stored encrypted)

Then go to **Settings** to configure course IDs, buddies, and schedule.

---

## 11. Weekly cron job (the actual booking)

This fires `scheduled_runner.py` every Wednesday at 7:25 AM Eastern,
which logs in to the golf site and waits to book at exactly 7:30:00.

```bash
crontab -e
```

Add this line:

```
25 7 * * 3 /opt/tuesdayman/venv/bin/python /opt/tuesdayman/scheduled_runner.py --scheduled >> /opt/tuesdayman/data/cron.log 2>&1
```

Verify cron timezone matches the server:
```bash
timedatectl set-timezone America/Toronto
```

---

## 12. Ongoing updates

```bash
cd /opt/tuesdayman
git pull
sudo systemctl restart the-tuesday-man
```

---

## What the cron flag does

| Flag | Behaviour |
|------|-----------|
| `--scheduled` | Checks `booking_active` toggle in DB; skips silently if disabled |
| `--dry-run` | Full flow but skips the final Book POST — safe to run any time |
| *(no flag)* | Books immediately without waiting for 7:30 |
