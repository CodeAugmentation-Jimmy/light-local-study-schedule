"""Exercise production Java timer/store with fake clock and in-memory preferences."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AndroidTimerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = list((ROOT / ".tools").glob("jdk-*/bin/javac.exe"))
        library = ROOT / ".tools/json.jar"
        if not candidates or not library.exists():
            raise unittest.SkipTest("Host JDK and JSON test library not available")
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        cls.java = candidates[0].with_name("java.exe")
        cls.classpath = ";".join([cls.folder.name, str(library)])
        source = ROOT / "android/app/src/main/java/cn/local/studyschedule"
        files = [*sorted((ROOT / "tests/android_stubs").rglob("*.java")),
                 source / "StudyStore.java", source / "StudyStats.java", source / "CourseSchedule.java", ROOT / "tests/AndroidTimerCheck.java"]
        result = subprocess.run([str(candidates[0]), "-encoding", "UTF-8", "--release", "17",
                                 "-cp", cls.classpath, "-d", cls.folder.name, *map(str, files)], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))

    def test_timer_and_statistics(self):
        for scenario in ("background_off", "background_on", "focus_limit", "manual_pause",
                         "boundary_pause", "recovery", "settings", "sync", "statistics",
                         "calendar_rules", "calendar_midnight", "calendar_sync", "calendar_upgrade"):
            with self.subTest(scenario=scenario):
                result = subprocess.run([str(self.java), "-Dfile.encoding=UTF-8", "-cp", self.classpath,
                                         "AndroidTimerCheck", scenario], capture_output=True, encoding="utf-8")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("PASS " + scenario, result.stdout)
