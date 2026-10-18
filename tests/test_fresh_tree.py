"""Proves the no-key path works from tracked files alone: export HEAD, run the demo."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _has_git_head():
    """True only for a real clone of this kit: a .git folder here and a commit in it.

    A downloaded zip or an exported tree has no history, so the test skips there."""
    if shutil.which("git") is None or not os.path.isdir(os.path.join(ROOT, ".git")):
        return False
    probe = subprocess.run(["git", "-C", ROOT, "rev-parse", "--verify", "HEAD"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return probe.returncode == 0


@unittest.skipUnless(_has_git_head(), "needs a git clone of the kit (a .git folder with a commit)")
class FreshTreeTests(unittest.TestCase):
    def test_demo_sweep_runs_from_git_archive_with_clean_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = os.path.join(tmp, "tree.zip")
            subprocess.run(["git", "-C", ROOT, "archive", "--format=zip", "HEAD", "-o", archive],
                           check=True)
            tree = os.path.join(tmp, "tree")
            os.mkdir(tree)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(tree)
            env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", tmp)}
            done = subprocess.run(
                [sys.executable, "jev_threshold_lab.py", "--demo", "sweep"],
                cwd=tree, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True, timeout=60)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("DEMO (recorded response)", done.stdout)


if __name__ == "__main__":
    unittest.main()
