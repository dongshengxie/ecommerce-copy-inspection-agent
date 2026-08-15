from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_phase_one_required_directories_and_configuration_exist() -> None:
    required_directories = {
        "app",
        "agent",
        "skills",
        "tools",
        "rag",
        "llm",
        "prompts",
        "workers",
        "review",
        "evaluation",
        "observability",
        "db",
        "scripts",
        "tests",
        "docs",
    }
    required_files = {
        "AGENTS.md",
        "README.md",
        "pyproject.toml",
        ".env.example",
        ".gitignore",
        "docker-compose.yml",
    }

    assert all((PROJECT_ROOT / directory).is_dir() for directory in required_directories)
    assert all((PROJECT_ROOT / file_name).is_file() for file_name in required_files)
