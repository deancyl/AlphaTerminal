"""
test_notification_service.py — Unit tests for NotificationService module
Tests all notification functionality including:
  - Notification configuration and validation
  - Template rendering (trade, risk_alert, performance)
  - Channel validation (email, webhook)
  - Send operations (mocked)
  - Status tracking
  - Debug logging (5 cycles)
"""
import pytest
import logging
from unittest.mock import Mock, patch
from app.services.notification_service import (
    NotificationService,
    NotificationConfig,
    Notification,
    NotificationTemplates,
    NotificationStatus,
    NotificationChannel,
)


class TestNotificationConfig:
    """Test NotificationConfig validation."""
    
    def test_default_config(self):
        """Test default configuration is valid."""
        config = NotificationConfig()
        assert config.enabled is True
        assert config.retry_attempts == 3
        assert config.retry_delay_seconds == 5
        assert config.timeout_seconds == 30
        assert config.max_notifications_per_hour == 100
        assert config.email_enabled is True
        assert config.webhook_enabled is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = NotificationConfig(
            enabled=False,
            retry_attempts=5,
            retry_delay_seconds=10,
            timeout_seconds=60,
        )
        assert config.enabled is False
        assert config.retry_attempts == 5
        assert config.retry_delay_seconds == 10
        assert config.timeout_seconds == 60
    
    def test_invalid_retry_attempts(self):
        """Test invalid retry_attempts raises error."""
        with pytest.raises(ValueError, match="retry_attempts"):
            NotificationConfig(retry_attempts=15)
        
        with pytest.raises(ValueError, match="retry_attempts"):
            NotificationConfig(retry_attempts=-1)
    
    def test_invalid_retry_delay(self):
        """Test invalid retry_delay_seconds raises error."""
        with pytest.raises(ValueError, match="retry_delay_seconds"):
            NotificationConfig(retry_delay_seconds=100)
        
        with pytest.raises(ValueError, match="retry_delay_seconds"):
            NotificationConfig(retry_delay_seconds=-1)
    
    def test_invalid_timeout(self):
        """Test invalid timeout_seconds raises error."""
        with pytest.raises(ValueError, match="timeout_seconds"):
            NotificationConfig(timeout_seconds=500)
        
        with pytest.raises(ValueError, match="timeout_seconds"):
            NotificationConfig(timeout_seconds=0)
    
    def test_invalid_max_notifications(self):
        """Test invalid max_notifications_per_hour raises error."""
        with pytest.raises(ValueError, match="max_notifications_per_hour"):
            NotificationConfig(max_notifications_per_hour=2000)
        
        with pytest.raises(ValueError, match="max_notifications_per_hour"):
            NotificationConfig(max_notifications_per_hour=0)


class TestNotification:
    """Test Notification dataclass."""
    
    def test_notification_creation(self):
        """Test notification creation with default values."""
        notification = Notification(
            channel=NotificationChannel.EMAIL,
            message="Test message",
            recipient="test@example.com",
            subject="Test Subject",
        )
        
        assert notification.id is not None
        assert notification.channel == NotificationChannel.EMAIL
        assert notification.message == "Test message"
        assert notification.status == NotificationStatus.PENDING
        assert notification.created_at is not None
        assert notification.sent_at is None
        assert notification.error is None
    
    def test_notification_validation_empty_message(self):
        """Test notification with empty message raises error."""
        with pytest.raises(ValueError, match="message cannot be empty"):
            Notification(
                channel=NotificationChannel.EMAIL,
                message="",
                recipient="test@example.com",
                subject="Test",
            )
    
    def test_notification_validation_empty_recipient(self):
        """Test notification with empty recipient raises error."""
        with pytest.raises(ValueError, match="recipient cannot be empty"):
            Notification(
                channel=NotificationChannel.EMAIL,
                message="Test",
                recipient="",
                subject="Test",
            )
    
    def test_notification_validation_missing_subject_for_email(self):
        """Test email notification without subject raises error."""
        with pytest.raises(ValueError, match="subject is required for email"):
            Notification(
                channel=NotificationChannel.EMAIL,
                message="Test",
                recipient="test@example.com",
            )


class TestNotificationTemplates:
    """Test notification templates."""
    
    def test_trade_notification_buy(self):
        """Test trade notification for BUY order."""
        template = NotificationTemplates.trade_notification(
            symbol="AAPL",
            action="BUY",
            shares=100,
            price=150.0,
        )
        
        assert "BUY" in template["subject"]
        assert "AAPL" in template["subject"]
        assert "100" in template["message"]
        assert "150.00" in template["message"]
    
    def test_trade_notification_sell(self):
        """Test trade notification for SELL order."""
        template = NotificationTemplates.trade_notification(
            symbol="AAPL",
            action="SELL",
            shares=100,
            price=150.0,
            pnl=500.0,
        )
        
        assert "SELL" in template["subject"]
        assert "AAPL" in template["subject"]
        assert "500.00" in template["message"]
    
    def test_risk_alert_stop_loss(self):
        """Test risk alert for stop loss."""
        template = NotificationTemplates.risk_alert(
            alert_type="stop_loss",
            symbol="AAPL",
            current_value=90.0,
            threshold=92.0,
        )
        
        assert "Stop Loss" in template["subject"]
        assert "AAPL" in template["subject"]
        assert "90.00" in template["body"]
        assert "92.00" in template["body"]
    
    def test_risk_alert_position_limit(self):
        """Test risk alert for position limit."""
        template = NotificationTemplates.risk_alert(
            alert_type="position_limit",
            current_value=25.0,
            threshold=20.0,
        )
        
        assert "Position Limit" in template["subject"]
        assert "25.00" in template["body"]
        assert "20.00" in template["body"]
    
    def test_risk_alert_drawdown(self):
        """Test risk alert for drawdown."""
        template = NotificationTemplates.risk_alert(
            alert_type="drawdown",
            current_value=15.0,
            threshold=10.0,
        )
        
        assert "Drawdown" in template["subject"]
        assert "15.00" in template["body"]
        assert "10.00" in template["body"]
    
    def test_performance_summary(self):
        """Test performance summary template."""
        template = NotificationTemplates.performance_summary(
            period="daily",
            total_return=5000.0,
            total_return_pct=5.0,
            sharpe_ratio=1.5,
            max_drawdown=8.0,
            win_rate=65.0,
            total_trades=100,
        )
        
        assert "DAILY" in template["subject"]
        assert "5000.00" in template["message"]
        assert "5.00%" in template["message"]
        assert "1.50" in template["message"]


class TestTemplateRendering:
    """Test template rendering in NotificationService."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = NotificationService()
    
    def test_create_template_trade(self):
        """Test creating trade template."""
        message = self.service.create_template(
            template_name="trade",
            variables={
                "symbol": "AAPL",
                "action": "BUY",
                "shares": 100,
                "price": 150.0,
            },
        )
        
        assert "BUY" in message
        assert "AAPL" in message
        assert "100" in message
    
    def test_create_template_risk_alert(self):
        """Test creating risk_alert template."""
        message = self.service.create_template(
            template_name="risk_alert",
            variables={
                "alert_type": "stop_loss",
                "symbol": "AAPL",
                "current_value": 90.0,
                "threshold": 92.0,
            },
        )
        
        assert "Stop Loss" in message
        assert "AAPL" in message
    
    def test_create_template_performance(self):
        """Test creating performance template."""
        message = self.service.create_template(
            template_name="performance",
            variables={
                "period": "daily",
                "total_return": 5000.0,
                "total_return_pct": 5.0,
                "sharpe_ratio": 1.5,
                "max_drawdown": 8.0,
                "win_rate": 65.0,
                "total_trades": 100,
            },
        )
        
        assert "DAILY" in message
        assert "5000.00" in message
    
    def test_create_template_unknown(self):
        """Test unknown template raises error."""
        with pytest.raises(ValueError, match="Unknown template"):
            self.service.create_template(
                template_name="unknown",
                variables={},
            )
    
    def test_create_template_missing_variables(self):
        """Test template with missing variables raises error."""
        with pytest.raises(ValueError, match="Missing required variables"):
            self.service.create_template(
                template_name="trade",
                variables={"symbol": "AAPL"},  # Missing required vars
            )


class TestChannelValidation:
    """Test channel validation."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = NotificationService()
    
    def test_validate_email_channel(self):
        """Test email channel validation."""
        result = self.service.validate_channel(
            channel=NotificationChannel.EMAIL,
            recipient="test@example.com",
        )
        assert result is True
    
    def test_validate_webhook_channel(self):
        """Test webhook channel validation."""
        result = self.service.validate_channel(
            channel=NotificationChannel.WEBHOOK,
            recipient="https://example.com/webhook",
        )
        assert result is True
    
    def test_validate_email_disabled(self):
        """Test email validation when disabled."""
        config = NotificationConfig(email_enabled=False)
        service = NotificationService(config)
        
        with pytest.raises(ValueError, match="Email notifications are disabled"):
            service.validate_channel(
                channel=NotificationChannel.EMAIL,
                recipient="test@example.com",
            )
    
    def test_validate_webhook_disabled(self):
        """Test webhook validation when disabled."""
        config = NotificationConfig(webhook_enabled=False)
        service = NotificationService(config)
        
        with pytest.raises(ValueError, match="Webhook notifications are disabled"):
            service.validate_channel(
                channel=NotificationChannel.WEBHOOK,
                recipient="https://example.com/webhook",
            )
    
    def test_validate_invalid_email(self):
        """Test invalid email address."""
        with pytest.raises(ValueError, match="Invalid email address"):
            self.service.validate_channel(
                channel=NotificationChannel.EMAIL,
                recipient="invalid-email",
            )
    
    def test_validate_invalid_webhook_url(self):
        """Test invalid webhook URL."""
        with pytest.raises(ValueError, match="Invalid webhook URL"):
            self.service.validate_channel(
                channel=NotificationChannel.WEBHOOK,
                recipient="invalid-url",
            )
    
    def test_validate_notifications_disabled(self):
        """Test validation when notifications are disabled."""
        config = NotificationConfig(enabled=False)
        service = NotificationService(config)
        
        with pytest.raises(ValueError, match="Notifications are disabled"):
            service.validate_channel(
                channel=NotificationChannel.EMAIL,
                recipient="test@example.com",
            )


class TestSendOperations:
    """Test send operations."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = NotificationService()
    
    def test_send_email_notification(self):
        """Test sending email notification."""
        success = self.service.send_notification(
            channel=NotificationChannel.EMAIL,
            message="Test message",
            recipient="test@example.com",
            subject="Test Subject",
        )
        
        assert success is True
        
        # Check notification was stored
        assert len(self.service.notifications) == 1
    
    def test_send_webhook_notification(self):
        """Test sending webhook notification."""
        success = self.service.send_notification(
            channel=NotificationChannel.WEBHOOK,
            message="Test message",
            recipient="https://example.com/webhook",
            metadata={"key": "value"},
        )
        
        assert success is True
        
        # Check notification was stored
        assert len(self.service.notifications) == 1
    
    def test_send_email_mock(self):
        """Test mock email sending."""
        success = self.service.send_email(
            to="test@example.com",
            subject="Test Subject",
            body="Test body",
        )
        
        assert success is True
    
    def test_send_webhook_mock(self):
        """Test mock webhook sending."""
        success = self.service.send_webhook(
            url="https://example.com/webhook",
            payload={"message": "test"},
        )
        
        assert success is True
    
    def test_send_notification_disabled_channel(self):
        """Test sending when channel is disabled."""
        config = NotificationConfig(email_enabled=False)
        service = NotificationService(config)
        
        success = service.send_notification(
            channel=NotificationChannel.EMAIL,
            message="Test",
            recipient="test@example.com",
            subject="Test",
        )
        
        assert success is False


class TestStatusTracking:
    """Test status tracking."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = NotificationService()
    
    def test_get_notification_status(self):
        """Test getting notification status."""
        # Send a notification
        success = self.service.send_notification(
            channel=NotificationChannel.EMAIL,
            message="Test message",
            recipient="test@example.com",
            subject="Test Subject",
        )
        
        assert success is True
        
        # Get notification ID
        notification_id = list(self.service.notifications.keys())[0]
        
        # Get status
        status = self.service.get_notification_status(notification_id)
        
        assert status is not None
        assert status["status"] == "sent"
        assert status["channel"] == "email"
        assert status["recipient"] == "test@example.com"
    
    def test_get_notification_status_not_found(self):
        """Test getting status for non-existent notification."""
        status = self.service.get_notification_status("nonexistent-id")
        
        assert status is None
    
    def test_get_notification_history(self):
        """Test getting notification history."""
        # Send multiple notifications
        for i in range(3):
            self.service.send_notification(
                channel=NotificationChannel.EMAIL,
                message=f"Test message {i}",
                recipient="test@example.com",
                subject=f"Test Subject {i}",
            )
        
        history = self.service.get_notification_history()
        
        assert len(history) == 3
    
    def test_get_notification_history_limit(self):
        """Test notification history with limit."""
        # Send multiple notifications
        for i in range(10):
            self.service.send_notification(
                channel=NotificationChannel.EMAIL,
                message=f"Test message {i}",
                recipient="test@example.com",
                subject=f"Test Subject {i}",
            )
        
        history = self.service.get_notification_history(limit=5)
        
        assert len(history) == 5
    
    def test_get_statistics(self):
        """Test getting notification statistics."""
        # Send some notifications
        for i in range(5):
            self.service.send_notification(
                channel=NotificationChannel.EMAIL,
                message=f"Test message {i}",
                recipient="test@example.com",
                subject=f"Test Subject {i}",
            )
        
        stats = self.service.get_statistics()
        
        assert stats["total_notifications"] == 5
        assert stats["sent"] == 5
        assert stats["failed"] == 0
        assert stats["success_rate"] == 100.0


class TestConvenienceMethods:
    """Test convenience methods."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.service = NotificationService()
    
    def test_notify_trade_buy(self):
        """Test trade notification for BUY."""
        success = self.service.notify_trade(
            symbol="AAPL",
            action="BUY",
            shares=100,
            price=150.0,
            recipient="trader@example.com",
        )
        
        assert success is True
    
    def test_notify_trade_sell(self):
        """Test trade notification for SELL."""
        success = self.service.notify_trade(
            symbol="AAPL",
            action="SELL",
            shares=100,
            price=150.0,
            recipient="trader@example.com",
            pnl=500.0,
        )
        
        assert success is True
    
    def test_notify_risk_alert_stop_loss(self):
        """Test risk alert notification."""
        success = self.service.notify_risk_alert(
            alert_type="stop_loss",
            recipient="risk@example.com",
            symbol="AAPL",
            current_value=90.0,
            threshold=92.0,
        )
        
        assert success is True
    
    def test_notify_risk_alert_position_limit(self):
        """Test position limit alert."""
        success = self.service.notify_risk_alert(
            alert_type="position_limit",
            recipient="risk@example.com",
            current_value=25.0,
            threshold=20.0,
        )
        
        assert success is True
    
    def test_notify_performance_summary(self):
        """Test performance summary notification."""
        success = self.service.notify_performance_summary(
            period="daily",
            recipient="performance@example.com",
            total_return=5000.0,
            total_return_pct=5.0,
            sharpe_ratio=1.5,
            max_drawdown=8.0,
            win_rate=65.0,
            total_trades=100,
        )
        
        assert success is True


class TestIntegration:
    """Integration tests for complete notification workflow."""
    
    def test_complete_workflow(self):
        """Test complete notification workflow."""
        service = NotificationService()
        
        # 1. Create template
        message = service.create_template(
            template_name="trade",
            variables={
                "symbol": "AAPL",
                "action": "BUY",
                "shares": 100,
                "price": 150.0,
            },
        )
        
        assert "BUY" in message
        
        # 2. Send notification
        success = service.send_notification(
            channel=NotificationChannel.EMAIL,
            message=message,
            recipient="trader@example.com",
            subject="Trade Notification",
        )
        
        assert success is True
        
        # 3. Check status
        notification_id = list(service.notifications.keys())[0]
        status = service.get_notification_status(notification_id)
        
        assert status["status"] == "sent"
        
        # 4. Check history
        history = service.get_notification_history()
        
        assert len(history) == 1
        
        # 5. Check statistics
        stats = service.get_statistics()
        
        assert stats["total_notifications"] == 1
        assert stats["sent"] == 1
    
    def test_multiple_notifications_workflow(self):
        """Test workflow with multiple notifications."""
        service = NotificationService()
        
        # Send trade notification
        service.notify_trade(
            symbol="AAPL",
            action="BUY",
            shares=100,
            price=150.0,
            recipient="trader@example.com",
        )
        
        # Send risk alert
        service.notify_risk_alert(
            alert_type="stop_loss",
            recipient="risk@example.com",
            symbol="AAPL",
            current_value=90.0,
            threshold=92.0,
        )
        
        # Send performance summary
        service.notify_performance_summary(
            period="daily",
            recipient="performance@example.com",
            total_return=5000.0,
            total_return_pct=5.0,
            sharpe_ratio=1.5,
            max_drawdown=8.0,
            win_rate=65.0,
            total_trades=100,
        )
        
        # Check all notifications sent
        stats = service.get_statistics()
        
        assert stats["total_notifications"] == 3
        assert stats["sent"] == 3
        assert stats["success_rate"] == 100.0


class TestDebugLogging:
    """Test debug logging cycles."""
    
    def test_cycle_1_config_validation(self, caplog):
        """Test Cycle 1: Config validation debug logging."""
        with caplog.at_level(logging.DEBUG):
            config = NotificationConfig()
        
        # Check debug logs contain Cycle 1 marker
        assert any("Cycle 1" in record.message for record in caplog.records)
    
    def test_cycle_2_template_rendering(self, caplog):
        """Test Cycle 2: Template rendering debug logging."""
        service = NotificationService()
        
        with caplog.at_level(logging.DEBUG):
            service.create_template(
                template_name="trade",
                variables={
                    "symbol": "AAPL",
                    "action": "BUY",
                    "shares": 100,
                    "price": 150.0,
                },
            )
        
        # Check debug logs contain Cycle 2 marker
        assert any("Cycle 2" in record.message for record in caplog.records)
    
    def test_cycle_3_channel_validation(self, caplog):
        """Test Cycle 3: Channel validation debug logging."""
        service = NotificationService()
        
        with caplog.at_level(logging.DEBUG):
            service.validate_channel(
                channel=NotificationChannel.EMAIL,
                recipient="test@example.com",
            )
        
        # Check debug logs contain Cycle 3 marker
        assert any("Cycle 3" in record.message for record in caplog.records)
    
    def test_cycle_4_send_operation(self, caplog):
        """Test Cycle 4: Send operation debug logging."""
        service = NotificationService()
        
        with caplog.at_level(logging.DEBUG):
            service.send_notification(
                channel=NotificationChannel.EMAIL,
                message="Test",
                recipient="test@example.com",
                subject="Test",
            )
        
        # Check debug logs contain Cycle 4 marker
        assert any("Cycle 4" in record.message for record in caplog.records)
    
    def test_cycle_5_status_tracking(self, caplog):
        """Test Cycle 5: Status tracking debug logging."""
        service = NotificationService()
        
        # Send notification first
        service.send_notification(
            channel=NotificationChannel.EMAIL,
            message="Test",
            recipient="test@example.com",
            subject="Test",
        )
        
        notification_id = list(service.notifications.keys())[0]
        
        with caplog.at_level(logging.DEBUG):
            service.get_notification_status(notification_id)
        
        # Check debug logs contain Cycle 5 marker
        assert any("Cycle 5" in record.message for record in caplog.records)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
