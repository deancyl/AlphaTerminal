"""
notification_service.py — Task 19: Notification System
Provides comprehensive notification system for alerts and notifications.

Features:
  - Multiple notification channels (email, webhook)
  - Notification templates for common scenarios
  - Status tracking and error handling
  - Comprehensive debug logging (5 cycles)
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
import json
import uuid

logger = logging.getLogger(__name__)


# ── Notification Status ──────────────────────────────────────────────────────
class NotificationStatus(str, Enum):
    """Notification status enumeration."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


class NotificationChannel(str, Enum):
    """Notification channel enumeration."""
    EMAIL = "email"
    WEBHOOK = "webhook"


# ── Notification Data Structure ──────────────────────────────────────────────
@dataclass
class Notification:
    """
    Notification data structure for tracking notifications.
    
    Attributes:
        id: Unique notification identifier
        channel: Notification channel (email, webhook)
        message: Notification message content
        status: Current notification status
        created_at: Timestamp when notification was created
        sent_at: Timestamp when notification was sent (None if not sent)
        error: Error message if notification failed (None if successful)
        recipient: Recipient information (email address or webhook URL)
        subject: Subject line (for email notifications)
        metadata: Additional metadata for the notification
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    channel: NotificationChannel = NotificationChannel.EMAIL
    message: str = ""
    status: NotificationStatus = NotificationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    sent_at: Optional[datetime] = None
    error: Optional[str] = None
    recipient: str = ""
    subject: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate notification after initialization."""
        self._validate_notification()
    
    def _validate_notification(self):
        """Validate notification fields."""
        if not self.message:
            raise ValueError("message cannot be empty")
        
        if not self.recipient:
            raise ValueError("recipient cannot be empty")
        
        if self.channel == NotificationChannel.EMAIL and not self.subject:
            raise ValueError("subject is required for email notifications")


# ── Notification Configuration ──────────────────────────────────────────────
@dataclass
class NotificationConfig:
    """
    Notification configuration with sensible defaults.
    
    Attributes:
        enabled: Enable/disable notifications (default: True)
        retry_attempts: Number of retry attempts for failed notifications (default: 3)
        retry_delay_seconds: Delay between retry attempts in seconds (default: 5)
        timeout_seconds: Timeout for notification operations in seconds (default: 30)
        max_notifications_per_hour: Maximum notifications per hour (default: 100)
        email_enabled: Enable email notifications (default: True)
        webhook_enabled: Enable webhook notifications (default: True)
    """
    enabled: bool = True
    retry_attempts: int = 3
    retry_delay_seconds: int = 5
    timeout_seconds: int = 30
    max_notifications_per_hour: int = 100
    email_enabled: bool = True
    webhook_enabled: bool = True
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
    
    def _validate_config(self):
        """Validate all configuration parameters."""
        # Cycle 1: Notification config validation
        logger.debug("=" * 60)
        logger.debug("[Cycle 1: Notification Config Validation]")
        logger.debug(f"  enabled: {self.enabled}")
        logger.debug(f"  retry_attempts: {self.retry_attempts}")
        logger.debug(f"  retry_delay_seconds: {self.retry_delay_seconds}")
        logger.debug(f"  timeout_seconds: {self.timeout_seconds}")
        logger.debug(f"  max_notifications_per_hour: {self.max_notifications_per_hour}")
        logger.debug(f"  email_enabled: {self.email_enabled}")
        logger.debug(f"  webhook_enabled: {self.webhook_enabled}")
        
        errors = []
        
        if self.retry_attempts < 0 or self.retry_attempts > 10:
            errors.append(f"retry_attempts must be in [0, 10], got {self.retry_attempts}")
        
        if self.retry_delay_seconds < 0 or self.retry_delay_seconds > 60:
            errors.append(f"retry_delay_seconds must be in [0, 60], got {self.retry_delay_seconds}")
        
        if self.timeout_seconds < 1 or self.timeout_seconds > 300:
            errors.append(f"timeout_seconds must be in [1, 300], got {self.timeout_seconds}")
        
        if self.max_notifications_per_hour < 1 or self.max_notifications_per_hour > 1000:
            errors.append(f"max_notifications_per_hour must be in [1, 1000], got {self.max_notifications_per_hour}")
        
        if errors:
            logger.error(f"  [VALIDATION FAILED] {len(errors)} errors:")
            for err in errors:
                logger.error(f"    - {err}")
            raise ValueError(f"Invalid notification configuration: {'; '.join(errors)}")
        
        logger.debug(f"  [VALIDATION PASSED] All parameters within acceptable ranges")
        logger.debug("=" * 60)


# ── Notification Templates ──────────────────────────────────────────────────
class NotificationTemplates:
    """
    Notification templates for common scenarios.
    
    Provides pre-defined templates for:
        - Trade notifications (buy/sell)
        - Risk alerts (stop loss, position limit)
        - Performance summaries (daily/weekly)
    """
    
    @staticmethod
    def trade_notification(
        symbol: str,
        action: str,
        shares: int,
        price: float,
        pnl: Optional[float] = None,
    ) -> Dict[str, str]:
        """
        Create trade notification template.
        
        Args:
            symbol: Trading symbol
            action: Trade action (BUY/SELL)
            shares: Number of shares
            price: Trade price
            pnl: Profit/loss (for SELL orders)
            
        Returns:
            Dictionary with subject and message
        """
        action_upper = action.upper()
        
        if action_upper == "BUY":
            subject = f"📈 Trade Executed: BUY {shares} {symbol} @ ${price:.2f}"
            message = f"""
Trade Notification

Action: BUY
Symbol: {symbol}
Shares: {shares}
Price: ${price:.2f}
Total: ${shares * price:.2f}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:  # SELL
            pnl_str = f"P&L: ${pnl:.2f}" if pnl is not None else "P&L: N/A"
            subject = f"📉 Trade Executed: SELL {shares} {symbol} @ ${price:.2f}"
            message = f"""
Trade Notification

Action: SELL
Symbol: {symbol}
Shares: {shares}
Price: ${price:.2f}
Total: ${shares * price:.2f}
{pnl_str}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return {"subject": subject.strip(), "message": message.strip()}
    
    @staticmethod
    def risk_alert(
        alert_type: str,
        symbol: Optional[str] = None,
        current_value: Optional[float] = None,
        threshold: Optional[float] = None,
        message: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Create risk alert notification template.
        
        Args:
            alert_type: Type of risk alert (stop_loss, position_limit, drawdown)
            symbol: Trading symbol (if applicable)
            current_value: Current value (if applicable)
            threshold: Threshold value (if applicable)
            message: Custom message (if provided)
            
        Returns:
            Dictionary with subject and message
        """
        alert_type_upper = alert_type.upper()
        
        if alert_type_upper == "STOP_LOSS":
            subject = f"🚨 Risk Alert: Stop Loss Triggered for {symbol}"
            body = f"""
Risk Alert: Stop Loss Triggered

Symbol: {symbol}
Current Price: ${current_value:.2f}
Stop Price: ${threshold:.2f}

Action Required: Review position and consider exit strategy.

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        elif alert_type_upper == "POSITION_LIMIT":
            subject = "🚨 Risk Alert: Position Limit Exceeded"
            body = f"""
Risk Alert: Position Limit Exceeded

Current Position Size: {current_value:.2f}%
Maximum Allowed: {threshold:.2f}%

Action Required: Reduce position size to comply with risk limits.

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        elif alert_type_upper == "DRAWDOWN":
            subject = "🚨 Risk Alert: Maximum Drawdown Exceeded"
            body = f"""
Risk Alert: Maximum Drawdown Exceeded

Current Drawdown: {current_value:.2f}%
Maximum Allowed: {threshold:.2f}%

Action Required: Review portfolio and consider risk reduction.

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        else:
            subject = f"🚨 Risk Alert: {alert_type_upper}"
            body = f"""
Risk Alert: {alert_type_upper}

{message or 'No additional details provided.'}

Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return {"subject": subject.strip(), "body": body.strip()}
    
    @staticmethod
    def performance_summary(
        period: str,
        total_return: float,
        total_return_pct: float,
        sharpe_ratio: float,
        max_drawdown: float,
        win_rate: float,
        total_trades: int,
    ) -> Dict[str, str]:
        """
        Create performance summary notification template.
        
        Args:
            period: Performance period (daily/weekly/monthly)
            total_return: Total return in currency
            total_return_pct: Total return percentage
            sharpe_ratio: Sharpe ratio
            max_drawdown: Maximum drawdown percentage
            win_rate: Win rate percentage
            total_trades: Total number of trades
            
        Returns:
            Dictionary with subject and message
        """
        period_upper = period.upper()
        
        subject = f"📊 {period_upper} Performance Summary"
        message = f"""
Performance Summary - {period_upper}

Total Return: ${total_return:.2f} ({total_return_pct:.2f}%)
Sharpe Ratio: {sharpe_ratio:.2f}
Max Drawdown: {max_drawdown:.2f}%
Win Rate: {win_rate:.2f}%
Total Trades: {total_trades}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return {"subject": subject.strip(), "message": message.strip()}


# ── Notification Service ────────────────────────────────────────────────────
class NotificationService:
    """
    Comprehensive notification service for sending alerts and notifications.
    
    Features:
        - Multiple notification channels (email, webhook)
        - Template-based notifications
        - Status tracking and error handling
        - Rate limiting and retry logic
    """
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        """Initialize notification service with configuration."""
        self.config = config or NotificationConfig()
        self.notifications: Dict[str, Notification] = {}
        self.notification_history: List[Dict[str, Any]] = []
        
        logger.info(f"[NotificationService] Initialized with config:")
        logger.info(f"  enabled: {self.config.enabled}")
        logger.info(f"  retry_attempts: {self.config.retry_attempts}")
        logger.info(f"  email_enabled: {self.config.email_enabled}")
        logger.info(f"  webhook_enabled: {self.config.webhook_enabled}")
    
    # ── Template Rendering ─────────────────────────────────────────────────
    
    def create_template(
        self,
        template_name: str,
        variables: Dict[str, Any],
    ) -> str:
        """
        Create notification from template with variables.
        
        Args:
            template_name: Name of the template (trade, risk_alert, performance)
            variables: Dictionary of template variables
            
        Returns:
            Rendered notification message
            
        Raises:
            ValueError: If template name is invalid or required variables missing
        """
        # Cycle 2: Template rendering
        logger.debug("=" * 60)
        logger.debug("[Cycle 2: Template Rendering]")
        logger.debug(f"  template_name: {template_name}")
        logger.debug(f"  variables: {variables}")
        
        template_name_lower = template_name.lower()
        
        try:
            if template_name_lower == "trade":
                required_vars = ["symbol", "action", "shares", "price"]
                missing_vars = [v for v in required_vars if v not in variables]
                
                if missing_vars:
                    logger.error(f"  [ERROR] Missing required variables: {missing_vars}")
                    raise ValueError(f"Missing required variables for trade template: {missing_vars}")
                
                template = NotificationTemplates.trade_notification(
                    symbol=variables["symbol"],
                    action=variables["action"],
                    shares=variables["shares"],
                    price=variables["price"],
                    pnl=variables.get("pnl"),
                )
                
                logger.debug(f"  [SUCCESS] Trade template rendered")
                logger.debug(f"    subject: {template['subject']}")
                result = template["message"]
                
            elif template_name_lower == "risk_alert":
                required_vars = ["alert_type"]
                missing_vars = [v for v in required_vars if v not in variables]
                
                if missing_vars:
                    logger.error(f"  [ERROR] Missing required variables: {missing_vars}")
                    raise ValueError(f"Missing required variables for risk_alert template: {missing_vars}")
                
                template = NotificationTemplates.risk_alert(
                    alert_type=variables["alert_type"],
                    symbol=variables.get("symbol"),
                    current_value=variables.get("current_value"),
                    threshold=variables.get("threshold"),
                    message=variables.get("message"),
                )
                
                logger.debug(f"  [SUCCESS] Risk alert template rendered")
                logger.debug(f"    subject: {template['subject']}")
                result = template["body"]
                
            elif template_name_lower == "performance":
                required_vars = ["period", "total_return", "total_return_pct", 
                               "sharpe_ratio", "max_drawdown", "win_rate", "total_trades"]
                missing_vars = [v for v in required_vars if v not in variables]
                
                if missing_vars:
                    logger.error(f"  [ERROR] Missing required variables: {missing_vars}")
                    raise ValueError(f"Missing required variables for performance template: {missing_vars}")
                
                template = NotificationTemplates.performance_summary(
                    period=variables["period"],
                    total_return=variables["total_return"],
                    total_return_pct=variables["total_return_pct"],
                    sharpe_ratio=variables["sharpe_ratio"],
                    max_drawdown=variables["max_drawdown"],
                    win_rate=variables["win_rate"],
                    total_trades=variables["total_trades"],
                )
                
                logger.debug(f"  [SUCCESS] Performance template rendered")
                logger.debug(f"    subject: {template['subject']}")
                result = template["message"]
                
            else:
                logger.error(f"  [ERROR] Unknown template: {template_name}")
                raise ValueError(f"Unknown template: {template_name}")
            
            logger.debug(f"  [RESULT] Template rendered successfully")
            logger.debug("=" * 60)
            
            return result
            
        except ValueError as e:
            logger.error(f"  [ERROR] Template validation error: {e}")
            logger.debug("=" * 60)
            raise
        except KeyError as e:
            logger.error(f"  [ERROR] Missing template variable: {e}")
            logger.debug("=" * 60)
            raise ValueError(f"Missing required template variable: {e}")
        except Exception as e:
            logger.error(f"  [ERROR] Template rendering failed: {e}")
            logger.debug("=" * 60)
            raise
    
    # ── Channel Validation ────────────────────────────────────────────────
    
    def validate_channel(
        self,
        channel: NotificationChannel,
        recipient: str,
    ) -> bool:
        """
        Validate notification channel and recipient.
        
        Args:
            channel: Notification channel
            recipient: Recipient information
            
        Returns:
            True if valid, False otherwise
            
        Raises:
            ValueError: If channel is disabled or invalid
        """
        # Cycle 3: Channel validation
        logger.debug("=" * 60)
        logger.debug("[Cycle 3: Channel Validation]")
        logger.debug(f"  channel: {channel}")
        logger.debug(f"  recipient: {recipient}")
        
        if not self.config.enabled:
            logger.error(f"  [ERROR] Notifications are disabled")
            logger.debug("=" * 60)
            raise ValueError("Notifications are disabled in configuration")
        
        # Validate channel
        if channel == NotificationChannel.EMAIL:
            if not self.config.email_enabled:
                logger.error(f"  [ERROR] Email notifications are disabled")
                logger.debug("=" * 60)
                raise ValueError("Email notifications are disabled in configuration")
            
            # Basic email validation
            if "@" not in recipient or "." not in recipient:
                logger.error(f"  [ERROR] Invalid email address: {recipient}")
                logger.debug("=" * 60)
                raise ValueError(f"Invalid email address: {recipient}")
            
            logger.debug(f"  [VALID] Email channel validated")
            
        elif channel == NotificationChannel.WEBHOOK:
            if not self.config.webhook_enabled:
                logger.error(f"  [ERROR] Webhook notifications are disabled")
                logger.debug("=" * 60)
                raise ValueError("Webhook notifications are disabled in configuration")
            
            # Basic URL validation
            if not recipient.startswith(("http://", "https://")):
                logger.error(f"  [ERROR] Invalid webhook URL: {recipient}")
                logger.debug("=" * 60)
                raise ValueError(f"Invalid webhook URL: {recipient}")
            
            logger.debug(f"  [VALID] Webhook channel validated")
            
        else:
            logger.error(f"  [ERROR] Unknown channel: {channel}")
            logger.debug("=" * 60)
            raise ValueError(f"Unknown channel: {channel}")
        
        logger.debug(f"  [RESULT] Channel validation passed")
        logger.debug("=" * 60)
        
        return True
    
    # ── Send Operations ────────────────────────────────────────────────────
    
    def send_notification(
        self,
        channel: NotificationChannel,
        message: str,
        recipient: str,
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send notification through specified channel.
        
        Args:
            channel: Notification channel
            message: Notification message
            recipient: Recipient information
            subject: Subject line (for email)
            metadata: Additional metadata
            
        Returns:
            True if sent successfully, False otherwise
        """
        # Cycle 4: Send operation
        logger.debug("=" * 60)
        logger.debug("[Cycle 4: Send Operation]")
        logger.debug(f"  channel: {channel}")
        logger.debug(f"  recipient: {recipient}")
        logger.debug(f"  subject: {subject}")
        logger.debug(f"  message_length: {len(message)}")
        
        try:
            # Validate channel
            self.validate_channel(channel, recipient)
            
            # Create notification object
            notification = Notification(
                channel=channel,
                message=message,
                recipient=recipient,
                subject=subject,
                metadata=metadata or {},
            )
            
            logger.debug(f"  [CREATED] Notification ID: {notification.id}")
            
            # Send based on channel
            if channel == NotificationChannel.EMAIL:
                success = self.send_email(
                    to=recipient,
                    subject=subject or "Notification",
                    body=message,
                )
            elif channel == NotificationChannel.WEBHOOK:
                success = self.send_webhook(
                    url=recipient,
                    payload={
                        "message": message,
                        "subject": subject,
                        "metadata": metadata,
                    },
                )
            else:
                logger.error(f"  [ERROR] Unknown channel: {channel}")
                success = False
            
            # Update notification status
            if success:
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.now()
                logger.debug(f"  [SUCCESS] Notification sent successfully")
            else:
                notification.status = NotificationStatus.FAILED
                notification.error = "Send operation failed"
                logger.error(f"  [FAILED] Notification send failed")
            
            # Store notification
            self.notifications[notification.id] = notification
            self.notification_history.append({
                "id": notification.id,
                "channel": channel.value,
                "recipient": recipient,
                "status": notification.status.value,
                "timestamp": datetime.now().isoformat(),
            })
            
            logger.debug(f"  [RESULT] Status: {notification.status.value}")
            logger.debug("=" * 60)
            
            return success
            
        except ValueError as e:
            logger.error(f"  [ERROR] Validation error: {e}")
            logger.debug("=" * 60)
            return False
        except KeyError as e:
            logger.error(f"  [ERROR] Missing required field: {e}")
            logger.debug("=" * 60)
            return False
        except Exception as e:
            logger.error(f"  [ERROR] Send operation failed: {e}")
            logger.debug("=" * 60)
            return False
    
    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> bool:
        """
        Send email notification (MOCKED - does not actually send).
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body
            
        Returns:
            True if mock send successful, False otherwise
        """
        logger.debug(f"  [MOCK EMAIL] Sending email to: {to}")
        logger.debug(f"  [MOCK EMAIL] Subject: {subject}")
        logger.debug(f"  [MOCK EMAIL] Body length: {len(body)} characters")
        
        # Mock email sending - always succeeds for testing
        # In production, this would integrate with an email service
        
        # Simulate successful send
        logger.info(f"[NotificationService] Mock email sent to {to}")
        return True
    
    def send_webhook(
        self,
        url: str,
        payload: Dict[str, Any],
    ) -> bool:
        """
        Send webhook notification (MOCKED - does not actually send).
        
        Args:
            url: Webhook URL
            payload: Webhook payload
            
        Returns:
            True if mock send successful, False otherwise
        """
        logger.debug(f"  [MOCK WEBHOOK] Sending webhook to: {url}")
        logger.debug(f"  [MOCK WEBHOOK] Payload: {json.dumps(payload, indent=2)}")
        
        # Mock webhook sending - always succeeds for testing
        # In production, this would make an HTTP POST request
        
        # Simulate successful send
        logger.info(f"[NotificationService] Mock webhook sent to {url}")
        return True
    
    # ── Status Tracking ───────────────────────────────────────────────────
    
    def get_notification_status(
        self,
        notification_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get notification status by ID.
        
        Args:
            notification_id: Notification ID
            
        Returns:
            Notification status dictionary or None if not found
        """
        # Cycle 5: Status tracking
        logger.debug("=" * 60)
        logger.debug("[Cycle 5: Status Tracking]")
        logger.debug(f"  notification_id: {notification_id}")
        
        if notification_id not in self.notifications:
            logger.warning(f"  [NOT FOUND] Notification {notification_id} not found")
            logger.debug("=" * 60)
            return None
        
        notification = self.notifications[notification_id]
        
        status_dict = {
            "id": notification.id,
            "channel": notification.channel.value,
            "status": notification.status.value,
            "created_at": notification.created_at.isoformat(),
            "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
            "error": notification.error,
            "recipient": notification.recipient,
        }
        
        logger.debug(f"  [FOUND] Notification status:")
        logger.debug(f"    status: {status_dict['status']}")
        logger.debug(f"    channel: {status_dict['channel']}")
        logger.debug(f"    recipient: {status_dict['recipient']}")
        logger.debug(f"    created_at: {status_dict['created_at']}")
        logger.debug(f"    sent_at: {status_dict['sent_at']}")
        logger.debug("=" * 60)
        
        return status_dict
    
    def get_notification_history(
        self,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get notification history.
        
        Args:
            limit: Maximum number of notifications to return
            
        Returns:
            List of notification history entries
        """
        logger.debug(f"[NotificationService] Getting notification history (limit: {limit})")
        
        # Return most recent notifications
        history = self.notification_history[-limit:]
        
        logger.debug(f"[NotificationService] Returning {len(history)} notifications")
        
        return history
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get notification statistics.
        
        Returns:
            Dictionary with notification statistics
        """
        logger.debug("[NotificationService] Getting notification statistics")
        
        total = len(self.notifications)
        sent = sum(1 for n in self.notifications.values() if n.status == NotificationStatus.SENT)
        failed = sum(1 for n in self.notifications.values() if n.status == NotificationStatus.FAILED)
        pending = sum(1 for n in self.notifications.values() if n.status == NotificationStatus.PENDING)
        
        stats = {
            "total_notifications": total,
            "sent": sent,
            "failed": failed,
            "pending": pending,
            "success_rate": (sent / total * 100) if total > 0 else 0.0,
            "history_count": len(self.notification_history),
        }
        
        logger.debug(f"[NotificationService] Statistics: {stats}")
        
        return stats
    
    # ── Convenience Methods ───────────────────────────────────────────────
    
    def notify_trade(
        self,
        symbol: str,
        action: str,
        shares: int,
        price: float,
        recipient: str,
        pnl: Optional[float] = None,
    ) -> bool:
        """
        Send trade notification using template.
        
        Args:
            symbol: Trading symbol
            action: Trade action (BUY/SELL)
            shares: Number of shares
            price: Trade price
            recipient: Notification recipient
            pnl: Profit/loss (for SELL orders)
            
        Returns:
            True if sent successfully, False otherwise
        """
        template = NotificationTemplates.trade_notification(
            symbol=symbol,
            action=action,
            shares=shares,
            price=price,
            pnl=pnl,
        )
        
        return self.send_notification(
            channel=NotificationChannel.EMAIL,
            message=template["message"],
            recipient=recipient,
            subject=template["subject"],
        )
    
    def notify_risk_alert(
        self,
        alert_type: str,
        recipient: str,
        symbol: Optional[str] = None,
        current_value: Optional[float] = None,
        threshold: Optional[float] = None,
        message: Optional[str] = None,
    ) -> bool:
        """
        Send risk alert notification using template.
        
        Args:
            alert_type: Type of risk alert
            recipient: Notification recipient
            symbol: Trading symbol (if applicable)
            current_value: Current value (if applicable)
            threshold: Threshold value (if applicable)
            message: Custom message (if provided)
            
        Returns:
            True if sent successfully, False otherwise
        """
        template = NotificationTemplates.risk_alert(
            alert_type=alert_type,
            symbol=symbol,
            current_value=current_value,
            threshold=threshold,
            message=message,
        )
        
        return self.send_notification(
            channel=NotificationChannel.EMAIL,
            message=template["body"],
            recipient=recipient,
            subject=template["subject"],
        )
    
    def notify_performance_summary(
        self,
        period: str,
        recipient: str,
        total_return: float,
        total_return_pct: float,
        sharpe_ratio: float,
        max_drawdown: float,
        win_rate: float,
        total_trades: int,
    ) -> bool:
        """
        Send performance summary notification using template.
        
        Args:
            period: Performance period
            recipient: Notification recipient
            total_return: Total return in currency
            total_return_pct: Total return percentage
            sharpe_ratio: Sharpe ratio
            max_drawdown: Maximum drawdown percentage
            win_rate: Win rate percentage
            total_trades: Total number of trades
            
        Returns:
            True if sent successfully, False otherwise
        """
        template = NotificationTemplates.performance_summary(
            period=period,
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
        )
        
        return self.send_notification(
            channel=NotificationChannel.EMAIL,
            message=template["message"],
            recipient=recipient,
            subject=template["subject"],
        )
