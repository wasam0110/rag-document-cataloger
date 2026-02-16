"""
Email service for sending verification codes.

Handles generating random numeric codes, computing expiry timestamps,
and delivering styled HTML emails via SMTP (Gmail by default).
"""

import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.logging import logger


def generate_verification_code(length: int = 6) -> str:
    """Generate a random numeric verification code (e.g. '482917').

    Args:
        length: Number of digits in the code (default 6).
    """
    return ''.join(random.choices(string.digits, k=length))


def get_expiry_time(minutes: int = 10) -> str:
    """Return a formatted timestamp ``minutes`` from now.

    The result is stored in the DB and later compared with
    ``datetime('now')`` in SQLite to check expiration.
    """
    expiry = datetime.now() + timedelta(minutes=minutes)
    return expiry.strftime('%Y-%m-%d %H:%M:%S')


def send_verification_email(to_email: str, code: str) -> bool:
    """Send a verification code email with both plain-text and HTML parts.

    Uses SMTP settings from ``app.core.config.settings``.
    Returns True on success, False on any failure.
    """
    try:
        # Build a multipart/alternative message so mail clients can choose
        # between the plain-text fallback and the styled HTML version.
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Your Verification Code - RAG Document Cataloger'
        msg['From'] = settings.smtp_from_email
        msg['To'] = to_email
        
        # ── Plain-text body (fallback for text-only clients) ────────
        text = f"""
Hello,

Your verification code is: {code}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.

Best regards,
RAG Document Cataloger Team
        """
        
        # ── HTML body (styled version shown by modern mail clients) ─
        html = f"""
<html>
<head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4a7c59, #3d6b4a);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .content {{
            padding: 40px 30px;
        }}
        .code-box {{
            background-color: #f8f9fa;
            border: 2px solid #4a7c59;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 30px 0;
        }}
        .code {{
            font-size: 32px;
            font-weight: bold;
            color: #4a7c59;
            letter-spacing: 5px;
            font-family: 'Courier New', monospace;
        }}
        .footer {{
            background-color: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>RAG Document Cataloger</h1>
            <p>Email Verification</p>
        </div>
        <div class="content">
            <h2>Your Verification Code</h2>
            <p>Use the code below to complete your login:</p>
            <div class="code-box">
                <div class="code">{code}</div>
            </div>
            <p><strong>This code will expire in 10 minutes.</strong></p>
            <p>If you didn't request this code, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>© 2026 RAG Document Cataloger. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
        """
        
        # Attach both representations; the mail client picks the best one
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # ── Deliver the message via SMTP (STARTTLS on port 587) ─────
        with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
            server.starttls()                                       # Upgrade to encrypted connection
            server.login(settings.smtp_username, settings.smtp_password)  # Authenticate
            server.send_message(msg)                                # Send
        
        logger.info(f"Verification email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending verification email: {e}")
        return False
