# Pull Request

## 📝 What

<!-- Describe what this PR changes. Be specific. -->

## 🎯 Why

<!-- Why is this change needed? Link to the WBS task, issue, or ADR. -->

Closes #<!-- issue number -->

## 🔧 How

<!-- Brief technical summary of the approach. What are the key design decisions? -->

## 🧪 Testing

<!-- How did you test this? Include commands, screenshots, or links to CI runs. -->

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed (describe below)

**Manual testing steps:**
1.
2.
3.

## 📋 Checklist

### Code Quality
- [ ] `make check` passes (lint, format, typecheck)
- [ ] `make test` passes
- [ ] `make adr-validate` passes (if ADRs were changed)
- [ ] No new warnings introduced
- [ ] Public functions have type hints
- [ ] Any `# type: ignore` has an explanatory comment

### Documentation
- [ ] `README.md` updated (if user-facing)
- [ ] `docs/` updated (if architecture or behaviour changed)
- [ ] `CHANGELOG.md` updated (if user-facing)
- [ ] ADR created/updated (if architectural decision)

### Security
- [ ] No secrets or credentials committed
- [ ] No sensitive data in logs or artifacts
- [ ] Dependencies reviewed (if new dependency added)

### CI
- [ ] All GitHub Actions checks pass
- [ ] No CI warnings that could become errors in future

## 📸 Screenshots / Evidence

<!-- If applicable, add screenshots or links to CI runs, artifacts, or test reports. -->

## 🔗 Related

<!-- Link to related PRs, issues, ADRs, or external documentation. -->

- Related to #
- Supersedes #
- See ADR-XXX

## 📝 Notes for Reviewers

<!-- Anything the reviewer should pay special attention to? Any known limitations? -->
