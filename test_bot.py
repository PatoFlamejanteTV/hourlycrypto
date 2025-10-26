import unittest
from unittest.mock import patch
import os
import sys

sys.argv = ['bot.py']
from bot import main

class TestBot(unittest.TestCase):

    @patch('bot.post_once')
    @patch('time.sleep', side_effect=InterruptedError)
    @patch('time.time')
    @patch('bot.load_env_from_dotenv')
    def test_main_loop_adjusts_sleep_time(self, mock_load_env, mock_time, mock_sleep, mock_post_once):
        """
        Tests that the main loop correctly adjusts the sleep time
        to account for the execution time of post_once.
        """
        # Simulate post_once taking 5 seconds to run by controlling time.time().
        mock_time.side_effect = [1000.0, 1005.0]

        os.environ['INTERVAL_MINUTES'] = '1'

        with self.assertRaises(InterruptedError):
            main(['bot.py'])

        # execution_time will be 1005.0 - 1000.0 = 5.0.
        # sleep_time will be 60 - 5.0 = 55.0.
        mock_sleep.assert_called_once_with(55.0)

if __name__ == '__main__':
    unittest.main()
