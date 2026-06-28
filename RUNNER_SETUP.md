# Self-Hosted GitHub Actions Runner — Windows Setup

The pipeline's Forge step runs the strategy on **your laptop**, so GitHub needs a
self-hosted runner installed here. Do this once. Commands are PowerShell.

> Repo: `zainhussain2003/EoD_OptionTrading`

## 0. Prerequisites (already true on this laptop)

- `python` (3.13+), `git`, `gh` (authenticated as `zainhussain2003`), and the
  `claude` CLI are installed and on PATH.
- You're logged into the `claude` CLI with your subscription (`claude` runs
  without prompting for a key).

## 1. Add the required GitHub secrets

The workflow reads your Alpaca paper keys from repo secrets:

```powershell
gh secret set ALPACA_API_KEY    --repo zainhussain2003/EoD_OptionTrading
gh secret set ALPACA_SECRET_KEY --repo zainhussain2003/EoD_OptionTrading
```

Each command prompts for the value (paste your paper key/secret). Verify:

```powershell
gh secret list --repo zainhussain2003/EoD_OptionTrading
```

## 2. Get a runner registration token

Open the repo's runner settings page (this opens it in your browser):

```powershell
gh repo view zainhussain2003/EoD_OptionTrading --web
```

Then go to **Settings → Actions → Runners → New self-hosted runner →
Windows / x64**. GitHub shows a one-time `--token ...`. Copy it.

(Or fetch a token from the CLI:
`gh api -X POST repos/zainhussain2003/EoD_OptionTrading/actions/runners/registration-token -q .token`)

## 3. Download and configure the runner

```powershell
# Create a folder OUTSIDE the repo (keeps the runner's files out of git)
New-Item -ItemType Directory -Force C:\actions-runner | Out-Null
Set-Location C:\actions-runner

# Download the latest Windows x64 runner (check the version on the runner page;
# update the version number below if GitHub shows a newer one).
$ver = "2.323.0"
Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v$ver/actions-runner-win-x64-$ver.zip" -OutFile runner.zip
Expand-Archive -Path runner.zip -DestinationPath . -Force
Remove-Item runner.zip

# Configure (paste the token from step 2). --unattended avoids prompts.
.\config.cmd --url https://github.com/zainhussain2003/EoD_OptionTrading --token <PASTE_TOKEN> --name "laptop-runner" --labels self-hosted,windows,laptop --unattended
```

## 4. Install it as a Windows service (survives reboots, runs in background)

From `C:\actions-runner`, in an **Administrator** PowerShell:

```powershell
.\svc.cmd install
.\svc.cmd start
.\svc.cmd status
```

The service runs under `NT AUTHORITY\NETWORK SERVICE` by default. **Important:**
that account is *not* logged into your `claude` CLI or `gh`, which Oracle/Herald
need. Run the service as **your own user** so it inherits your logins:

- During `svc.cmd install` you can pass your account:
  `.\svc.cmd install "$env:USERDOMAIN\$env:USERNAME"` and it will prompt for your
  Windows password. Then `.\svc.cmd start`.
- Alternatively, open `services.msc`, find **"GitHub Actions Runner (…)"**, →
  Properties → **Log On** tab → "This account" → enter your Windows user +
  password → restart the service.

> Why this matters: Oracle calls `claude` and Herald calls `gh`, both of which
> use credentials stored in *your* user profile. The Alpaca keys come from the
> GitHub secrets (step 1), so those don't depend on the service account.

Confirm the runner shows **Idle / green** under repo **Settings → Actions →
Runners**.

## 5. Test with the dummy workflow

```powershell
gh workflow run "Runner Smoke Test" --repo zainhussain2003/EoD_OptionTrading
gh run watch --repo zainhussain2003/EoD_OptionTrading
```

It checks Python/git/gh/claude versions on the runner. Green = the runner is
ready. (You can also click **Run workflow** on the Actions tab.)

## 6. Test the full pipeline

From the repo, create a throwaway strategy branch off the template and push:

```powershell
git checkout main; git pull
git checkout -b strategy/smoke-test
New-Item -ItemType Directory -Force strategies\smoke-test | Out-Null
Copy-Item templates\eod_strategy_template\* strategies\smoke-test\ -Recurse
git add strategies\smoke-test
git commit -m "Architect: smoke-test"
git push -u origin strategy/smoke-test
```

Watch the run; within a couple of minutes a PR titled **"Strategy: smoke-test"**
should appear with a metrics comment. Clean up when done:

```powershell
gh pr close strategy/smoke-test --repo zainhussain2003/EoD_OptionTrading --delete-branch
```

## Managing the runner

```powershell
Set-Location C:\actions-runner
.\svc.cmd stop      # pause it
.\svc.cmd start     # resume
.\svc.cmd uninstall # remove the service
.\config.cmd remove --token <NEW_TOKEN>  # deregister from GitHub
```

## Troubleshooting

- **Job stuck "Waiting for a runner":** runner offline — `svc.cmd start`, or check
  `services.msc`.
- **Oracle/Herald fall back / `claude` or `gh` "not logged in":** the service is
  running as the wrong account — set it to your user (step 4).
- **Alpaca auth errors in Forge:** secrets missing/typo'd — redo step 1.
- **Strategy used SIMULATED data:** secrets not reaching the runner, or Alpaca
  request failed — check `results/<name>/run.log`.
