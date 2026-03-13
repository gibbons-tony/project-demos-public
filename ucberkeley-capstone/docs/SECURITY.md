# Security and Credential Management

This document describes how the Forecast Agent project secures sensitive credentials and prevents API keys from being exposed in the public repository.

## Table of Contents

1. [Security Audit Results](#security-audit-results)
2. [Automated Protection Mechanisms](#automated-protection-mechanisms)
3. [Secure Credential Storage](#secure-credential-storage)
4. [Developer Guidelines](#developer-guidelines)
5. [Emergency Response](#emergency-response)

---

## Security Audit Results

**Last Audit**: October 31, 2025

### Findings

- **No exposed API keys found** in codebase
- **No AWS credentials** committed to repository
- **No Databricks tokens** in tracked files
- All `.pem` files found are legitimate CA certificates (botocore/certifi bundles)

### Scanned Patterns

The audit checked for:
- `DATABRICKS_TOKEN`, `DATABRICKS_HOST`
- AWS access keys (pattern: `AKIA[0-9A-Z]{16}`)
- Generic API keys and secrets
- Connection strings and endpoints
- Password/credential files

---

## Automated Protection Mechanisms

The project uses multiple layers of automated protection to prevent credential exposure:

### 1. Comprehensive .gitignore

**Location**: `.gitignore:80-132`

Blocks the following file types from being committed:

**Cloud Credentials**:
```gitignore
.databrickscfg
*.pem
.aws/credentials
.aws/config
**/aws_credentials.json
```

**API Keys and Secrets**:
```gitignore
.env
.env.*
!.env.example
.secrets
secrets.yaml
secrets.json
**/credentials.json
**/service-account*.json
```

**SSH and GPG Keys**:
```gitignore
id_rsa
id_rsa.pub
id_ecdsa
id_ed25519
*.gpg
*.asc
```

**OAuth and Passwords**:
```gitignore
.token
.tokens
oauth_token*
passwords.txt
*.password
*.secret
```

### 2. Pre-commit Hooks with Secret Detection

**Location**: `.pre-commit-config.yaml:59-65`

Automatically scans for secrets before every commit using [detect-secrets](https://github.com/Yelp/detect-secrets):

```yaml
- repo: https://github.com/Yelp/detect-secrets
  rev: v1.5.0
  hooks:
    - id: detect-secrets
      args: ['--baseline', '.secrets.baseline']
      exclude: '\.ipynb$|\.html$|\.lock$|package-lock\.json$|cacert\.pem$'
```

**Installation**:
```bash
pip install pre-commit detect-secrets
pre-commit install
```

**How it works**:
- Runs automatically before each `git commit`
- Scans for 20+ types of secrets (AWS keys, GitHub tokens, JWT, private keys, etc.)
- Blocks commits containing potential secrets
- Uses baseline file to track known false positives

**Manual scan**:
```bash
# Scan entire repository
detect-secrets scan

# Update baseline (after reviewing findings)
detect-secrets scan --baseline .secrets.baseline
```

### 3. Security Vulnerability Scanning

**Location**: `.pre-commit-config.yaml:52-57`

Uses [Bandit](https://github.com/PyCQA/bandit) to detect security vulnerabilities:

```yaml
- repo: https://github.com/PyCQA/bandit
  rev: 1.7.10
  hooks:
    - id: bandit
```

Detects:
- Hardcoded passwords
- SQL injection risks
- Insecure deserialization
- Weak cryptography
- And 50+ other security issues

---

## Secure Credential Storage

### Recommended Approaches

#### 1. Environment Variables (Recommended for Local Development)

Store credentials as environment variables, never in code:

```python
import os

# CORRECT
databricks_token = os.environ.get('DATABRICKS_TOKEN')
aws_key = os.environ.get('AWS_ACCESS_KEY_ID')

# WRONG - Never do this!
databricks_token = "dapi1234567890abcdef"
```

**Setup**:

Create a `.env` file (automatically ignored by git):
```bash
# .env
DATABRICKS_TOKEN=your_token_here
DATABRICKS_HOST=your_workspace.cloud.databricks.com
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
```

Load in Python:
```python
from dotenv import load_dotenv
import os

load_dotenv()  # Loads .env file
token = os.environ.get('DATABRICKS_TOKEN')
```

**Install python-dotenv**:
```bash
pip install python-dotenv
```

#### 2. AWS Secrets Manager (Recommended for Production)

For production deployments, use AWS Secrets Manager:

```python
import boto3
from botocore.exceptions import ClientError

def get_secret(secret_name):
    """Retrieve secret from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name='us-west-2'
    )

    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response['SecretString']
    except ClientError as e:
        raise Exception(f"Failed to retrieve secret: {e}")

# Usage
databricks_token = get_secret('forecast-agent/databricks-token')
```

**Create secret**:
```bash
aws secretsmanager create-secret \
  --name forecast-agent/databricks-token \
  --secret-string "dapi1234567890abcdef" \
  --region us-west-2
```

#### 3. Databricks Secret Scopes

For Databricks-specific credentials:

```python
# In Databricks notebook
dbutils.secrets.get(scope="forecast-agent", key="api-token")
```

**Create scope**:
```bash
databricks secrets create-scope --scope forecast-agent
databricks secrets put --scope forecast-agent --key api-token
```

#### 4. macOS Keychain (Recommended for Local Mac Development)

Store credentials securely in macOS Keychain:

```python
import keyring

# Store credential
keyring.set_password("forecast-agent", "databricks_token", "dapi1234567890")

# Retrieve credential
token = keyring.get_password("forecast-agent", "databricks_token")
```

**Install keyring**:
```bash
pip install keyring
```

### What NOT to Do

- **Never commit** `.env` files
- **Never hardcode** credentials in Python files
- **Never commit** `.databrickscfg` or AWS credentials
- **Never store** secrets in Jupyter notebooks
- **Never include** credentials in git commit messages
- **Never share** credentials via Slack, email, or other messaging

---

## Developer Guidelines

### Before Your First Commit

1. **Install pre-commit hooks**:
   ```bash
   pip install pre-commit
   pre-commit install
   ```

2. **Verify gitignore**:
   ```bash
   git status
   # Ensure no .env, .databrickscfg, or credential files appear
   ```

3. **Test secret detection**:
   ```bash
   pre-commit run detect-secrets --all-files
   ```

### Daily Development Workflow

1. **Store credentials in `.env`** (never commit this file)
2. **Use environment variables** in code: `os.environ.get('KEY')`
3. **Pre-commit hooks** will block commits with secrets
4. **Review warnings** if pre-commit detects potential secrets

### Adding New Credentials

When you need to add new API keys or credentials:

1. **Add to `.env`** (local development):
   ```bash
   echo "NEW_API_KEY=your_key_here" >> .env
   ```

2. **Update `.env.example`** (template for other developers):
   ```bash
   echo "NEW_API_KEY=your_key_here_placeholder" >> .env.example
   ```

3. **Document in this file** under [Secure Credential Storage](#secure-credential-storage)

4. **For production**, add to AWS Secrets Manager:
   ```bash
   aws secretsmanager create-secret \
     --name forecast-agent/new-api-key \
     --secret-string "your_key_here"
   ```

### Code Review Checklist

When reviewing pull requests, verify:

- [ ] No hardcoded credentials in code
- [ ] No `.env` files in changeset
- [ ] No `.databrickscfg` or AWS credentials
- [ ] Environment variables used for all secrets
- [ ] Pre-commit hooks passed
- [ ] No credential patterns in commit messages

---

## Emergency Response

### If You Accidentally Commit a Secret

**CRITICAL**: Act immediately. Pushed secrets are public and must be revoked.

#### Step 1: Revoke the Credential

**Databricks**:
```bash
# Revoke token via UI: User Settings → Access Tokens → Revoke
# Or via API:
curl -X DELETE https://your-workspace.cloud.databricks.com/api/2.0/token/delete \
  -H "Authorization: Bearer <token>" \
  -d '{"token_id": "abc123"}'
```

**AWS**:
```bash
# Deactivate key
aws iam delete-access-key --access-key-id AKIA...

# Or via Console: IAM → Users → Security credentials → Deactivate
```

**GitHub** (if exposed):
- GitHub will automatically detect AWS/Azure keys and notify you
- Revoke immediately via AWS/Azure console

#### Step 2: Remove from Git History

**Option A: Remove last commit** (if just pushed):
```bash
# Remove secret from file
vim path/to/file.py

# Amend last commit
git add path/to/file.py
git commit --amend

# Force push (WARNING: rewrites history)
git push --force
```

**Option B: Use BFG Repo-Cleaner** (if in git history):
```bash
# Install BFG
brew install bfg

# Remove secret pattern
bfg --replace-text secrets.txt repo.git

# Clean up
cd repo.git
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push --force
```

**Option C: Contact repository admin** to purge history

#### Step 3: Generate New Credential

Create a replacement credential immediately:

**Databricks**:
- User Settings → Access Tokens → Generate New Token

**AWS**:
```bash
aws iam create-access-key --user-name your-username
```

#### Step 4: Update Documentation

Document the incident in `docs/SECURITY_INCIDENTS.md` (if created):
- Date and time
- What was exposed
- How it was detected
- Actions taken
- Lessons learned

### Reporting Security Issues

If you discover a security vulnerability:

1. **DO NOT** open a public GitHub issue
2. **Email** the project maintainer directly: [insert contact email]
3. **Include**:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if known)

---

## Additional Resources

- [Yelp detect-secrets](https://github.com/Yelp/detect-secrets)
- [AWS Secrets Manager](https://aws.amazon.com/secrets-manager/)
- [Databricks Secret Management](https://docs.databricks.com/security/secrets/index.html)
- [OWASP Secret Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning)

---

## Compliance

This project follows security best practices for:

- **OWASP Top 10** (Sensitive Data Exposure)
- **AWS Security Best Practices** (IAM credential rotation)
- **Databricks Security Best Practices** (Secret scopes)

**Last Updated**: October 31, 2025
