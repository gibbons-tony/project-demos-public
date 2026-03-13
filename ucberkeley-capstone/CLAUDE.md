# Claude Code Workflow Instructions

**Purpose:** Checklist to prevent errors when working across this multi-component capstone project

**Note:** Component-specific patterns in forecast_agent/CLAUDE.md, research_agent/CLAUDE.md, trading_agent/CLAUDE.md are automatically loaded when working in those folders.

**Collaboration Philosophy:** The user is very open to questions and suggestions. If you're ever unclear, ask or offer them options - this is a collaboration.

---

## Documentation Structure (CRITICAL)

**This project uses hierarchical documentation.** Before performing ANY task:

1. **Read relevant documentation FIRST** from the appropriate folder
2. Start with the component README.md for overview
3. Follow links to detailed docs/ files for specifics
4. Never search for files - all paths are explicit in the hierarchy

**Full Documentation Strategy**: See [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) for:
- Complete hierarchical structure explanation
- "Read X before doing Y" pattern
- Temp document lifecycle and cleanup
- Reference rules and best practices

**Example workflow:**
- Before forecasting work → Read [forecast_agent/README.md](forecast_agent/README.md), then follow links to docs/
- Before research work → Read [research_agent/README.md](research_agent/README.md) for navigation
- Before any task → Check [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) if unsure about doc organization

**Forecast Agent - Read X Before Doing Y:**
- **Before training models** → Read [forecast_agent/docs/ARCHITECTURE.md](forecast_agent/docs/ARCHITECTURE.md) sections on "Train-Once Pattern" and "Model Persistence"
- **Before running Spark backfills** → Read [forecast_agent/docs/SPARK_BACKFILL_GUIDE.md](forecast_agent/docs/SPARK_BACKFILL_GUIDE.md) for cluster sizing and cost optimization
- **Before modifying models** → Read [forecast_agent/docs/ARCHITECTURE.md](forecast_agent/docs/ARCHITECTURE.md) section on "Model Implementation Pattern"
- **Before large backfills** → Read [forecast_agent/README.md](forecast_agent/README.md) for execution environment guidance (local vs Databricks)

---

## Documentation Creation Rules

**Strategic Document Creation:**
- You don't need explicit permission to create .md docs, BUT be strategic and context-aware
- Ask yourself: "Does this add lasting value or create clutter?"
- Temporary analysis/exploration → Use comments in code or ask user if doc needed
- Important decisions/learnings → Create doc (e.g., DECISIONS_AND_LEARNINGS.md)

**Structure Rules:**
- **One .md file per folder maximum** (except docs/ subfolder)
- Additional documentation → Create docs/ subfolder in that folder
- Reference detailed docs from main README.md in that folder
- Follow existing hierarchy patterns (see DOCUMENTATION_STRATEGY.md)

**Temporary Documents:**
- Organizing a complex project → Create temporary doc in tmp/ subfolder
- Examples: tmp/MIGRATION_PLAN.md, tmp/REFACTOR_NOTES.md
- Clean up tmp/ folder once project is complete
- tmp/ folders are useful during active work but should not persist long-term

**File Organization Philosophy:**
- Be very intentional about maintaining a clean, structured file tree
- If you notice files that could be better grouped, **suggest refactoring**
- The user is open to reorganizing the file tree if a better structure is more logical
- Before adding new files, consider: "Is there a better place for this?" or "Should we reorganize?"

**Examples:**
```
Good:
  forecast_agent/README.md                # Main entry point
  forecast_agent/docs/ARCHITECTURE.md     # Detailed guide
  forecast_agent/tmp/REFACTOR_PLAN.md     # Temporary (delete when done)

Bad:
  forecast_agent/README.md
  forecast_agent/NOTES.md                 # Violates one-per-folder rule
  forecast_agent/TODO.md                  # Should be in tmp/ or deleted
```

**Context Awareness:**
- Before creating a new .md, check if existing docs cover the topic
- Consolidate related content rather than proliferating files
- Use temporary document lifecycle (see DOCUMENTATION_STRATEGY.md)

---

## Before Making Any Code Changes

### 1. Read Documentation in Your Working Folder (REQUIRED)
Before writing code in ANY component, ALWAYS read the README.md in that folder:

```bash
# Working in forecast_agent/?
cat forecast_agent/README.md

# Working in research_agent/?
cat research_agent/README.md

# Working in trading_agent/?
cat trading_agent/README.md
```

**Rule:** Read the local README first. It will point you to other docs you need.

### 2. Follow Cross-References (Hierarchical Navigation)
READMEs use **hierarchical documentation** - each component has a docs/ folder with detailed guides:

```
forecast_agent/README.md (concise overview)
  ↓ links to
forecast_agent/docs/ARCHITECTURE.md  (detailed implementation)
  ↓ references
research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md  (data source authority)
```

**Key docs by topic:**
- **Documentation strategy:** `docs/DOCUMENTATION_STRATEGY.md` (read this to understand our doc organization)
- **Data architecture:** `research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md`
- **Forecasting architecture:** `forecast_agent/docs/ARCHITECTURE.md`
- **Spark parallelization:** `forecast_agent/docs/SPARK_BACKFILL_GUIDE.md`
- **Data sources:** `research_agent/docs/DATA_SOURCES.md`
- **Trading system:** `trading_agent/README.md`

**IMPORTANT**: All documentation is reachable from root README.md through explicit links. Never search for files - follow the hierarchy.

### 3. Data Source Rule (Forecasting Only)
When writing **forecasting code specifically**:

❌ **DON'T** query `commodity.bronze.*` tables
✅ **DO** query `commodity.silver.unified_data`

**Why:**
- unified_data has continuous daily coverage (including weekends/holidays)
- All features are forward-filled (no NULLs)
- Bronze tables have gaps (trading days only)

**Note:** Bronze tables are fine for other use cases (data exploration, debugging, etc.)

### 4. Check for Existing Patterns
Before implementing new functionality:

```bash
# Search for similar implementations
grep -r "pattern_name" --include="*.py"
```

**Example:** Before adding a new model:
1. Read [forecast_agent/README.md](forecast_agent/README.md) → [forecast_agent/docs/ARCHITECTURE.md](forecast_agent/docs/ARCHITECTURE.md)
2. Check existing models in `forecast_agent/ml_lib/models/` (baseline.py, linear.py, multi_horizon.py)
3. For legacy context, see `forecast_agent/deprecated/README.md`
4. Follow the train-once/inference-many pattern

### 5. Research Best Practices
When approaching a new task or technology:

- **Search the web** for best practices, common patterns, or modern approaches
- Look for current (2025) best practices and technologies
- Consider if there's a better library, framework, or pattern than what's currently used
- Share findings with the user and suggest improvements

**Examples:**
- "I found a newer approach to X using Y library - would you like to explore this?"
- "Best practices for Z suggest using pattern A instead of B - should we refactor?"
- "This technology has been superseded by X in 2025 - worth considering?"

---

## Data Architecture Quick Reference

```
Bronze (Raw)
  └── commodity.bronze.market          # Trading days only, has gaps
  └── commodity.bronze.weather         # Daily, complete
  └── commodity.bronze.vix             # Trading days only
  └── commodity.bronze.forex           # Weekdays only
  └── commodity.bronze.gdelt           # News sentiment data
         ↓
    Forward-fill + join to continuous daily
         ↓
Gold (Unified Data - ⚠️ USE FOR FORECASTING)
  ├── commodity.gold.unified_data      # Production (forward-filled, no NULLs)
  │   - Grain: (date, commodity)
  │   - 90% fewer rows than silver (7k vs 75k)
  │   - Array-based regional data
  │
  └── commodity.gold.unified_data_raw  # Experimental (NULLs preserved)
      - Requires ImputationTransformer
      - For testing new imputation strategies
         ↓
    Models consume gold tables
         ↓
Gold (Forecast Outputs)
  └── commodity.forecast.distributions # Model outputs (2,000 paths)
  └── commodity.forecast.point_forecasts
  └── commodity.forecast.model_metadata

Legacy (Deprecated Q1 2025):
  └── commodity.silver.unified_data    # 90% larger, exploded regions
```

**Golden Rule:** All forecasting models should query `commodity.gold.unified_data`, NOT bronze or silver tables.

---

## Common Pitfalls (Learn from Past Mistakes)

### ❌ Mistake #1: Querying bronze.market Instead of gold.unified_data
**What happened:** TFT implementation queried `bronze.market` which only has trading days, causing "missing timesteps" error.

**Why wrong:** Bronze tables have gaps (weekends/holidays missing).

**Correct approach:** Query `commodity.gold.unified_data` which has continuous daily data with forward-filled prices.

**File reference:** `research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md`

### ❌ Mistake #2: Creating Docs Without Being Asked
**What happened:** Created `TFT_STATUS.md` proactively without user request.

**Why wrong:** User's instructions say "NEVER proactively create documentation files (*.md)".

**Correct approach:** Only create docs when explicitly requested.

### ❌ Mistake #3: Not Checking git Before Committing
**What happened:** Almost committed hardcoded Databricks credentials in 3 files.

**Why wrong:** GitHub secret scanning would block the push.

**Correct approach:**
```bash
git diff                    # Review all changes
grep -r "dapi" --include="*.py"  # Check for hardcoded tokens
```

---

## File Permissions / Ownership

**Component Ownership:**
- **forecast_agent/** - Owned by Connor
- **research_agent/** - Shared among all team members
- **trading_agent/** - Owned by Tony

**Rules:**
- If working with Connor → Can modify `forecast_agent/*` and `research_agent/*`
- If working with Tony → Can modify `trading_agent/*` (see trading_agent/CLAUDE.md)
- If working with other team members → Can modify `research_agent/*` only
- **All team members** can modify: `collaboration/*`, `docs/*`

**Always Ask First:**
- `infra/*` (infrastructure changes, contains credentials)
- Root-level config files (.gitignore, setup files)

**Never Commit:**
- `.env` files (credentials)
- `infra/*` contents (credentials)
- Files in `trading_agent/*` unless you are Tony's AI assistant

---

## Credential Management

### ✅ Correct Pattern
```python
import os
token = os.environ['DATABRICKS_TOKEN']
```

### ❌ Wrong Pattern
```python
token = "dapi_fake_example_token_12345"  # Hardcoded! Never do this!
```

**Always use:** Environment variables via `os.environ` or load from `../infra/.env`

---

## Before Pushing to Git

### Pre-Push Checklist
```bash
# 1. Review all changes
git status
git diff

# 2. Check for hardcoded secrets
grep -r "dapi" forecast_agent/ research_agent/
grep -r "https://dbc-" forecast_agent/ research_agent/

# 3. Verify no trading_agent changes (unless explicitly asked)
git status | grep trading_agent

# 4. Test locally first
python -m pytest tests/
```

### Git Commit Message Format
```
Brief description (imperative mood)

- Bullet points of what changed
- Why the change was needed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Databricks Infrastructure Rules (CRITICAL)

**NEVER use Databricks Serverless - it is extremely expensive!**

**Instead:**
- **For SQL queries** → Use Unity Catalog SQL warehouse
- **For notebooks/Python** → Use dedicated clusters

**Finding or Creating Clusters:**
1. Check component's `infrastructure/databricks/clusters/` folder for existing cluster configs
2. Examples:
   - `forecast_agent/infrastructure/databricks/clusters/`
   - `research_agent/infrastructure/databricks/clusters/`
3. If no suitable cluster exists → Use Databricks API to create one (see cluster config examples)
4. DO NOT create Serverless compute

**Example: List existing clusters**
```bash
databricks clusters list
```

**Example: Create cluster via API**
```python
# See forecast_agent/infrastructure/databricks/clusters/create_ml_clusters.py
# Use similar pattern with appropriate cluster config
```

---

## Databricks Deployment Workflow

**Full workflow: Local Development → Git → Databricks → Execution**

### 1. Local Development & Git Push
```bash
# Develop locally in forecast_agent/ or research_agent/
# Test changes
# Push to GitHub
git add .
git commit -m "description"
git push origin main
```

### 2. Pull into Databricks
```bash
# In Databricks Repos UI: Pull latest from GitHub
# OR via CLI:
databricks repos update --path /Repos/your-user/ucberkeley-capstone --branch main
```

### 3. Deploy Package to Cluster (forecast_agent only)
```bash
# Build wheel, upload to DBFS, install on cluster
cd forecast_agent
python infrastructure/databricks/clusters/deploy_package.py

# This enables: from ml_lib.models import ...
```

### 4. Run on Databricks
```bash
# Option A: Run notebook in Databricks UI (attach to existing cluster!)
# Option B: Submit job via CLI
databricks jobs run-now --job-id 123

# Option C: Run Python script directly
databricks workspace import-dir notebooks /Repos/your-user/ucberkeley-capstone/forecast_agent/notebooks
```

**Key Points:**
- **NEVER use Serverless** - expensive!
- **forecast_agent** requires package deployment (setup.py → wheel → DBFS)
- **research_agent** Lambda functions deployed via AWS (deploy.sh scripts)
- **trading_agent** uses Databricks notebooks (no package deployment needed)
- Always pull latest from Git before running in Databricks
- See component-specific CLAUDE.md for detailed deployment patterns

---

## Quick Wins

### Instead of Guessing, Check Docs
```bash
# Before: "I think I should query bronze.market"
# After: "Let me read UNIFIED_DATA_ARCHITECTURE.md first"

cat research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md | grep -A 10 "unified_data"
```

### Instead of Creating Temp Files, Ask
```bash
# Before: Write TFT_STATUS.md
# After: "Should I document this?"
```

### Instead of Assuming, Verify
```bash
# Before: "Coffee data has weekends"
# After: Query unified_data to check date coverage
```

---

## Workflow Summary

```
┌─────────────────────────────────────────┐
│ User Requests Feature                   │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│ 1. Read relevant docs FIRST             │
│    - Component README.md for overview   │
│    - Follow links to docs/ for details  │
│    - Check DOCUMENTATION_STRATEGY.md    │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│ 2. Understand data source               │
│    - Use unified_data for forecasting   │
│    - Check grain, coverage, nulls       │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│ 3. Implement solution                   │
│    - Follow existing patterns           │
│    - Use env vars for credentials       │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│ 4. Test locally                         │
│    - Query Databricks to verify         │
│    - Check for edge cases               │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│ 5. Review before commit                 │
│    - git diff                           │
│    - Check for secrets                  │
│    - Verify no trading_agent changes    │
└───────────┬─────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│ 6. Commit and push                      │
└─────────────────────────────────────────┘
```

---

## Emergency Reference

**If in doubt:**
1. Read [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) to understand doc organization
2. Read component README.md, then follow links to detailed docs/
3. Be strategic about creating new docs (follow "Documentation Creation Rules" above)
4. Query `commodity.gold.unified_data` for forecasting (NOT bronze or silver tables)
5. Never hardcode credentials
6. Respect component ownership (Tony owns trading_agent/)

**When stuck:**
1. Read relevant documentation FIRST (follow hierarchical links)
2. Check existing code for patterns
3. **Ask the user for clarification** - they're open to questions and suggestions
4. Offer options if multiple approaches are viable
5. Don't guess - verify with data queries

**Documentation Quick Links:**
- [docs/DOCUMENTATION_STRATEGY.md](docs/DOCUMENTATION_STRATEGY.md) - How we organize docs
- [forecast_agent/README.md](forecast_agent/README.md) - Forecast agent guide
- [forecast_agent/docs/ARCHITECTURE.md](forecast_agent/docs/ARCHITECTURE.md) - Train-once architecture
- [forecast_agent/docs/SPARK_BACKFILL_GUIDE.md](forecast_agent/docs/SPARK_BACKFILL_GUIDE.md) - Spark parallelization
- [research_agent/README.md](research_agent/README.md) - Research agent guide
- [research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md](research_agent/docs/UNIFIED_DATA_ARCHITECTURE.md) - Data architecture

---

**Document Owner:** Claude Code (AI Assistant)
**Last Updated:** 2025-11-12
**Purpose:** Prevent repeated mistakes, establish workflow discipline
