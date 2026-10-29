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


def test_oci_compose_keeps_app_and_database_private():
    compose = (ROOT / "docker-compose.oci.yml").read_text(encoding="utf-8")
    assert '"5432:5432"' not in compose
    assert '"8000:8000"' not in compose
    assert '"3000:3000"' not in compose
    assert '"80:80"' in compose
    assert '"443:443"' in compose
    assert "  frontend:" in compose
    assert "  tracking-worker:" in compose
    assert 'backend.tracking_worker", "run"' in compose
    assert 'backend.tracking_worker", "healthcheck"' in compose
    assert "dockerfile: Dockerfile.frontend" in compose
    assert "NEXT_PUBLIC_API_BASE_URL" in compose
    assert "headers={'Host': os.environ['POSTBRIDGE_API_DOMAIN']}" in compose
    assert compose.count("internal: true") >= 1
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "platform: linux/arm64" in compose
    db_section = compose.split("  db:", 1)[1].split("  app:", 1)[0]
    assert "env_file" not in db_section


def test_oci_example_contains_placeholders_not_private_keys():
    example = (ROOT / ".env.oci.example").read_text(encoding="utf-8")
    assert "OCI_REGION=ap-sydney-1" in example
    assert "POSTBRIDGE_WEB_DOMAIN=postbridge.dev" in example
    assert "POSTBRIDGE_API_DOMAIN=api.postbridge.dev" in example
    assert "POSTBRIDGE_PUBLIC_API_URL=https://api.postbridge.dev" in example
    assert "BEGIN PRIVATE KEY" not in example
    assert "replace-with" in example


def test_oci_production_image_is_non_root_and_has_entrypoint():
    dockerfile = (ROOT / "Dockerfile.production").read_text(encoding="utf-8")
    assert "USER creatormind" in dockerfile
    assert 'ENTRYPOINT ["/app/scripts/oci/entrypoint.sh"]' in dockerfile


def test_oci_backup_upload_preserves_private_dump_permissions():
    script = (ROOT / "scripts" / "oci" / "backup-postgres.sh").read_text(
        encoding="utf-8"
    )
    assert "umask 077" in script
    assert '--user "$(id -u):$(id -g)"' in script
    assert "chmod 644" not in script


def test_oci_frontend_image_is_standalone_and_non_root():
    dockerfile = (ROOT / "Dockerfile.frontend").read_text(encoding="utf-8")
    next_config = (ROOT / "frontend" / "next.config.mjs").read_text(
        encoding="utf-8"
    )
    assert 'output: "standalone"' in next_config
    assert "NEXT_PUBLIC_API_BASE_URL" in dockerfile
    assert "/app/.next/standalone" in dockerfile
    assert "USER nextjs" in dockerfile
    assert 'CMD ["node", "server.js"]' in dockerfile


def test_oci_nginx_and_certificates_cover_web_www_and_api():
    nginx = (
        ROOT / "deploy" / "oci" / "nginx" / "templates" / "default.conf.template"
    ).read_text(encoding="utf-8")
    certificate_script = (ROOT / "scripts" / "oci" / "init-https.sh").read_text(
        encoding="utf-8"
    )
    for variable in (
        "NGINX_WEB_SERVER_NAME",
        "NGINX_WWW_SERVER_NAME",
        "NGINX_API_SERVER_NAME",
    ):
        assert variable in nginx
    assert "proxy_pass http://postbridge_web" in nginx
    assert "proxy_pass http://postbridge_api" in nginx
    assert '-d "$POSTBRIDGE_WEB_DOMAIN"' in certificate_script
    assert '-d "$POSTBRIDGE_WWW_DOMAIN"' in certificate_script
    assert '-d "$POSTBRIDGE_API_DOMAIN"' in certificate_script
