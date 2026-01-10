# Releasing the Drip Python SDK

This guide covers how to release the Python SDK to PyPI and set up a standalone GitHub repository.

## Option 1: Publish from Monorepo

If keeping the SDK in the main Drip monorepo:

### First-time Setup

1. **Create PyPI account** at https://pypi.org/account/register/

2. **Configure trusted publishing** (recommended - no API tokens needed):
   - Go to https://pypi.org/manage/project/drip-sdk/settings/publishing/
   - Add a new publisher:
     - Owner: `your-org`
     - Repository: `drip`
     - Workflow: `sdk-python/.github/workflows/publish.yml`
     - Environment: (leave blank)

3. **Or use API token** (alternative):
   ```bash
   # Generate token at https://pypi.org/manage/account/token/
   gh secret set PYPI_API_TOKEN --repo your-org/drip
   ```

### Publishing a Release

```bash
# 1. Update version in pyproject.toml
cd sdk-python
# Edit pyproject.toml: version = "1.0.1"

# 2. Commit the version bump
git add pyproject.toml
git commit -m "chore(sdk-python): bump version to 1.0.1"
git push

# 3. Create a GitHub release (triggers publish workflow)
gh release create sdk-python-v1.0.1 \
  --title "Python SDK v1.0.1" \
  --notes "Release notes here"
```

### Manual Publishing (for testing)

```bash
cd sdk-python

# Install build tools
pip install build twine

# Build the package
python -m build

# Upload to TestPyPI first (recommended)
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*
```

---

## Option 2: Standalone Repository

To maintain the Python SDK in its own public repository:

### Automated Setup

```bash
cd sdk-python
./scripts/setup-standalone-repo.sh your-org drip-sdk-python
```

### Manual Setup

1. **Create the GitHub repository**:
   ```bash
   gh repo create your-org/drip-sdk-python --public
   ```

2. **Clone and copy files**:
   ```bash
   git clone https://github.com/your-org/drip-sdk-python.git
   cd drip-sdk-python

   # Copy SDK files (from monorepo)
   cp -r ../drip/sdk-python/* .
   cp ../drip/sdk-python/.gitignore .
   ```

3. **Update workflow paths** (remove `sdk-python/` prefixes in CI workflows)

4. **Push to GitHub**:
   ```bash
   git add .
   git commit -m "Initial commit: Drip Python SDK"
   git push -u origin main
   ```

5. **Configure PyPI trusted publishing**:
   - Go to https://pypi.org/manage/project/drip-sdk-python/settings/publishing/
   - Add publisher for new repository

6. **Create first release**:
   ```bash
   gh release create v1.0.0 --title "v1.0.0" --notes "Initial release"
   ```

---

## Version Numbering

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0 → 2.0.0): Breaking API changes
- **MINOR** (1.0.0 → 1.1.0): New features, backwards compatible
- **PATCH** (1.0.0 → 1.0.1): Bug fixes, backwards compatible

---

## Pre-release Checklist

Before releasing:

- [ ] All tests pass: `pytest`
- [ ] Type checking passes: `mypy src`
- [ ] Linting passes: `ruff check src tests`
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG updated (if you maintain one)
- [ ] README is current

---

## Testing the Package

```bash
# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ drip-sdk

# Install from PyPI
pip install drip-sdk

# Verify installation
python -c "from drip import Drip; print('OK')"
```
