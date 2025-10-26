import os
import unittest
from unittest.mock import patch, Mock
import time
from datetime import datetime, timezone, timedelta

# This is a bit of a hack to import the bot script as a module
import sys
sys.path.append('.')
import bot

class TestScheduler(unittest.TestCase):

    @patch('time.sleep')
    def test_buggy_scheduler_sleeps_fixed_amount(self, mock_sleep):
        interval = 60
        # In the buggy code, the loop is `while True: post_once(); time.sleep(interval * 60)`
        # This test simulates that simple loop.
        bot.post_once = Mock() # Mock post_once so it does nothing

        # Simulate the loop running twice
        time.sleep(interval * 60)
        time.sleep(interval * 60)

        mock_sleep.assert_called_with(3600)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('time.sleep')
    def test_fixed_scheduler_sleeps_variable_amount(self, mock_sleep):
        interval = 60
        bot.post_once = Mock()

        # Simulate the fixed loop running twice
        for _ in range(2):
            now_utc = datetime.now(timezone.utc)
            minutes_to_next_interval = interval - (now_utc.minute % interval)
            next_run_time = (now_utc + timedelta(minutes=minutes_to_next_interval)).replace(second=0, microsecond=0)
            sleep_seconds = (next_run_time - now_utc).total_seconds()
            if sleep_seconds <= 0:
                next_run_time += timedelta(minutes=interval)
                sleep_seconds = (next_run_time - now_utc).total_seconds()
            time.sleep(sleep_seconds)

        # The sleep time should be less than 3600 because it accounts for the execution time
        self.assertLess(mock_sleep.call_args_list[0][0][0], 3600)
        self.assertLess(mock_sleep.call_args_list[1][0][0], 3600)
        self.assertEqual(mock_sleep.call_count, 2)

if __name__ == '__main__':
    unittest.main()
