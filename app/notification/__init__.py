"""
Notification module for AI Daily News Bot.
"""

from app.notification.email_sender import (
    send_email,
    send_report,
    is_email_configured,
)

__all__ = [
    'send_email',
    'send_report',
    'is_email_configured',
]
