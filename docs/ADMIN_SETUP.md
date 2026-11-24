# Administrator accounts and roles

Roles in the database: `patient`, `provider`, `admin`. A provider has `provider_type` `counsellor` or `doctor`; a doctor can prescribe only while an administrator of the institution has verified the registration. Contract: [CLINICAL_DESIGN.md](CLINICAL_DESIGN.md).

## Creating the first administrator

Administrators are never created from a web form and never from an invite code. The operator runs a command with shell access. It uses whatever `DATABASE_URL` is set, so it can be run from your own machine against Neon:

```
# PowerShell
$env:DATABASE_URL = "postgresql://...neon..."
$env:SKIP_CREATE_ALL = "1"
flask --app app.py create-admin --email you@college.edu --name "Your Name" --institution "Your University" --pharmacy-desk
```

The password is asked twice with a hidden prompt. For scripts, put it in an environment variable and pass its name: `--password-env NEW_ADMIN_PW` (never the password itself on the command line). It must have 8 or more characters with upper and lower case letters, a digit and a special character. The command refuses an email that already exists, so it cannot promote a student or counsellor. `--pharmacy-desk` also makes the account the pharmacy desk (dispensing and stock changes); leave it out for an administrator who should only see aggregates.

Other commands (all audited, all need the account to have the matching role):

| Command | Purpose |
|---------|---------|
| `flask set-pharmacy-desk --email E --on` or `--off` | give or remove the desk capability |
| `flask admin-set-password --email E` | reset an administrator password |
| `flask set-provider-type --email E --type doctor` | make a provider a doctor (creates a pending prescriber profile) or a counsellor |
| `flask ops-daily-schedule` | queue the nightly job (expiry, stock alerts, re-check reminders); the dashboard also does this |

Administrators sign in at `/admin/login`, not on the main sign-in page. Google sign-in refuses administrator accounts.

## Doctors and counsellors

- Counsellor signup: `PROVIDER_INVITE_CODE`. Doctor signup: `DOCTOR_INVITE_CODE` plus the registration number, council and year. The two codes must differ; if they are equal doctor signup is disabled. Unset means closed.
- A new doctor is `pending` and behaves like a counsellor until an administrator of the same institution checks the entry in the Indian Medical Register and records the check at `/admin/verification`. MindFull Horizon does not query the register itself.
- The check expires after `PRESCRIBER_REVIEW_DAYS` (default 365). Suspending a doctor stops prescribing on their next request.

## Legal status

Legal and pharmacist review of prescribing and dispensing is still pending. The pilot defaults in `.env.example` (item limits, durations, consult window) are product policy, not regulation.
