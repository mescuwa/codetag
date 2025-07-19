# CodeTag: AI-Powered Codebase Analysis and Distillation

**CodeTag** is a powerful, **interactive** toolkit for analysing, understanding, and summarising software repositories. It turns sprawling projects into concise, AI-ready context through a guided, text-based user-interface (TUI).

---

## Why CodeTag?

* **Guided UX** – a menu-driven TUI makes every feature discoverable.
* **Insightful Metrics** – language breakdowns, complexity scores & dependency graphs in seconds.
* **AI-Ready Context** – pack or distil code into a single file tailor-made for LLMs.
* **Integrated Security** – optional OSV-Scanner & Semgrep checks before you share code.
* **Hybrid Power** – friendly TUI for humans; rich CLI for automation.

---

## 🚀 Installation (Recommended)

The easiest way to install CodeTag is via **[pipx](https://pypa.github.io/pipx/)** – it creates an isolated environment automatically and places the `codetag` command on your `$PATH`.

### 1. Install `pipx` *(one-time)*

```bash
# macOS / Linux
python3 -m pip install --user pipx
python3 -m pipx ensurepath  # may require terminal restart
```

### 2. Install CodeTag

```bash
pipx install git+https://github.com/mescuwa/codetag.git
```

That's it – `codetag` is now available everywhere:

```bash
codetag  # launches the interactive TUI
```

---

## External Dependencies (for the `audit` command)

`audit` orchestrates standalone security tools; install them *inside* CodeTag’s pipx environment:

```bash
pipx inject codetag osv-scanner   # dependency vulnerability scanner
pipx inject codetag semgrep       # static code analysis
```

For **tree-sitter distillation** follow the instructions in the advanced section below.

---

## For Developers / Contributors

Prefer a classic editable install? Use a virtual environment:

```bash
# clone & enter repo
git clone https://github.com/mescuwa/codetag.git
cd codetag

# create & activate venv
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate

# editable install with extras
pip install -e ".[audit,dev]"
```

---

## Advanced Usage – CLI Reference

The TUI shows the equivalent CLI after every run, but here are common commands:

```bash
# scan a repo into JSON
codetag scan ./project --output report.json

# pack with 100k token budget
codetag pack ./project --output packed.txt --max-tokens 100000

# distill (level 2)
codetag distill ./project --output summary.txt --level 2

# audit with stricter rules
codetag audit ./project --strict
```

Settings can be stored in a `.codetag.yaml`; flags override file values.

---

## Advanced: Enabling Tree-sitter Distillation

```bash
pip install tree-sitter
# clone grammars you need e.g.
git clone https://github.com/tree-sitter/tree-sitter-python vendor/tree-sitter-python

python - <<'PY'
from tree_sitter import Language
Language.build_library('build/my-languages.so', ['vendor/tree-sitter-python'])
PY

export CODETAG_TS_LIB=build/my-languages.so
```

---

## Licence

CodeTag is released under the MIT Licence (see `LICENSE`).