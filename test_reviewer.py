import os
import tempfile
import unittest
from unittest import mock

import reviewer


class RunAgenticReviewEnvTests(unittest.TestCase):
    def test_invalid_max_review_iterations_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_client = mock.Mock()
            fake_message = mock.Mock()
            fake_message.tool_calls = None
            fake_message.content = "synthetic review"
            fake_response = mock.Mock()
            fake_response.choices = [mock.Mock(message=fake_message)]
            fake_client.chat.completions.create.return_value = fake_response

            with mock.patch.dict(os.environ, {"MAX_REVIEW_ITERATIONS": "not-a-number"}, clear=False):
                with mock.patch("reviewer._make_client", return_value=fake_client):
                    result = reviewer.run_agentic_review(working_dir=tmpdir)

        self.assertEqual(result, "synthetic review")
        fake_client.chat.completions.create.assert_called_once()

    def test_get_git_diff_builds_single_pathspec_separator(self) -> None:
        completed = mock.Mock(stdout="diff output")

        with mock.patch("reviewer._run_git_command", return_value=completed) as run_git:
            result = reviewer.get_git_diff(".", "staged")

        self.assertEqual(result, "diff output")
        args = run_git.call_args.args[1]
        self.assertEqual(args[:2], ["diff", "--staged"])
        self.assertEqual(args.count("--"), 1)
        self.assertGreater(len(args), 3)
        self.assertTrue(all(part.startswith(":!") for part in args[3:]))


if __name__ == "__main__":
    unittest.main()
