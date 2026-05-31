"""
Core email validation logic.
3 layers: syntax → MX record → API verification.
"""
import os
import re
import requests

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

# Common disposable email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "fakeinbox.com", "trashmail.com", "yopmail.com", "sharklasers.com",
    "spam4.me", "getairmail.com", "dispostable.com", "maildrop.cc",
}

# Common role-based prefixes (lower deliverability)
ROLE_PREFIXES = {
    "info", "admin", "support", "hello", "contact", "sales", "help",
    "noreply", "no-reply", "team", "office", "hr", "finance", "billing",
}


def validate_syntax(email: str) -> dict:
    """Check if email matches a valid format."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    valid = bool(re.match(pattern, email))
    return {
        "valid": valid,
        "reason": "" if valid else "Invalid email format",
    }


def validate_mx(domain: str) -> dict:
    """Check if the domain has valid MX records."""
    if not DNS_AVAILABLE:
        return {"valid": True, "reason": "DNS check skipped (dnspython not available)"}
    try:
        records = dns.resolver.resolve(domain, "MX")
        mx = str(records[0].exchange).rstrip(".")
        return {"valid": True, "mx_host": mx}
    except Exception:
        return {"valid": False, "reason": f"No MX records found for {domain}"}


def validate_via_hunter(email: str) -> dict:
    """Verify email deliverability via Hunter.io."""
    api_key = os.getenv("HUNTER_API_KEY", "")
    if not api_key:
        return {"status": "unknown", "score": None, "source": "skipped"}
    try:
        resp = requests.get(
            "https://api.hunter.io/v2/email-verifier",
            params={"email": email, "api_key": api_key},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            return {
                "status": data.get("status", "unknown"),
                "score": data.get("score", None),
                "smtp_check": data.get("smtp_server", False),
                "source": "hunter",
            }
    except Exception:
        pass
    return {"status": "unknown", "score": None, "source": "error"}


def validate_via_zerobounce(email: str) -> dict:
    """Verify email via ZeroBounce (optional secondary check)."""
    api_key = os.getenv("ZEROBOUNCE_API_KEY", "")
    if not api_key:
        return {"status": "unknown", "source": "skipped"}
    try:
        resp = requests.get(
            "https://api.zerobounce.net/v2/validate",
            params={"api_key": api_key, "email": email},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "status": data.get("status", "unknown"),
                "sub_status": data.get("sub_status", ""),
                "source": "zerobounce",
            }
    except Exception:
        pass
    return {"status": "unknown", "source": "error"}


def score_email(checks: dict) -> tuple[int, str]:
    """
    Score an email 0–100 based on validation checks.
    Returns (score, deliverability_label).
    """
    score = 0

    if checks.get("syntax", {}).get("valid"):
        score += 20

    if checks.get("mx", {}).get("valid"):
        score += 25

    api_status = checks.get("api_verification", {}).get("status", "unknown")
    api_score = checks.get("api_verification", {}).get("score")

    if api_status == "valid":
        score += 40
    elif api_status == "accept_all":
        score += 25
    elif api_status == "unknown":
        score += 10

    if api_score:
        score = min(100, score + int(api_score * 0.15))

    if not checks.get("is_disposable"):
        score += 10

    if not checks.get("is_role_based"):
        score += 5

    if score >= 80:
        label = "High"
    elif score >= 50:
        label = "Medium"
    else:
        label = "Low"

    return score, label


def validate_email(email: str) -> dict:
    """
    Run the full 3-layer validation pipeline on a single email.
    Returns a structured result dict.
    """
    email = email.strip().lower()
    parts = email.split("@")
    domain = parts[1] if len(parts) == 2 else ""
    prefix = parts[0] if parts else ""

    is_disposable = domain in DISPOSABLE_DOMAINS
    is_role_based = any(prefix.startswith(r) for r in ROLE_PREFIXES)

    checks = {
        "syntax": validate_syntax(email),
        "mx": validate_mx(domain) if domain else {"valid": False, "reason": "No domain"},
        "is_disposable": is_disposable,
        "is_role_based": is_role_based,
    }

    # Only hit API if syntax + MX pass
    if checks["syntax"]["valid"] and checks["mx"]["valid"]:
        hunter_result = validate_via_hunter(email)
        zb_result = validate_via_zerobounce(email)
        checks["api_verification"] = hunter_result
        checks["secondary_verification"] = zb_result
    else:
        checks["api_verification"] = {"status": "skipped", "score": None, "source": "skipped"}
        checks["secondary_verification"] = {"status": "skipped", "source": "skipped"}

    score, deliverability = score_email(checks)

    return {
        "email": email,
        "domain": domain,
        "score": score,
        "deliverability": deliverability,
        "syntax_valid": checks["syntax"]["valid"],
        "mx_valid": checks["mx"]["valid"],
        "is_disposable": is_disposable,
        "is_role_based": is_role_based,
        "api_status": checks["api_verification"].get("status", "unknown"),
        "api_source": checks["api_verification"].get("source", "none"),
        "mx_host": checks["mx"].get("mx_host", ""),
        "recommendation": _recommendation(score, is_disposable),
    }


def _recommendation(score: int, is_disposable: bool) -> str:
    if is_disposable:
        return "Block — disposable email address"
    if score >= 80:
        return "Send — high deliverability"
    if score >= 50:
        return "Send with caution — medium confidence"
    return "Skip — low deliverability risk"
