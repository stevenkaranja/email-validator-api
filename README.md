# Email Validator API

A REST API that validates email addresses through 3 layers: syntax - MX record - deliverability verification. Returns a 0–100 score and actionable recommendation.

Built for GTM teams who need to clean lead lists before loading into a CRM or sending outbound sequences.

---

## What It Does

```
Input: john@stripe.com
         ↓
  [Layer 1] Syntax check      — valid format?
         ↓
  [Layer 2] MX record check   — does the domain accept email?
         ↓
  [Layer 3] API verification  — is this mailbox real? (Hunter.io / ZeroBounce)
         ↓
Output: score (0–100), deliverability, recommendation
```

---

## Stack

| Layer | Tool |
|---|---|
| API framework | Flask 3.0 |
| DNS checks | dnspython |
| Deliverability | Hunter.io API (free tier) |
| Secondary check | ZeroBounce (optional) |

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/stevenkaranja/email-validator-api
cd email-validator-api

# 2. Install
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
# Add your Hunter.io API key (optional — works without it)

# 4. Start the server
python app.py
```

---

## Endpoints

### `GET /validate?email=<email>`

Validate a single email.

```bash
curl "http://localhost:5000/validate?email=john@stripe.com"
```

**Response:**
```json
{
  "email": "john@stripe.com",
  "domain": "stripe.com",
  "score": 87,
  "deliverability": "High",
  "syntax_valid": true,
  "mx_valid": true,
  "is_disposable": false,
  "is_role_based": false,
  "api_status": "valid",
  "mx_host": "aspmx.l.google.com",
  "recommendation": "Send — high deliverability"
}
```

---

### `POST /validate/batch`

Validate up to 50 emails at once.

```bash
curl -X POST http://localhost:5000/validate/batch \
  -H "Content-Type: application/json" \
  -d '{"emails": ["john@stripe.com", "fake@mailinator.com", "info@hubspot.com"]}'
```

**Response:**
```json
{
  "summary": {
    "total": 3,
    "high_deliverability": 1,
    "medium_deliverability": 1,
    "low_deliverability": 1,
    "disposable": 1
  },
  "results": [...]
}
```

---

### `GET /health`

```bash
curl http://localhost:5000/health
# {"status": "ok", "service": "email-validator-api"}
```

---

## Scoring Logic

| Check | Points |
|---|---|
| Valid syntax | 20 |
| MX record found | 25 |
| API status: valid | 40 |
| API status: accept_all | 25 |
| Not disposable | 10 |
| Not role-based | 5 |

| Score | Deliverability |
|---|---|
| 80–100 | High — Send |
| 50–79 | Medium — Send with caution |
| 0–49 | Low — Skip |

---

## Author

**Stephen Karanja** — AI Automation & GTM Systems Engineer  
[stephenkaranja.vercel.app](https://stephenkaranja.vercel.app) · [LinkedIn](https://linkedin.com/in/steven-karanja)
