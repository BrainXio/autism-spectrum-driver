"""Tests for the prototype scanner module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from asd.scanner import (
    PrototypeMetadata,
    ScanResult,
    _compute_priority,
    _detect_domain,
    _detect_maturity,
    _detect_tech_stack,
    _is_project_directory,
    load_shortlist,
    save_shortlist,
    scan_prototypes,
)


class TestDomainDetection:
    """Domain extraction from file contents."""

    def test_detects_ai_ml_domain(self) -> None:
        contents = [
            "We use a transformer-based language model for inference.",
            "Fine-tuning the LLM on custom data.",
        ]
        domain, confidence = _detect_domain(contents)
        assert domain == "ai-ml"
        assert confidence > 0

    def test_detects_neuroscience_domain(self) -> None:
        contents = [
            "The prefrontal cortex gates action selection.",
            "Dopamine neurons encode reward prediction error.",
        ]
        domain, confidence = _detect_domain(contents)
        assert domain == "neuroscience"
        assert confidence > 0

    def test_detects_knowledge_management_domain(self) -> None:
        contents = [
            "Knowledge base compilation from markdown files.",
            "TF-IDF semantic search with frontmatter parsing.",
        ]
        domain, confidence = _detect_domain(contents)
        assert domain == "knowledge-management"
        assert confidence > 0

    def test_detects_dev_tools_domain(self) -> None:
        contents = [
            "MCP server plugin with CLI tool.",
            "CI pipeline with lint and format checks.",
        ]
        domain, confidence = _detect_domain(contents)
        assert domain == "dev-tools"
        assert confidence > 0

    def test_detects_data_engineering_domain(self) -> None:
        contents = [
            "Streaming ETL pipeline with message bus.",
            "Database storage with cache and queue.",
        ]
        domain, confidence = _detect_domain(contents)
        assert domain == "data-engineering"
        assert confidence > 0

    def test_unknown_domain_for_empty_contents(self) -> None:
        domain, confidence = _detect_domain([])
        assert domain == "unknown"
        assert confidence == 0.0

    def test_unknown_domain_for_no_match(self) -> None:
        domain, confidence = _detect_domain(["lorem ipsum dolor sit amet"])
        assert domain == "unknown"
        assert confidence == 0.0

    def test_handles_multiple_domains_picks_strongest(self) -> None:
        contents = [
            "python cli tool",  # dev-tools
            "machine learning neural network training",  # ai-ml (stronger)
        ]
        domain, confidence = _detect_domain(contents)
        assert domain == "ai-ml"


class TestMaturityDetection:
    """Maturity level detection from directory structure."""

    def test_detects_production_from_ci(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "ci.yml").write_text("")
            assert _detect_maturity(root) == "production"

    def test_detects_beta_from_tests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "conftest.py").write_text("")
            assert _detect_maturity(root) == "beta"

    def test_detects_alpha_from_readme(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Project")
            assert _detect_maturity(root) == "alpha"

    def test_unknown_for_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert _detect_maturity(root) == "unknown"

    def test_production_beats_beta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Dockerfile").write_text("")
            (root / "tests").mkdir()
            assert _detect_maturity(root) == "production"


class TestTechStackDetection:
    """Technology stack detection from project files."""

    def test_detects_python_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("")
            assert _detect_tech_stack(root) == ["python"]

    def test_detects_javascript_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("")
            assert _detect_tech_stack(root) == ["javascript"]

    def test_detects_rust_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Cargo.toml").write_text("")
            assert _detect_tech_stack(root) == ["rust"]

    def test_detects_multi_stack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("")
            (root / "Dockerfile").write_text("")
            result = _detect_tech_stack(root)
            assert "docker" in result
            assert "python" in result

    def test_unknown_for_empty_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert _detect_tech_stack(root) == ["unknown"]

    def test_sorted_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Dockerfile").write_text("")
            (root / "package.json").write_text("")
            result = _detect_tech_stack(root)
            assert result == sorted(result)


class TestProjectDetection:
    """Project directory identification."""

    def test_pyproject_toml_is_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("")
            assert _is_project_directory(root) is True

    def test_package_json_is_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("")
            assert _is_project_directory(root) is True

    def test_readme_is_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("")
            assert _is_project_directory(root) is True

    def test_multiple_py_files_is_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("")
            (root / "utils.py").write_text("")
            assert _is_project_directory(root) is True

    def test_single_py_file_is_not_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "script.py").write_text("")
            assert _is_project_directory(root) is False

    def test_empty_dir_is_not_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assert _is_project_directory(root) is False

    def test_ipynb_files_are_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notebook.ipynb").write_text("{}")
            assert _is_project_directory(root) is True


class TestPriorityComputation:
    """Priority scoring for ingestion planning."""

    def test_high_confidence_production_is_priority_1(self) -> None:
        meta = PrototypeMetadata(
            name="test",
            path="/tmp/test",
            domain="ai-ml",
            domain_confidence=0.5,
            maturity="production",
            tech_stack=["python"],
            last_modified="2026-01-01T00:00:00Z",
            topic_overlap=0.3,
            file_count=30,
        )
        priority, rationale = _compute_priority(meta)
        assert priority == 1
        assert rationale

    def test_low_confidence_prototype_is_low_priority(self) -> None:
        meta = PrototypeMetadata(
            name="test",
            path="/tmp/test",
            domain="unknown",
            domain_confidence=0.0,
            maturity="prototype",
            tech_stack=["unknown"],
            last_modified="2026-01-01T00:00:00Z",
            topic_overlap=0.0,
            file_count=1,
        )
        priority, rationale = _compute_priority(meta)
        assert priority == 5
        assert rationale == "no strong signals"

    def test_beta_with_known_stack_is_priority_2(self) -> None:
        meta = PrototypeMetadata(
            name="test",
            path="/tmp/test",
            domain="dev-tools",
            domain_confidence=0.3,
            maturity="beta",
            tech_stack=["python", "docker"],
            last_modified="2026-01-01T00:00:00Z",
            topic_overlap=0.1,
            file_count=15,
        )
        priority, _ = _compute_priority(meta)
        assert priority == 2


class TestScanPrototypes:
    """Full prototype scanning."""

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = scan_prototypes(root_dir=root)
            assert isinstance(result, ScanResult)
            assert result.prototypes_found == 0
            assert result.prototypes == []

    def test_nonexistent_directory(self) -> None:
        result = scan_prototypes(root_dir=Path("/nonexistent/path"))
        assert result.prototypes_found == 0

    def test_scans_single_python_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = root / "my-python-app"
            proj.mkdir()
            (proj / "pyproject.toml").write_text("")
            (proj / "README.md").write_text("# My Python App")
            (proj / "Dockerfile").write_text("")
            (proj / "src").mkdir(parents=True)
            (proj / "src" / "app.py").write_text(
                "import ollama\n" + "model = 'transformer'\n" + "# machine learning inference\n"
            )

            result = scan_prototypes(root_dir=root)
            assert result.prototypes_found == 1
            proto = result.prototypes[0]
            assert proto["name"] == "my-python-app"
            assert "domain" in proto
            assert "maturity" in proto
            assert "tech_stack" in proto
            assert "suggested_priority" in proto
            assert "priority_rationale" in proto

    def test_skips_dot_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            hidden = root / ".hidden-project"
            hidden.mkdir()
            (hidden / "pyproject.toml").write_text("")
            (hidden / "README.md").write_text("")

            result = scan_prototypes(root_dir=root)
            assert result.prototypes_found == 0

    def test_sorts_by_priority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # Low priority project
            low = root / "zzz-low"
            low.mkdir()
            (low / "README.md").write_text("# Low")

            # High priority project
            high = root / "aaa-high"
            high.mkdir()
            (high / "pyproject.toml").write_text("")
            (high / "Dockerfile").write_text("")
            (high / ".github" / "workflows").mkdir(parents=True)
            (high / ".github" / "workflows" / "ci.yml").write_text("")
            (high / "src").mkdir(parents=True)
            (high / "src" / "brain.py").write_text(
                "prefrontal cortex dopamine basal ganglia " * 5,
            )
            for i in range(25):
                (high / f"module_{i}.py").write_text(f"# module {i}")

            result = scan_prototypes(root_dir=root)
            assert result.prototypes_found == 2
            # High priority project should be first
            assert result.prototypes[0]["name"] == "aaa-high"
            assert result.prototypes[1]["name"] == "zzz-low"

    def test_respects_max_prototypes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(10):
                proj = root / f"project-{i}"
                proj.mkdir()
                (proj / "pyproject.toml").write_text("")

            result = scan_prototypes(root_dir=root, max_prototypes=3)
            assert result.prototypes_found == 3


class TestShortlistIO:
    """Shortlist save/load serialization."""

    def test_roundtrip(self) -> None:
        result = ScanResult(
            scanned_at="2026-05-01T00:00:00Z",
            root_directory="/tmp/test",
            prototypes_found=1,
            prototypes=[
                {
                    "name": "test-proj",
                    "path": "/tmp/test/test-proj",
                    "domain": "ai-ml",
                    "domain_confidence": 0.4,
                    "maturity": "beta",
                    "tech_stack": ["python"],
                    "last_modified": "2026-05-01T00:00:00Z",
                    "topic_overlap": 0.2,
                    "file_count": 10,
                    "summary": "A test project",
                    "suggested_priority": 2,
                    "priority_rationale": "strong signal",
                },
            ],
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shortlist.json"
            saved = save_shortlist(result, path)
            assert saved == path
            assert path.exists()

            loaded = load_shortlist(path)
            assert loaded is not None
            assert loaded.prototypes_found == 1
            assert loaded.prototypes[0]["name"] == "test-proj"

    def test_load_nonexistent_file(self) -> None:
        result = load_shortlist(Path("/nonexistent/shortlist.json"))
        assert result is None

    def test_load_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text("not valid json at all {{{")
            result = load_shortlist(path)
            assert result is None
