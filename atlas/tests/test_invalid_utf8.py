"""Malformed source bytes retain original file identity but share decoded AST offsets."""

import hashlib
import unittest
from pathlib import Path

from atlas.discovery import SourceFile
from atlas.extraction.parser import parse_files


class InvalidUtf8Test(unittest.TestCase):
    def test_original_file_digest_and_replacement_decoded_declarations(self) -> None:
        sources = {
            "app.ts": b'// \xff\xfe\xf0\x28\x8c\x28\nexport function value() { return "\xff" }\nvalue()\n',
            "worker.py": b'# \x80\xed\xa0\x80\ndef work():\n return "\xff"\nwork()\n',
            "worker.go": b"//\xff text\npackage main\nfunc f(){g()}\n",
            "Worker.java": b"//\xff text\nclass A { void f(){g();} }\n",
        }
        languages = {
            "ts": "typescript",
            "py": "python",
            "go": "go",
            "java": "java",
        }
        repository = parse_files(
            [
                SourceFile(
                    path,
                    Path("/invalid") / path,
                    languages[path.rsplit(".", 1)[1]],
                    source,
                )
                for path, source in sources.items()
            ]
        )
        expected = {
            "app.ts": [("value", 25)],
            "worker.py": [("work", 15)],
            "worker.go": [("f", 24)],
            "Worker.java": [("A", 11), ("f", 21)],
        }
        for file in repository.files:
            with self.subTest(path=file.source.path):
                self.assert_original_digest_and_decoded_declarations(file, sources, expected)

    def assert_original_digest_and_decoded_declarations(self, file, sources, expected):
        self.assertIsNone(file.parse_error)
        self.assertEqual(
            file.content_hash,
            hashlib.sha256(sources[file.source.path]).hexdigest(),
        )
        self.assertEqual(
            [(s.name, s.start_byte) for s in file.symbols],
            expected[file.source.path],
        )
        self.assertEqual(len(file.calls), 1)
        self.assertEqual(
            file.calls[0].name,
            {
                "app.ts": "value",
                "worker.py": "work",
                "worker.go": "g",
                "Worker.java": "g",
            }[file.source.path],
        )


if __name__ == "__main__":
    unittest.main()
