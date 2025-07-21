# Contributing to **CodeTag**

Thanks for considering a contribution 🎉

This project thrives on community input—whether it’s bug reports, code, or
ideas.  The sections below describe the preferred workflow and basic coding
conventions.

---

## 1. Workflow

1. **Fork** the repository and create your feature branch
   ```bash
   git checkout -b feat/my-awesome-thing
   ```
2. **Make your changes** (see Style Guide below).
3. **Add tests** if possible (`pytest`).
4. **Run the linters / formatters**
   ```bash
   tox -e format,lint,test     # see *tox.ini*
   ```
5. **Commit** using conventional-commit style messages.
6. **Open a Pull Request** — automatic CI will run the same checks.

---

## 2. Development Environment

```bash
# clone & enter repo
git clone https://github.com/<you>/codetag.git
cd codetag

# create & activate a virtualenv
python -m venv venv
source venv/bin/activate

# editable install with dev extras
pip install -e ".[dev]"
```

The command above installs **black**, **isort**, **pytest**, **tox**, etc.

---

## Code Style and Quality

To maintain a consistent and high-quality codebase we use **[Ruff](https://docs.astral.sh/ruff/)** for automated linting *and* formatting.  The CI pipeline will automatically check every pull request for compliance.

Before committing your changes, run:

```bash
# Show linting errors & warnings
ruff check .

# Auto-format files to the project style
ruff format .
```

Fix any reported issues locally so your PR sails through CI.

---

## Running Tests

Our test suite uses **pytest**.  After setting up the development environment, execute all tests from the project root with:

```bash
pytest
```

Pytest will automatically discover every file in the `tests/` directory.
Please ensure the suite passes locally before opening a pull request.

---