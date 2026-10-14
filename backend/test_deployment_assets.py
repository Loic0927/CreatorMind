from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_docker_build_context_excludes_sensitive_and_unneeded_paths():
    rules = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    required_rules = (
        ".env",
        ".env.*",
        "backend/data/*.json",
        "backend/test*.py",
        "**/*token*.local.json",
        "backups",
        "**/*.pem",
        "**/*.key",
        "node_modules",
        "secrets",
        "**/*credentials*.json",
    )
    for rule in required_rules:
        assert rule in rules


def test_compose_does_not_publish_api_or_database_ports():
    compose = (ROOT / "deploy" / "aws-lightsail" / "compose.yaml").read_text(
        encoding="utf-8"
    )
    assert '"8000:8000"' not in compose
    assert '"5432:5432"' not in compose
    assert "postgres:17-alpine" in compose
    assert "internal: true" in compose


def test_oci_compose_keeps_app_and_database_private():
    compose = (ROOT / "docker-compose.oci.yml").read_text(encoding="utf-8")
    assert '"5432:5432"' not in compose
    assert '"8000:8000"' not in compose
    assert '"80:80"' in compose
    assert '"443:443"' in compose
    assert compose.count("internal: true") >= 1
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "platform: linux/arm64" in compose
    db_section = compose.split("  db:", 1)[1].split("  app:", 1)[0]
    assert "env_file" not in db_section


def test_oci_example_contains_placeholders_not_private_keys():
    example = (ROOT / ".env.oci.example").read_text(encoding="utf-8")
    assert "OCI_REGION=ap-sydney-1" in example
    assert "BEGIN PRIVATE KEY" not in example
    assert "replace-with" in example


def test_oci_production_image_is_non_root_and_has_entrypoint():
    dockerfile = (ROOT / "Dockerfile.production").read_text(encoding="utf-8")
    assert "USER creatormind" in dockerfile
    assert 'ENTRYPOINT ["/app/scripts/oci/entrypoint.sh"]' in dockerfile
