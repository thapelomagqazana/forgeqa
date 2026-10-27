# Security Policy

> **Project Status: Pre-alpha**
>
> ForgeQA is a reusable, evidence-first Python test automation foundation. This document outlines the security policy, supported versions, and reporting process for security vulnerabilities.

---

## Table of Contents

1. [Supported Versions](#1-supported-versions)
2. [Reporting a Vulnerability](#2-reporting-a-vulnerability)
3. [Response Timeline](#3-response-timeline)
4. [Security Controls](#4-security-controls)
5. [Known Limitations](#5-known-limitations)
6. [Security Best Practices for Users](#6-security-best-practices-for-users)
7. [Dependency Management](#7-dependency-management)
8. [Data Handling and Privacy](#8-data-handling-and-privacy)
9. [Security Hall of Fame](#9-security-hall-of-fame)

---

## 1. Supported Versions

ForgeQA is currently in **pre-alpha** (Phase 0–1). Only the latest commit on `main` is supported for security updates. Once ForgeQA reaches a stable release (1.0.0+), this table will be updated with LTS versions.

| Version | Supported | Notes |
| :--- | :--- | :--- |
| `main` (pre-alpha) | ✅ | Active development. Security fixes applied. |
| `0.x.y` (pre-release) | ⚠️ | Security fixes applied to the latest `0.x` release only. |
| `< 0.1.0` | ❌ | Not supported. |

---

## 2. Reporting a Vulnerability

**Do not open a public GitHub Issue for security vulnerabilities.** Public disclosure puts all users at risk.

### 2.1 How to Report

Report security issues **privately** via one of the following channels:

| Channel | Link | Preferred |
| :--- | :--- | :--- |
| **GitHub Security Advisories** | [Report a vulnerability](https://github.com/thapelomagqazana/forgeqa/security/advisories/new) | ✅ **Recommended** |
| **Email** | `maintainer@forgeqa.dev` | Alternative |

### 2.2 What to Include

A good security report includes:

1. **Description**: A clear description of the vulnerability.
2. **Impact**: What can an attacker do? What data is at risk?
3. **Steps to reproduce**: Minimal code or configuration to trigger the issue.
4. **Affected versions**: Which versions of ForgeQA are affected?
5. **Suggested fix**: If you have one (optional).
6. **Your contact**: How to reach you for follow-up.

### 2.3 What NOT to Include

- Do **not** include real credentials, API keys, or production data in your report.
- Do **not** open a public PR that fixes the vulnerability without prior coordination.

---

## 3. Response Timeline

ForgeQA is maintained by a solo developer. The following timelines are targets, not guarantees:

| Stage | Target |
| :--- | :--- |
| **Acknowledgment** | Within 5 business days. |
| **Initial assessment** | Within 10 business days. |
| **Fix or mitigation** | Within 30 business days (severity-dependent). |
| **Public disclosure** | After a fix is released, coordinated with the reporter. |

If you do not receive an acknowledgment within 5 business days, please follow up via email.

---

## 4. Security Controls

ForgeQA implements the following security controls. They are documented here so that users and auditors can verify them.

### 4.1 Secret Management

| Control | Implementation | Status |
| :--- | :--- | :--- |
| No secrets in source control | `.gitignore` excludes `.env`, `*.pem`, `*.key`. | ✅ Implemented |
| Secret scanning | `gitleaks` pre-commit hook blocks commits with hardcoded secrets. | ✅ Implemented |
| Secret injection | Configuration reads credentials from environment variables or a secret manager. | 🔄 Phase 1 |
| Redaction in logs | Diagnostics redact passwords, tokens, cookies, and sensitive headers. | 🔄 Phase 3 |

### 4.2 Dependency Security

| Control | Implementation | Status |
| :--- | :--- | :--- |
| Dependency auditing | `pip-audit` runs in CI (Phase 8). | 🔄 Phase 8 |
| Dependency pinning | `pyproject.toml` uses `>=` constraints; `uv.lock` for reproducibility. | 🔄 Phase 1 |
| Automated updates | Dependabot (or Renovate) creates weekly update PRs. | 🔄 Phase 1 |
| SBOM generation | CycloneDX SBOM produced at release (Phase 8). | 🔄 Phase 8 |

### 4.3 Artifact Security

| Control | Implementation | Status |
| :--- | :--- | :--- |
| Controlled output directory | Artifacts written to `artifacts/` (gitignored). | ✅ Implemented |
| Redaction in artifacts | Structured JSON and JUnit XML redact sensitive fields. | 🔄 Phase 3 |
| Artifact retention | Configurable retention policy (Phase 8). | 🔄 Phase 8 |
| Screenshot/trace warnings | Documentation warns that screenshots and traces may contain sensitive content. | 🔄 Phase 3 |

### 4.4 CI/CD Security

| Control | Implementation | Status |
| :--- | :--- | :--- |
| Least-privilege permissions | GitHub Actions workflows use `permissions: contents: read`. | ✅ Implemented |
| No secrets in fork PRs | Workflows do not expose secrets to untrusted fork code. | ✅ Implemented |
| Pinned action versions | Actions pinned to reviewed versions or commit SHAs. | 🔄 Phase 1 |
| Quality gates | Linting, type checking, and tests must pass before merge. | ✅ Implemented |

### 4.5 Code Quality

| Control | Implementation | Status |
| :--- | :--- | :--- |
| Static analysis | Ruff (lint) and MyPy (type checking) run on every commit. | ✅ Implemented |
| Conventional Commits | Commit messages follow a structured format (traceability). | ✅ Implemented |
| ADR validation | Architecture decisions are documented and validated. | ✅ Implemented |

---

## 5. Known Limitations

ForgeQA is a **testing framework**. It interacts with external systems (browsers, APIs, databases) and captures diagnostic evidence (screenshots, traces, request/response metadata). The following limitations are known:

| Limitation | Impact | Mitigation |
| :--- | :--- | :--- |
| **Screenshots and traces cannot be fully sanitised** | Binary artifacts may contain sensitive UI content, URLs, or headers. | Users must configure capture policies and restrict access to artifacts. |
| **Arbitrary secrets cannot be detected** | ForgeQA redacts known secrets (from configuration) but cannot detect unknown secrets in third-party logs. | Use synthetic test data; never run against production data without approval. |
| **No multi-user access control** | ForgeQA's core framework has no built-in RBAC. | Access is controlled by the OS, CI provider, or a future control plane (Phase 10). |
| **No formal security certification** | ForgeQA is not certified for SOC 2, ISO 27001, or POPIA compliance. | Pilot organisations must perform their own security review. |

---

## 6. Security Best Practices for Users

### 6.1 Configuration

- **Never commit `forgeqa.toml` with real credentials.** Use environment variables or a `.env` file (gitignored).
- **Use the `.env.example` template** (if provided) to document required variables without exposing values.

### 6.2 Test Data

- **Use synthetic test data by default.** Do not use production customer data.
- **Use reserved example domains** (e.g., `@example.test`) for synthetic emails.
- **Clean up test data** using ownership-aware cleanup (Phase 5).

### 6.3 Artifacts

- **Restrict access to the `artifacts/` directory.** It may contain screenshots, traces, and API metadata.
- **Configure retention** to delete artifacts after a defined period (Phase 8).
- **Redact secrets** before sharing artifacts with anyone outside your team.

### 6.4 CI/CD

- **Do not expose secrets to fork PRs.** Use `pull_request` (not `pull_request_target`) for untrusted code.
- **Pin third-party actions** to reviewed versions or commit SHAs.
- **Use least-privilege permissions** for `GITHUB_TOKEN`.

### 6.5 Reporting Vulnerabilities

- **Do not open public issues** for security vulnerabilities.
- **Use GitHub Security Advisories** or email `maintainer@forgeqa.dev`.

---

## 7. Dependency Management

### 7.1 Supported Versions

ForgeQA supports:

- **Python**: 3.11 and 3.12 (see `docs/engineering-standards.md`).
- **Pytest**: `>=9.2.0`.
- **Pydantic**: `>=2.14.1`.
- **Playwright**: `>=1.64.1` (optional).
- **HTTPX**: `>=0.27` (optional).

### 7.2 Vulnerability Scanning

| Tool | Purpose | Frequency |
| :--- | :--- | :--- |
| **gitleaks** | Detect hardcoded secrets. | Every commit (pre-commit hook). |
| **pip-audit** | Detect known vulnerabilities in Python dependencies. | Every CI run (Phase 8). |
| **Dependabot** | Automated dependency update PRs. | Weekly (Phase 1). |

### 7.3 Remediation Policy

| Severity | Action | Timeline |
| :--- | :--- | :--- |
| **Critical** | Block release until fixed or formally accepted. | Immediate. |
| **High** | Normally block release; exception requires review. | Within 7 days. |
| **Medium** | Triage based on exposure and available fixes. | Within 30 days. |
| **Low** | Triage based on risk. | Next release cycle. |

---

## 8. Data Handling and Privacy

### 8.1 Data Collected by ForgeQA

ForgeQA itself does **not** collect telemetry or send data to external services. However, it **captures** data during test execution:

| Data Type | Captured By | Retention | Redaction |
| :--- | :--- | :--- | :--- |
| Screenshots | UI adapter (on failure) | Configurable | Not automatically sanitised (binary). |
| Traces | UI adapter (on failure) | Configurable | Not automatically sanitised (binary). |
| API request/response metadata | API adapter (on failure) | Configurable | Headers and bodies redacted by default. |
| Logs | Framework | Configurable | Secrets redacted. |
| Test results (JUnit XML, JSON) | Reporting | Configurable | Secrets redacted. |

### 8.2 POPIA/GDPR Considerations

For South African deployments, users must consider the **Protection of Personal Information Act (POPIA)**:

- **Personal information** in screenshots, traces, or API bodies must be minimised and protected.
- **Retention periods** for artifacts must be defined and enforced (Phase 8).
- **Access controls** for artifacts must be appropriate to the sensitivity of the data.
- **Data minimisation**: Use synthetic data by default; do not use production data without approval.

ForgeQA does **not** claim POPIA compliance. Users are responsible for configuring the framework appropriately for their regulatory context.

---

## 9. Security Hall of Fame

We gratefully acknowledge security researchers who report vulnerabilities responsibly.

*No reports yet. Be the first to help make ForgeQA more secure.*

---

## 10. Document History

| Version | Date | Author | Changes |
| :--- | :--- | :--- | :--- |
| 0.1.0 | 2026-10-27 | Solo Dev | Initial security policy created. |

---

*This document is a living artifact. It will be updated as ForgeQA progresses through Phase 8 (Security Hardening) and beyond.*
