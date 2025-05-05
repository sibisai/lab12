# Contributing to Lab12

Thanks for your interest in improving Lab12! This guide will get you set up and ready to contribute.

🚨 Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before contributing.

---

## 1. Setup

Before you start, make sure you’ve followed the full installation steps:

📖 See [SETUP.md](SETUP.md) for prerequisites and how to run Lab12 locally (manual or Docker).

---

## 2. Running the App Locally

```bash
# from the project root
source venv/bin/activate        # or `venv\\Scripts\\activate` on Windows
uvicorn server.main:app --reload --env-file .env
```

> **Note:** transcripts & notes are stored in local storage by default.

---

## 3. Branching Convention

We follow Git Flow–style branches:

- **Feature** branches:  
  `feature/<short-description>`
- **Bugfix** branches:  
  `bugfix/<short-description>`
- **Hotfix** branches:  
  `hotfix/<short-description>`

Always branch off `main`, and target your PR back to `main`.

---

## 4. Commit Message Convention

Use Conventional Commits:

- `feat:` a new feature
- `fix:` a bug fix
- `refactor:` code change that neither fixes a bug nor adds a feature
- `perf:` a code change that improves performance
- `docs:` documentation only changes
- `chore:` build process or auxiliary tool changes

Example:

```
feat(summarizer): allow custom prompt per user
```

---

## 5. Testing & Linting

> _Testing support coming soon!_

---

## 6. Pull Request Checklist

- You’ve formatted your code (e.g. `black .`)
- Your commit messages follow the convention
- You’ve added or updated documentation in `README.md` or relevant `.md` files
- Your PR describes _what_ and _why_ (not just _how_)

---

## 7. Reporting Issues

If you discover a bug or have a feature request, please open an issue and include:

- A clear description of the problem
- Steps to reproduce (if a bug)
- Expected vs. actual behavior
- Any relevant logs or screenshots

---

Thanks for helping make Lab12 better! 🎉
