"""
Email sender module for AI Daily News Bot.
Sends reports via SMTP with auto-detection of email provider.
"""

import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from typing import Optional, List

import markdown2

from app.config import settings


logger = logging.getLogger(__name__)


# SMTP 服务器配置（自动识别）
SMTP_CONFIGS = {
    # QQ邮箱
    "qq.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    "foxmail.com": {"server": "smtp.qq.com", "port": 465, "ssl": True},
    # 网易邮箱
    "163.com": {"server": "smtp.163.com", "port": 465, "ssl": True},
    "126.com": {"server": "smtp.126.com", "port": 465, "ssl": True},
    # Gmail
    "gmail.com": {"server": "smtp.gmail.com", "port": 587, "ssl": False},
    # Outlook
    "outlook.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "hotmail.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    "live.com": {"server": "smtp-mail.outlook.com", "port": 587, "ssl": False},
    # 新浪
    "sina.com": {"server": "smtp.sina.com", "port": 465, "ssl": True},
    # 搜狐
    "sohu.com": {"server": "smtp.sohu.com", "port": 465, "ssl": True},
    # 阿里云
    "aliyun.com": {"server": "smtp.aliyun.com", "port": 465, "ssl": True},
    # 139邮箱
    "139.com": {"server": "smtp.139.com", "port": 465, "ssl": True},
}


def is_email_configured() -> bool:
    """Check if email is properly configured."""
    return bool(
        settings.email_enabled and
        settings.email_sender and
        settings.email_password
    )


def send_email(
    content: str,
    subject: Optional[str] = None,
    content_is_html: bool = False,
) -> bool:
    """
    Send email via SMTP.

    Args:
        content: Email content (Markdown or HTML)
        subject: Email subject (auto-generated if None)
        content_is_html: Whether content is already HTML

    Returns:
        True if sent successfully, False otherwise
    """
    if not is_email_configured():
        logger.warning("Email not configured or disabled, skipping")
        return False

    sender = settings.email_sender
    password = settings.email_password
    receivers = settings.email_receiver_list
    sender_name = settings.email_sender_name

    if not receivers:
        logger.warning("No email receivers configured")
        return False

    try:
        # Generate subject
        if subject is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
            subject = f"AI技术日报 - {date_str}"

        # Convert Markdown to HTML
        if content_is_html:
            html_content = content
        else:
            html_content = markdown2.markdown(
                content,
                extras=['tables', 'fenced-code-blocks', 'code-friendly']
            )

        # Build email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = formataddr((sender_name, sender))
        msg['To'] = ', '.join(receivers)

        # Add both plain text and HTML versions
        text_part = MIMEText(content, 'plain', 'utf-8')
        html_part = MIMEText(html_content, 'html', 'utf-8')

        msg.attach(text_part)
        msg.attach(html_part)

        # Determine SMTP settings
        if settings.email_smtp_server:
            smtp_server = settings.email_smtp_server
            smtp_port = settings.email_smtp_port
            use_ssl = smtp_port == 465
        else:
            # Auto-detect SMTP config from email domain
            domain = sender.split('@')[-1].lower()
            smtp_config = SMTP_CONFIGS.get(domain)

            if smtp_config:
                smtp_server = smtp_config['server']
                smtp_port = smtp_config['port']
                use_ssl = smtp_config['ssl']
                logger.info(f"Auto-detected SMTP: {domain} -> {smtp_server}:{smtp_port}")
            else:
                # Unknown domain, try generic config
                smtp_server = f"smtp.{domain}"
                smtp_port = 465
                use_ssl = True
                logger.warning(f"Unknown email domain {domain}, trying {smtp_server}:{smtp_port}")

        # Connect and send
        if use_ssl:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()

        server.login(sender, password)
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent successfully to {len(receivers)} recipient(s)")
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("Email authentication failed - check email and password/app password")
        return False
    except smtplib.SMTPConnectError as e:
        logger.error(f"Failed to connect to SMTP server: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def send_report(report_content: str, report_date: Optional[str] = None) -> bool:
    """
    Send daily report via email.

    Args:
        report_content: Markdown report content
        report_date: Report date string (optional)

    Returns:
        True if sent successfully, False otherwise
    """
    if report_date:
        subject = f"AI技术日报 - {report_date}"
    else:
        subject = None

    return send_email(report_content, subject)
