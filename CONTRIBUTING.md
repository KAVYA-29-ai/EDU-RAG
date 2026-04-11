# Contributing to EduRag

Thank you for your interest in contributing to EduRag! 🎉

## Table of Contents
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Commit Message Guide](#commit-message-guide)
- [Reporting Issues](#reporting-issues)
- [Code Style](#code-style)
- [Code of Conduct](#code-of-conduct)

## Getting Started
1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR-USERNAME/MINI-RAG.git`
3. Install dependencies: `pip install -r requirements.txt` and `npm install`
4. Create a new branch: `git checkout -b feature/your-feature-name`
5. Copy `.env.example` to `.env` and fill in your keys

## How to Contribute
- Make your changes with clear, descriptive commit messages
- Ensure your code follows the existing style
- Add docstrings to any new Python functions
- Add JSDoc comments for key React handlers/components where logic is non-trivial
- Add or update documentation as needed
- Submit a pull request with a clear description of your changes

## Quality Gates Before PR
Run these commands locally before opening a PR:

```bash
# Frontend
npm run lint:js
npm run test:ci

# Backend
pytest -q
```

If your change touches RAG logic, include before/after behavior notes in the PR description.

## Commit Message Guide
Use these prefixes for clean commits:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation changes
- `test:` — adding tests
- `refactor:` — code refactoring
- `chore:` — maintenance tasks
- `ci:` — CI/workflow updates

Example: `feat: add support for DOCX file upload`

## Commit Conventions (Required)
- Keep commits focused and atomic. One intent per commit.
- Avoid noisy messages like `Update file` or `Add files via upload`.
- Prefer imperative, scoped messages such as:
	- `fix: handle missing JWT secret at request time`
	- `docs: update auth endpoint examples`
	- `ci: run backend pytest with coverage`

## Pull Request Checklist
Before opening a PR, confirm all items below:

- [ ] PR title follows conventional format (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`)
- [ ] PR description explains problem, solution, and impact
- [ ] Test evidence is included (commands + key output)
- [ ] No generated artifacts committed (`build/`, coverage reports, local IDE files)
- [ ] Related docs updated if API or behavior changed
- [ ] Changes are split into logical commits with meaningful messages

## Reporting Issues
- Use the [GitHub Issues](https://github.com/KAVYA-29-ai/MINI-RAG/issues) tab
- For bugs: include steps to reproduce, expected vs actual behavior, screenshots
- For features: explain the use case and why it would help

## Code Style
**Python:** Follow PEP8, add docstrings to all functions
**JavaScript:** Use camelCase, add JSDoc comments to key functions
**General:** Keep functions small and single-purpose; prefer extracting duplicate logic into shared helpers/hooks

## Code of Conduct
- Be respectful and inclusive in all interactions
- Follow the [Contributor Covenant](https://www.contributor-covenant.org/)

Thank you for helping make EduRag better! 💙
