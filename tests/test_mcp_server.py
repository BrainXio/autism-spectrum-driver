"""Integration tests for the ASD MCP server and tool handlers."""

import tempfile
from pathlib import Path

from asd.tools.developer import (
    handle_compile,
    handle_get_mode,
    handle_get_shortlist,
    handle_ingest,
    handle_query,
    handle_scan_prototypes,
    handle_set_mode,
    handle_status,
    handle_validate,
)


class TestModeHandlers:
    """Mode switching."""

    def test_set_valid_mode(self) -> None:
        result = handle_set_mode("developer")
        assert result["ok"] is True
        assert result["current"] == "developer"

    def test_set_invalid_mode(self) -> None:
        result = handle_set_mode("invalid")
        assert result["ok"] is False
        assert "error" in result

    def test_get_mode(self) -> None:
        result = handle_get_mode()
        assert result["mode"] == "developer"


class TestIngestHandler:
    """Ingest handler integration."""

    def test_ingest_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_ingest(project_root=tmp)
            assert result["ok"] is False
            assert "not found" in result["error"]

    def test_ingest_with_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb_dir = root / "USER" / "kb" / "concepts"
            kb_dir.mkdir(parents=True)
            (kb_dir / "article.md").write_text(
                "---\ntitle: Test\ntags: [a, b]\n---\n\n" + "word " * 100 + "\n",
            )

            result = handle_ingest(project_root=tmp)
            assert result["ok"] is True
            assert result["scanned"] == 1


class TestCompileHandler:
    """Compile handler integration."""

    def test_compile_missing_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_compile(project_root=tmp)
            assert result["ok"] is False
            assert "not found" in result["error"]

    def test_compile_with_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "USER" / "logs" / "daily"
            logs_dir.mkdir(parents=True)
            log = logs_dir / "2026-04-29.md"
            log_content = (
                "## Python Patterns\n\n"
                + "Design patterns in Python are reusable solutions.\n" * 10
                + "\n## Rust Memory\n\n"
                + "Rust memory management uses ownership.\n" * 10
            )
            log.write_text(log_content)

            result = handle_compile(project_root=tmp)
            assert result["ok"] is True
            assert result["articles_created"] >= 1

    def test_compile_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            logs_dir = root / "USER" / "logs" / "daily"
            logs_dir.mkdir(parents=True)
            (logs_dir / "2026-04-29.md").write_text("## Test\n\n" + "content " * 50)

            result = handle_compile(project_root=tmp, dry_run=True)
            assert result["ok"] is True
            assert result["articles_created"] == 0  # dry run doesn't write


class TestQueryHandler:
    """Query handler integration."""

    def test_query_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_query(project_root=tmp, question="test")
            assert result["ok"] is False
            assert "not found" in result["error"]

    def test_query_with_kb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb_dir = root / "USER" / "kb" / "concepts"
            kb_dir.mkdir(parents=True)
            (kb_dir / "python.md").write_text(
                '---\ntitle: Python\ntags: [python]\nupdated: "2026-04-29"\n---\n\n'
                + "Python programming language patterns and idioms.\n",
            )
            (kb_dir / "rust.md").write_text(
                '---\ntitle: Rust\ntags: [rust]\nupdated: "2026-04-28"\n---\n\n'
                + "Rust systems programming.\n",
            )

            result = handle_query(project_root=tmp, question="python patterns", top_k=2)
            assert result["ok"] is True
            assert len(result["results"]) >= 1
            assert result["results"][0]["title"] == "Python"


class TestValidateHandler:
    """Validate handler integration."""

    def test_validate_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_validate(project_root=tmp)
            assert result["ok"] is False

    def test_validate_with_kb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb_dir = root / "USER" / "kb" / "concepts"
            kb_dir.mkdir(parents=True)
            (kb_dir / "article.md").write_text(
                "---\ntitle: Article\n---\n\n" + "word " * 60 + "\n",
            )

            result = handle_validate(project_root=tmp)
            assert result["ok"] is True
            assert "errors" in result
            assert "warnings" in result
            assert "is_healthy" in result


class TestStatusHandler:
    """Status handler integration."""

    def test_status_missing_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_status(project_root=tmp)
            assert result["ok"] is True
            assert result["article_count"] == 0

    def test_status_with_kb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            kb_dir = root / "USER" / "kb" / "concepts"
            kb_dir.mkdir(parents=True)
            (kb_dir / "article1.md").write_text(
                "---\ntitle: Article 1\n---\n\nBody one.\n",
            )

            # First ingest to create state
            handle_ingest(project_root=tmp)

            result = handle_status(project_root=tmp)
            assert result["ok"] is True
            assert result["disk_count"] == 1


class TestScanPrototypesHandler:
    """Prototype scanner MCP tool handler."""

    def test_scan_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_scan_prototypes(project_root=tmp, scan_dir=tmp)
            assert result["ok"] is True
            assert result["prototypes_found"] == 0
            assert "prototypes" in result

    def test_scan_with_python_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / "test-project"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("")
            (proj / "README.md").write_text("# Test Project")
            (proj / "src").mkdir()
            (proj / "src" / "main.py").write_text(
                "import ollama\n# machine learning pipeline\n",
            )

            result = handle_scan_prototypes(project_root=tmp, scan_dir=tmp)
            assert result["ok"] is True
            assert result["prototypes_found"] >= 1
            assert "shortlist_path" in result
            assert Path(result["shortlist_path"]).exists()


class TestGetShortlistHandler:
    """Shortlist loading with filtering."""

    def test_missing_shortlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = handle_get_shortlist(project_root=tmp)
            assert result["ok"] is False
            assert "No shortlist found" in result["error"]

    def test_loads_existing_shortlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortlist_path = root / "USER" / "shortlist.json"

            # First scan to create shortlist
            proj = root / "ai-project"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("")
            (proj / "src").mkdir(parents=True)
            (proj / "src" / "model.py").write_text(
                "neural network deep learning inference " * 5,
            )

            handle_scan_prototypes(project_root=tmp, scan_dir=tmp)
            assert shortlist_path.exists()

            # Now load it
            result = handle_get_shortlist(project_root=tmp)
            assert result["ok"] is True
            assert result["prototypes_found"] >= 1

    def test_filter_by_domain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Create a shortlist with multiple domain entries directly
            shortlist_path = root / "USER" / "shortlist.json"
            shortlist_path.parent.mkdir(parents=True)
            import json

            data = {
                "scanned_at": "2026-05-01T00:00:00Z",
                "root_directory": str(root),
                "prototypes_found": 3,
                "prototypes": [
                    {
                        "name": "ai-proj",
                        "path": "/tmp/ai-proj",
                        "domain": "ai-ml",
                        "domain_confidence": 0.5,
                        "maturity": "beta",
                        "tech_stack": ["python"],
                        "last_modified": "2026-05-01T00:00:00Z",
                        "topic_overlap": 0.3,
                        "file_count": 20,
                        "summary": "AI project",
                        "suggested_priority": 1,
                        "priority_rationale": "strong ai-ml signal",
                    },
                    {
                        "name": "neuro-proj",
                        "path": "/tmp/neuro-proj",
                        "domain": "neuroscience",
                        "domain_confidence": 0.4,
                        "maturity": "alpha",
                        "tech_stack": ["python"],
                        "last_modified": "2026-05-01T00:00:00Z",
                        "topic_overlap": 0.2,
                        "file_count": 10,
                        "summary": "Neuro project",
                        "suggested_priority": 2,
                        "priority_rationale": "neuroscience signal",
                    },
                    {
                        "name": "another-ai",
                        "path": "/tmp/another-ai",
                        "domain": "ai-ml",
                        "domain_confidence": 0.6,
                        "maturity": "production",
                        "tech_stack": ["python", "docker"],
                        "last_modified": "2026-05-01T00:00:00Z",
                        "topic_overlap": 0.4,
                        "file_count": 30,
                        "summary": "Another AI project",
                        "suggested_priority": 1,
                        "priority_rationale": "strong signal",
                    },
                ],
            }
            shortlist_path.write_text(json.dumps(data, indent=2))

            # Load with domain filter
            result = handle_get_shortlist(project_root=tmp, domain="ai-ml")
            assert result["ok"] is True
            assert result["prototypes_found"] == 2
            assert all(p["domain"] == "ai-ml" for p in result["prototypes"])

    def test_filter_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            shortlist_path = root / "USER" / "shortlist.json"
            shortlist_path.parent.mkdir(parents=True)
            import json

            data = {
                "scanned_at": "2026-05-01T00:00:00Z",
                "root_directory": str(root),
                "prototypes_found": 3,
                "prototypes": [
                    {
                        "name": "high-pri",
                        "path": "/tmp/high",
                        "domain": "dev-tools",
                        "domain_confidence": 0.3,
                        "maturity": "production",
                        "tech_stack": ["python"],
                        "last_modified": "2026-05-01T00:00:00Z",
                        "topic_overlap": 0.2,
                        "file_count": 25,
                        "summary": "High",
                        "suggested_priority": 1,
                        "priority_rationale": "production",
                    },
                    {
                        "name": "mid-pri",
                        "path": "/tmp/mid",
                        "domain": "dev-tools",
                        "domain_confidence": 0.2,
                        "maturity": "alpha",
                        "tech_stack": ["python"],
                        "last_modified": "2026-05-01T00:00:00Z",
                        "topic_overlap": 0.1,
                        "file_count": 5,
                        "summary": "Mid",
                        "suggested_priority": 3,
                        "priority_rationale": "alpha",
                    },
                    {
                        "name": "low-pri",
                        "path": "/tmp/low",
                        "domain": "unknown",
                        "domain_confidence": 0.0,
                        "maturity": "prototype",
                        "tech_stack": ["unknown"],
                        "last_modified": "2026-05-01T00:00:00Z",
                        "topic_overlap": 0.0,
                        "file_count": 1,
                        "summary": "Low",
                        "suggested_priority": 5,
                        "priority_rationale": "no strong signals",
                    },
                ],
            }
            shortlist_path.write_text(json.dumps(data, indent=2))

            # min_priority=2: only include priority 1 and 2
            result = handle_get_shortlist(project_root=tmp, min_priority=2)
            assert result["ok"] is True
            assert result["prototypes_found"] == 1
            assert result["prototypes"][0]["name"] == "high-pri"


class TestEndToEnd:
    """Full pipeline: compile → ingest → query → validate → status."""

    def test_full_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Setup: create daily log
            logs_dir = root / "USER" / "logs" / "daily"
            logs_dir.mkdir(parents=True)
            log = logs_dir / "2026-04-29.md"
            log_content = (
                "## TF-IDF Search\n\n"
                + "TF-IDF implementation from first principles.\n" * 10
                + "\n## MCP Server Pattern\n\n"
                + "FastMCP server pattern with typed tools.\n" * 10
            )
            log.write_text(log_content)

            # 1. Compile logs -> KB articles
            compile_result = handle_compile(project_root=tmp)
            assert compile_result["ok"] is True
            assert compile_result["articles_created"] >= 1

            # 2. Ingest KB -> state tracking
            ingest_result = handle_ingest(project_root=tmp)
            assert ingest_result["ok"] is True
            assert ingest_result["scanned"] >= 1

            # 3. Query -> relevant results
            query_result = handle_query(project_root=tmp, question="TF-IDF search")
            assert query_result["ok"] is True
            assert len(query_result["results"]) >= 1

            # 4. Validate -> health check
            validate_result = handle_validate(project_root=tmp)
            assert validate_result["ok"] is True

            # 5. Status -> health report
            status_result = handle_status(project_root=tmp)
            assert status_result["ok"] is True
            assert status_result["disk_count"] >= 1
