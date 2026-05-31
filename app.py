"""
Email Validator API
===================
Flask REST API for email validation, MX checks, and deliverability scoring.

Endpoints:
    GET  /validate?email=<email>
    POST /validate/batch         { "emails": ["a@b.com", ...] }
    GET  /health
"""
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from api import validate_email

load_dotenv()

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "email-validator-api"})


@app.route("/validate", methods=["GET"])
def validate_single():
    """
    Validate a single email address.

    Query params:
        email (required) — the email to validate

    Example:
        GET /validate?email=john@stripe.com
    """
    email = request.args.get("email", "").strip()

    if not email:
        return jsonify({"error": "Missing required param: email"}), 400

    result = validate_email(email)
    return jsonify(result)


@app.route("/validate/batch", methods=["POST"])
def validate_batch():
    """
    Validate up to 50 emails in one request.

    Body (JSON):
        { "emails": ["a@b.com", "c@d.com"] }

    Example:
        POST /validate/batch
        { "emails": ["john@stripe.com", "fake@mailinator.com"] }
    """
    data = request.get_json(silent=True)
    if not data or "emails" not in data:
        return jsonify({"error": "Body must be JSON with an 'emails' array"}), 400

    emails = data["emails"]
    if not isinstance(emails, list):
        return jsonify({"error": "'emails' must be an array"}), 400
    if len(emails) > 50:
        return jsonify({"error": "Maximum 50 emails per batch request"}), 400

    results = [validate_email(e) for e in emails if e]

    summary = {
        "total": len(results),
        "high_deliverability": len([r for r in results if r["deliverability"] == "High"]),
        "medium_deliverability": len([r for r in results if r["deliverability"] == "Medium"]),
        "low_deliverability": len([r for r in results if r["deliverability"] == "Low"]),
        "disposable": len([r for r in results if r["is_disposable"]]),
    }

    return jsonify({"summary": summary, "results": results})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    print(f"\n Email Validator API running on http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
