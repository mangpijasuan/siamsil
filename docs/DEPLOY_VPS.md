# Deploy the API on one small server (VPS)

Status: **guide, not yet run.** An alternative to the Railway steps in [DEPLOY.md](DEPLOY.md), chosen because Railway's Hobby plan caps storage at 5 GB and bills memory by use, while this API holds a 1.6 GB database. Prices below are from memory; check each provider's page. Keep Siamsil on its **own server**, apart from any trading or financial software.

The website stays on Vercel. This server runs three containers: Caddy (HTTPS), the API, and PostgreSQL. Files are in `deploy/vps/`.

## What you need

- The data bundle already uploaded to the private R2 bucket (DEPLOY.md, step 2), with its 64-character SHA-256.
- The **read-only** R2 token's Access Key ID and Secret Access Key (never the upload token).
- Your R2 endpoint: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`.
- The domain `siamsil.org` in Cloudflare.

## 1. Rent the server

At a provider such as Hetzner (check current plans): about 2 vCPU, 4 GB RAM, 40 GB disk, Ubuntu 24.04. Add your SSH key when asked (so you log in without a password). Note the server's IP address.

## 2. First login and basic safety

From your Mac:

```bash
ssh root@SERVER-IP
```

On the server:

```bash
apt update && apt -y upgrade
adduser siamsil            # choose a strong password
usermod -aG sudo siamsil
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
apt -y install unattended-upgrades fail2ban
```

Copy your SSH key to the new user, then work as that user from now on:

```bash
rsync --archive --chown=siamsil:siamsil ~/.ssh /home/siamsil
exit
ssh siamsil@SERVER-IP
```

Optional but wise: turn off password login (`PasswordAuthentication no` in `/etc/ssh/sshd_config.d/`, then `sudo systemctl restart ssh`) once your key login works.

## 3. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
exit
ssh siamsil@SERVER-IP
docker --version && docker compose version
```

## 4. Get the code and set the secrets

```bash
git clone https://github.com/mangpijasuan/siamsil.git
cd siamsil/deploy/vps
cp .env.example .env
chmod 600 .env
nano .env
```

Fill in every line: the domain, a long random `POSTGRES_PASSWORD` (for example `openssl rand -base64 32`), your R2 endpoint, the **read-only** keys, and the SHA-256. Leave `SIAMSIL_SERVE_PARALLEL_CORPUS=false`: the 1.77M-pair corpus is blocked and must stay hidden. Save with Ctrl+O, Enter, then exit with Ctrl+X.

## 5. Point the domain at the server

In Cloudflare DNS add an **A** record: name `api`, value `SERVER-IP`, **DNS only** (grey cloud), so Caddy can get its certificate. Wait a few minutes.

## 6. Start it

```bash
docker compose --env-file .env up -d --build
docker compose logs -f api
```

The first start downloads and unpacks the bundle (several minutes). Wait for lines saying the server is running, then press Ctrl+C to stop reading logs (the API keeps running).

## 7. Check

- `https://api.siamsil.org/health` reports `"status": "ok"` and the dictionary counts.
- A dictionary search for "water" works: `https://api.siamsil.org/api/v1/dictionary/search?q=water`.
- A Translate search returns dictionary results only, with no corpus sentences.

## 8. Website

On Vercel (DEPLOY.md, section 4) set `SIAMSIL_API_URL` and `NEXT_PUBLIC_API_URL` to `https://api.siamsil.org` and `SIAMSIL_SITE_URL` to `https://siamsil.org`, then add the domains and DNS records Vercel shows.

## Everyday tasks

| Task | Command (in `siamsil/deploy/vps`) |
|---|---|
| Update the code | `git pull && docker compose --env-file .env up -d --build` |
| New data release | Upload the new bundle to R2, change `SIAMSIL_DATA_BUNDLE_SHA256` in `.env`, then `docker compose --env-file .env up -d` |
| See logs | `docker compose logs --tail 100 api` |
| Restart | `docker compose restart` |
| Disk space | `df -h` and `docker system df` |

## Backups

- The data bundle lives in R2, so the language data can always be restored.
- PostgreSQL holds accounts and review records. Back it up before you rely on it: `docker compose exec postgres pg_dump -U siamsil siamsil | gzip > backup-$(date +%F).sql.gz`, then copy the file off the server (for example to R2 or your Mac). Turn on the provider's snapshot backups too.

## Rules

- Never put the upload token, `.env`, or any secret in the repository, in a chat or in a screenshot.
- Do not unpause the GitHub data-release workflow; releases stay manual.
- Do not enable the OpenAI pilot or any paid feature here. They are development-only and need the rights and approvals in DATA_RIGHTS.md and PRO_PLAN.md.
