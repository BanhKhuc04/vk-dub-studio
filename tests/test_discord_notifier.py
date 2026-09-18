import unittest
from unittest.mock import patch, MagicMock
from vkdub.services.discord_notifier import (
    send_discord_message,
    post_project_launch_announcement,
    post_commit_push_notification,
)


class TestDiscordNotifier(unittest.TestCase):
    @patch("vkdub.services.discord_notifier.urllib.request.urlopen")
    def test_send_discord_message_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 204
        mock_urlopen.return_value.__enter__.return_value = mock_response

        success = send_discord_message(
            content="Test Notification",
            embeds=[{"title": "Test Title", "description": "Test Description"}],
        )
        self.assertTrue(success)
        mock_urlopen.assert_called_once()

    @patch("vkdub.services.discord_notifier.urllib.request.urlopen")
    def test_send_discord_message_failure(self, mock_urlopen):
        mock_urlopen.side_effect = Exception("Network error")

        success = send_discord_message(content="Test Fail")
        self.assertFalse(success)

    @patch("vkdub.services.discord_notifier.send_discord_message")
    def test_post_project_launch_announcement(self, mock_send):
        mock_send.return_value = True
        success = post_project_launch_announcement()
        self.assertTrue(success)
        mock_send.assert_called_once()

    @patch("vkdub.services.discord_notifier.send_discord_message")
    def test_post_commit_push_notification(self, mock_send):
        mock_send.return_value = True
        success = post_commit_push_notification(
            commit_msg="feat: test notification",
            author="vanhkhuc",
        )
        self.assertTrue(success)
        mock_send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
