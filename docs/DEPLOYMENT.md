# Deployment

## Current State

This project has been initialized as a standalone local Git repository at:

`/Users/valx/cathedral-prime/03-code/active/gemini-unchained-daemon`

If no remote is configured yet, the repository is still fully ready for a private push.

## Local Validation Before Push

Run:

```bash
cd /Users/valx/cathedral-prime/03-code/active/gemini-unchained-daemon
python3 -m compileall src
PYTHONPATH=src python3 -m unittest discover -s tests -v
gemini-unchained-daemon doctor
```

## Create Or Attach The GitHub Remote

Target repository:

`wearelegion1/gemini-unchained-daemon`

Option 1: attach an existing GitHub repo

```bash
cd /Users/valx/cathedral-prime/03-code/active/gemini-unchained-daemon
git remote add origin git@github.com:wearelegion1/gemini-unchained-daemon.git
```

Option 2: use HTTPS

```bash
cd /Users/valx/cathedral-prime/03-code/active/gemini-unchained-daemon
git remote add origin https://github.com/wearelegion1/gemini-unchained-daemon.git
```

## First Push

```bash
cd /Users/valx/cathedral-prime/03-code/active/gemini-unchained-daemon
git push -u origin main
```

## Recommended Visibility

Use a private repository first.
The runtime is publishable, but the operator should review README wording and any Cathedral-specific examples before making it public.
