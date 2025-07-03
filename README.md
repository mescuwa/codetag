# CodeTag

[![Python CI](https://github.com/paprikachewl/codetag/actions/workflows/ci.yml/badge.svg)](https://github.com/paprikachewl/codetag/actions/workflows/ci.yml)

A lightweight, local-first CLI tool to rapidly understand a new codebase. It scans a repository and generates a single, structured JSON report detailing its file structure, language statistics, and key points of interest.

---

### About The Project

Developers spend up to 60% of their time just reading and understanding code. When joining a new project, auditing a codebase, or onboarding a new team member, this "code comprehension" phase can take weeks or even months.

CodeTag is designed to drastically shorten that time. It acts as an "instant audit," giving you a high-level, data-driven overview of any repository in seconds. It is built to be fast, private, and deterministic, running entirely on your local machine without ever sending your code to the cloud.

### Key Features

* **Detailed Structure Map:** Generates a complete directory tree of the repository.
* **Language Statistics:** Calculates Lines of Code (LOC) and provides a breakdown by programming language.
* **Key File Detection:** Automatically identifies important files like `READMEs`, `Dockerfiles`, configuration files, and potential entry points (`main.py`, `server.js`, etc.). It also lists the largest files, which often correlate with high complexity.
* **Actionable Insights:** Scans for `TODO` and `FIXME` comments left in the code, giving you an instant pulse on technical debt.
* **Single JSON Output:** Produces one clean, comprehensive JSON report that can be easily shared, stored, or used as context for other tools.
* **Local & Secure:** Processes everything on your machine. Your source code is never uploaded.

### Installation

Download the latest pre-compiled binary for your operating system from the **[Releases](https://github.com/paprikachewl/codetag/releases)** page.

Place the `codetag` (or `codetag.exe`) executable in a directory that is in your system's `PATH` (e.g., `/usr/local/bin` on macOS/Linux).

No dependencies or runtimes are required.

### Usage

The primary command is `scan`. It takes a single argument: the path to the directory you want to analyze.

```bash
# Analyze the current directory and print the report to the console
codetag scan .

# Analyze a specific project directory
codetag scan /path/to/my-project

# Save the report to a file instead of printing it
codetag scan . -o report.json

# Include hidden files and directories (like .git) in the analysis
codetag scan . -i
```

### Packing Source for AI Context

CodeTag can also **pack all relevant source code into a single text file**, ideal for providing context to large-language models (LLMs). The command respects your `.gitignore`, skips oversized files, and lets you fine-tune what gets included.

```bash
# Pack a project and save the output
codetag pack /path/to/my-project -o context.txt

# Increase the maximum file size (e.g., 200 KB)
codetag pack . -o context.txt --max-file-size-kb 200

# Exclude additional extensions
codetag pack . -o context.txt --exclude-extensions ".md,.log"
```

ℹ️  The `pack` command is a **Pro feature**. Activate your license first:

```bash
codetag activate <key> <email>
```

### Sample Output

The tool outputs a single, well-structured JSON object.

<details>
<summary>Click to expand sample JSON report</summary>

```json
{
  "analysis_metadata": {
    "report_version": "1.0",
    "timestamp": "2025-10-26T10:00:00Z",
    "analysis_duration_seconds": 1.25
  },
  "repository_summary": {
    "total_files": 451,
    "total_lines_of_code": 28340,
    "primary_language": "JavaScript",
    "language_stats": {
      "JavaScript": 21050,
      "HTML": 4500,
      "CSS": 2790
    }
  },
  "directory_tree": [
    {
      "name": "client",
      "type": "directory",
      "size_bytes": 120450,
      "children": [
        { "name": "src", "type": "directory", "size_bytes": 110400, "children": [] }
      ]
    },
    { "name": "package.json", "type": "file", "size_bytes": 1234, "children": null }
  ],
  "key_files": {
    "largest_files": [
      {
        "path": "server/api/PaymentHandler.js",
        "size_bytes": 8192
      }
    ],
    "important_files_detected": [
      "Dockerfile",
      "README.md",
      "package.json",
      "server/server.js"
    ]
  },
  "code_insights": {
    "todo_count": 42,
    "fixme_count": 7
  }
}
```
</details>

### License

This is a commercial software product. Your use of the software is governed by the terms of the End-User License Agreement (EULA) included with your download. 