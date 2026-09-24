# Trading FAQ WhatsApp Bot

Rule-based trading education bot for WhatsApp. Answers questions about technical analysis, risk management, trading strategies, psychology, and macro economics.

## Quick Start

```bash
# 1. Clone / copy the project to your server
# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
nano .env   # fill in your values

# 5. Start
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `PROVIDER` | Yes | `meta` / `twilio` / `dialog360` |
| `META_PHONE_NUMBER_ID` | If meta | Your WhatsApp phone number ID |
| `META_ACCESS_TOKEN` | If meta | Permanent access token |
| `META_VERIFY_TOKEN` | If meta | Any string you choose for webhook verification |
| `META_APP_SECRET` | If meta | App secret for signature validation |
| `TWILIO_ACCOUNT_SID` | If twilio | Twilio account SID |
| `TWILIO_AUTH_TOKEN` | If twilio | Twilio auth token |
| `TWILIO_FROM_NUMBER` | If twilio | e.g. `whatsapp:+14155238886` |
| `DIALOG360_API_KEY` | If dialog360 | 360dialog API key |
| `MENTOR_NUMBER` | Optional | WhatsApp number to notify on mentor requests |
| `MENTOR_WEBHOOK` | Optional | HTTP URL to POST mentor notifications to |
| `MENTOR_MODE_TTL_HOURS` | Optional | Hours before mentor mode auto-expires (default: 24) |
| `MENTOR_AI_ENABLED` | Optional | `true` to enable AI mentor via Kiro Gateway |
| `KIRO_GATEWAY_URL` | If AI mentor | URL of your Kiro Gateway instance |
| `KIRO_GATEWAY_API_KEY` | If AI mentor | Kiro Gateway API key |
| `FAQ_CONFIG_PATH` | Optional | Path to faqs.yaml (default: `config/faqs.yaml`) |
| `LOG_LEVEL` | Optional | `DEBUG` / `INFO` / `WARNING` (default: `INFO`) |
| `ADMIN_TOKEN` | Optional | Token for `/reload` endpoint |

## Webhook Setup

### Meta Cloud API
1. Go to [Meta Developer Console](https://developers.facebook.com)
2. Create a WhatsApp Business app
3. Set webhook URL to: `https://your-server/webhook/meta`
4. Set verify token to match `META_VERIFY_TOKEN` in your `.env`
5. Subscribe to `messages` webhook field

### Twilio
1. Go to [Twilio Console](https://console.twilio.com)
2. Set webhook URL to: `https://your-server/webhook/twilio`

### 360dialog
1. Go to [360dialog Hub](https://hub.360dialog.com)
2. Set webhook URL to: `https://your-server/webhook/dialog360`

## Editing FAQs

Edit `config/faqs.yaml` — no code changes needed. Then reload:
```bash
curl -X POST https://your-server/reload \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"
```
Or just restart the server.

## Logs

- `logs/app.log` — all processed messages (JSON lines, rotates daily)
- `logs/unanswered.log` — messages that didn't match any FAQ (review to improve)

## Oracle Cloud Always Free Setup

Oracle Cloud Free Tier gives you a VM with 1 OCPU and 1 GB RAM — enough for this bot.

```bash
# 1. Create an Always Free VM (Ubuntu 22.04)
# 2. Open port 8000 in the security list (or use nginx on port 80/443)
# 3. SSH into the VM and run:

sudo apt update && sudo apt install -y python3-pip python3-venv nginx certbot python3-certbot-nginx

# 4. Clone/copy the project
# 5. Set up the bot (see Quick Start above)

# 6. Create a systemd service so it runs on boot:
sudo nano /etc/systemd/system/faqbot.service
```

Paste this into the service file (adjust paths):
```ini
[Unit]
Description=Trading FAQ WhatsApp Bot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Chatbot_whatsapp_faq
Environment="PATH=/home/ubuntu/Chatbot_whatsapp_faq/.venv/bin"
ExecStart=/home/ubuntu/Chatbot_whatsapp_faq/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable faqbot
sudo systemctl start faqbot

# Check it's running:
sudo systemctl status faqbot
curl http://localhost:8000/health
```

### Nginx + HTTPS (required for Meta webhooks)

```bash
# Configure nginx reverse proxy
sudo nano /etc/nginx/sites-available/faqbot
```

```nginx
server {
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/faqbot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com
```

## Bot Commands

Users can type these in WhatsApp:
- `menu` — see all topics
- `analyze` — start setup analysis (guided flow)
- `risk` — start position size calculator
- `mentor` / `coach` / `review` / `support` — request human mentor
- `resume` — return to automatic bot from mentor mode
- `disclaimer` — see the educational disclaimer
- `cancel` — cancel current analysis/risk flow
