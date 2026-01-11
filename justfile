# Alienbio build commands

# Default: show available commands
default:
    @just --list

# Build all components
build:
    @echo "Building alienbio..."
    uv sync

# Run all tests
test:
    uv run pytest tests/ -v

# Type check with pyright
check:
    uv run pyright src/

# Format code with ruff
fmt:
    uv run ruff format src/ tests/

# Lint code with ruff
lint:
    uv run ruff check src/ tests/

# Clean build artifacts
clean:
    rm -rf __pycache__ .pytest_cache .pyright .ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Generate SVG diagrams from .dot files
diagrams:
    #!/usr/bin/env bash
    shopt -s nullglob
    for f in docs/diagrams/*.dot; do
        dot -Tsvg "$f" -o "${f%.dot}.svg"
        echo "Generated ${f%.dot}.svg"
    done

# Build documentation site with MkDocs
docs: diagrams
    @echo "Building documentation..."
    uv run mkdocs build

# Serve documentation locally with live reload
docs-serve:
    uv run mkdocs serve

# Website repo path for deployment
website_repo := "/Users/oblinger/ob/proj/oblinger.github.io"

# Deploy docs to personal website (copies to oblinger.github.io/abio-docs/)
docs-deploy: docs
    @echo "Deploying to website repo..."
    rm -rf {{website_repo}}/abio-docs
    cp -r site {{website_repo}}/abio-docs
    @echo ""
    @echo "✓ Copied to {{website_repo}}/abio-docs/"
    @echo "  To publish: cd {{website_repo}} && git add abio-docs && git commit -m 'Update abio docs' && git push"

# Build Rust simulator
build-rust:
    cd rust && cargo build --release

# Run main entry point
run *ARGS:
    uv run python -m alienbio {{ARGS}}

# View the last generated report in spreadsheet app
view-report:
    uv run python -m alienbio view-report
