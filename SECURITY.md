# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in Docglow, please report it responsibly by emailing **security@docglow.com** or by opening a [GitHub Security Advisory](https://github.com/docglow/docglow/security/advisories/new).

Please do not open public issues for security vulnerabilities.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.9.x | Yes |
| < 0.9.0 | No (0.1.0–0.4.1: see advisory below) |

## Known Security Advisories

### API Key Embedding in Generated Sites (versions 0.1.0–0.4.1)

**Affected versions:** 0.1.0, 0.2.0, 0.3.0, 0.4.0, 0.4.1

**Issue:** When using the `--ai` flag, the Anthropic API key was embedded in the generated site output (`window.__DOCGLOW_DATA__`), making it visible in the HTML source to anyone viewing a deployed site.

**Fix:** Resolved in version 0.5.0 (PR #49). The API key is no longer embedded in the output. Users enter their key in the chat panel UI, which stores it in the browser's sessionStorage.

**Action required:** If you deployed a site generated with `--ai` on versions 0.1.0–0.4.1, rotate your Anthropic API key immediately. Upgrade to version 0.5.0 or later.

**Affected PyPI versions have been yanked.**
