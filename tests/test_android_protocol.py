"""Run the actual Android Java merge/client code on the host JVM when available."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from lan_sync import Ledger, SyncServer, merge_documents


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"


class AndroidProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidates = list(TOOLS.glob("jdk-*/bin/javac.exe"))
        platform = TOOLS / "sdk/platforms/android-35/android.jar"
        library = TOOLS / "json.jar"
        if not candidates or not platform.exists() or not library.exists():
            raise unittest.SkipTest("Host JDK, Android SDK and JSON test library are not installed")
        cls.folder = tempfile.TemporaryDirectory()
        cls.output = Path(cls.folder.name)
        cls.java = candidates[0].with_name("java.exe")
        cls.classpath = ";".join(map(str, [library, platform, cls.output]))
        source = ROOT / "android/app/src/main/java/cn/local/studyschedule"
        subprocess.run([str(candidates[0]), "-encoding", "UTF-8", "--release", "17", "-cp", cls.classpath, "-d", str(cls.output),
                        str(source / "StudyStore.java"), str(source / "CourseSchedule.java"), str(source / "SyncClient.java"), str(ROOT / "tests/ProtocolCheck.java")], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def invoke(self, mode, document, *arguments):
        left = self.output / "left.json"
        left.write_text(json.dumps(document), encoding="utf-8")
        result = subprocess.run([str(self.java), "-Dfile.encoding=UTF-8", "-cp", self.classpath, "ProtocolCheck", mode, str(left), *map(str, arguments)],
                                check=True, capture_output=True, encoding="utf-8")
        return json.loads(result.stdout)

    def test_java_and_python_merge_match(self):
        pc = Ledger("pc", [{"id": "math", "name": "Math", "goal": 30, "records": {"2026-10-27": 100}}])
        phone = Ledger("phone", pc.stored())
        local = phone.active(); local[0]["name"] = "Algebra"; local[0]["records"]["2026-10-27"] += 60; phone.capture(local)
        local = phone.active(); local[0]["schedule"] = {"mode": "weekdays", "days": [1, 3, 5]}; phone.capture(local)
        local = pc.active(); local[0]["goal"] = 60; local[0]["records"]["2026-10-27"] += 20; pc.capture(local)
        right = self.output / "right.json"; right.write_text(json.dumps(phone.document), encoding="utf-8")
        merged = self.invoke("merge", pc.document, right)
        self.assertEqual(merged, merge_documents(pc.document, phone.document))
        self.assertEqual(merged["items"][0]["schedule"], {"mode": "weekdays", "days": [1, 3, 5]})
        self.assertEqual(self.invoke("merge", merged, right), merged)
        phone.capture([])
        right.write_text(json.dumps(phone.document), encoding="utf-8")
        self.assertEqual(self.invoke("merge", merged, right), merge_documents(merged, phone.document))

    def test_actual_android_http_client_to_python_server(self):
        pc = Ledger("pc", [{"id": "math", "name": "Math", "goal": 30, "records": {"2026-10-27": 100}}])
        phone = Ledger("phone", pc.stored())
        local = phone.active(); local[0]["records"]["2026-10-27"] += 60; phone.capture(local)
        local = phone.active(); local[0]["schedule"] = {"mode": "even"}; phone.capture(local)
        def exchange(document):
            pc.merge(document)
            return deepcopy(pc.document)
        server = SyncServer("ABCDEF123456", exchange, host="127.0.0.1", port=0)
        server.start()
        try:
            result = self.invoke("http", phone.document, f"http://127.0.0.1:{server.port}", "ABCDEF123456")
            self.assertEqual(result, pc.document)
            self.assertEqual(pc.active()[0]["records"]["2026-10-27"], 160)
            self.assertEqual(pc.active()[0]["schedule"], {"mode": "even"})
            self.assertEqual(self.invoke("http", phone.document, f"http://127.0.0.1:{server.port}", "ABCDEF123456"), result)
        finally:
            server.close()
