# Ask IT TODO

This file tracks items that are no longer blocked by app development and require action from IT / infrastructure / tenant administrators.

## Microsoft 365 SMTP For Password Reset Emails

Purpose:
Enable the Product Finder app to send password reset emails from Microsoft 365.

What IT should provide or confirm:
- Create or assign a dedicated mailbox for app sending.
- Recommended example: `noreply@yourdomain.com`
- Confirm SMTP host: `smtp.office365.com`
- Confirm SMTP port: `587`
- Confirm SMTP username: full mailbox email address
- Confirm sender/from email address
- Prefer using the same address for username and from email
- Confirm whether SMTP AUTH is enabled for that mailbox
- Confirm whether SMTP AUTH is enabled at tenant level
- Confirm whether MFA is enabled on that mailbox
- If MFA is enabled, provide the supported SMTP-compatible method
  - app password, or
  - approved tenant-specific alternative
- Confirm whether tenant security policies block authenticated SMTP
- If the sender address differs from the mailbox address, grant `Send As` permission

Values needed in the app admin Settings panel:
- `SMTP Host`
- `SMTP Port`
- `SMTP Username`
- `SMTP Password`
- `SMTP From Email`

Recommended IT message:

We need a Microsoft 365 mailbox for application email sending for the Product Finder app, specifically for password reset emails.

Please provide or enable:
- a mailbox dedicated to app sending
- SMTP AUTH enabled for that mailbox
- use with `smtp.office365.com` on port `587` with STARTTLS
- the SMTP username
- the sender/from address
- the password or app-password method allowed for SMTP
- confirmation that tenant security policies do not block authenticated SMTP for this mailbox

If SMTP AUTH is disabled by policy, please advise the supported alternative for app-based outbound email.

Common failure causes to mention to IT:
- SMTP AUTH disabled at tenant or mailbox level
- MFA blocking SMTP login
- wrong sender permissions (`Send As` not granted)
- use of an alias instead of a real mailbox

Status:
- App side: implemented
- IT side: pending

## Optional Follow-Up For Production

If IT is involved in go-live later, they may also need to support:
- DNS for the final app domain
- HTTPS / certificate-related mailbox ownership confirmation
- mailbox retention or auditing requirements for outbound app mail
