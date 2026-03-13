# Documentation Strategy

**Purpose**: This document defines our hierarchical documentation organization strategy for efficient human and AI agent navigation.

## Core Philosophy

**Single Entry Point**: All documentation must be reachable from the root README.md through hierarchical links. No orphaned documents.

**Web-Graph Structure**: Documents form a directed graph where:
- Root README is the entry point
- Each agent folder has its own README linking to detailed docs
- Detailed docs can link to related docs at the same or deeper levels
- Never require file searching - all paths are explicit

## Documentation Hierarchy

```
ucberkeley-capstone/                  # ROOT
├── README.md                         # Human entry point
├── CLAUDE.md                         # AI agent entry point (ONLY at root)
├── docs/                            # Root-level documentation
│   ├── DOCUMENTATION_STRATEGY.md    # This file (how we organize docs)
│   ├── DATA_CONTRACTS.md            # Database schemas (single source of truth)
│   ├── ARCHITECTURE.md              # System architecture
│   ├── SECURITY.md                  # Credential management
│   └── EVALUATION_STRATEGY.md       # Model evaluation approach
│
├── forecast_agent/
│   ├── README.md                    # Concise overview + links to docs/ (both human & AI readable)
│   └── docs/                        # Agent-specific detailed docs
│       ├── ARCHITECTURE.md          # Train-once/inference-many pattern
│       └── SPARK_BACKFILL_GUIDE.md  # Parallel processing guide
│
├── research_agent/
│   ├── README.md                    # Concise overview + links to docs/ (both human & AI readable)
│   └── docs/                        # Agent-specific detailed docs
│       ├── UNIFIED_DATA_ARCHITECTURE.md # Data joining strategy
│       ├── DATA_SOURCES.md          # All data sources explained
│       ├── GDELT_PROCESSING.md      # GDELT sentiment processing
│       ├── BUILD_INSTRUCTIONS.md    # Build and validate gold tables
│       ├── GOLD_MIGRATION_GUIDE.md  # Migration guide for forecast models
│       └── DATABRICKS_MIGRATION_GUIDE.md # Databricks setup
│
└── trading_agent/
    ├── README.md                    # Concise overview + links to docs/
    └── (additional structure TBD)
```

## Documentation Types

### 1. Entry Point Documents

**README.md** (Root and each agent folder)

**Location**: Root and each agent folder

**Purpose**:
- Provide concise overview (both human and AI readable)
- Link to all relevant detailed documentation
- Establish context and quick starts

**Rules**:
- Keep concise (< 300 lines)
- Link extensively to docs/ for details
- No orphaned references
- Update immediately when structure changes
- Serve both human and AI readers

**Example Pattern**:
```markdown
## Quick Start

**BEFORE running backfills, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for:**
- Train-once/inference-many pattern details
- Model persistence strategy
- Performance optimizations

**For Spark parallelization, see [docs/SPARK_BACKFILL_GUIDE.md](docs/SPARK_BACKFILL_GUIDE.md)**
```

**CLAUDE.md** (Root level ONLY)

**Location**: Root of repository only

**Purpose**:
- AI agent workflow guidelines
- General best practices across all agents
- Links to agent-specific READMEs for detailed guidance

**Rules**:
- Root CLAUDE.md contains universal rules (credentials, git workflow, permissions)
- **Each agent folder has component-specific CLAUDE.md** (auto-loaded when working in that folder)
  - forecast_agent/CLAUDE.md (forecasting-specific patterns)
  - research_agent/CLAUDE.md (data pipeline patterns)
  - trading_agent/CLAUDE.md (ownership notice)
- Reference docs/DOCUMENTATION_STRATEGY.md
- Emphasize reading docs before tasks

**Note**: This evolved from initial "only root CLAUDE.md" approach to hierarchical distribution for better focus and context efficiency (Dec 2024).

### 2. Detailed Documentation (docs/*.md)

**Location**: `docs/` folders at root and agent levels

**Purpose**:
- Comprehensive technical details
- Implementation patterns
- Design decisions and rationale
- Troubleshooting guides

**Rules**:
- Must be referenced from parent README or CLAUDE.md
- Can reference other docs/ files at same or deeper level
- Include examples and code snippets
- Maintain single source of truth for each topic

### 3. CLAUDE.md (AI Agent Guide - Root Only)

**Location**: Root of repository ONLY

**Purpose**:
- Guide AI agents to read docs BEFORE executing tasks
- Enforce hierarchical documentation usage
- Prevent context waste from flat documentation
- Link to agent READMEs for agent-specific guidance

**Critical Pattern** (Must appear 3+ times):
```markdown
**BEFORE working with X, read [agent/docs/Y.md](agent/docs/Y.md) for complete details.**
```

**Rules**:
- ONLY exists at root level (NOT in agent folders)
- Reference root [docs/DOCUMENTATION_STRATEGY.md](DOCUMENTATION_STRATEGY.md) to explain the pattern
- Emphasize reading docs BEFORE starting tasks (not during/after)
- Link to agent README.md files for agent-specific navigation
- Agent folders use README.md for both human and AI guidance

### 4. Temporary/Scaffolding Documents

**Naming Convention**:
- `*_SCRATCH.md`
- `*_TEMP.md`
- `*_BACKFILL_STATUS.md` (progress tracking)
- `*.draft.md`

**Purpose**: Exploration, planning, temporary status tracking

**Lifecycle**:
1. **Creation**: Use during exploration/development
2. **Consolidation**: Extract valuable content into permanent docs
3. **Deletion**: Remove when no longer needed
4. **Gitignore**: Most temp docs should be in `.gitignore`

**Rules**:
- Never reference temp docs from permanent documentation
- Clean up regularly (weekly during active development)
- Consolidate into docs/ before considering "done"
- Add patterns to `.gitignore` to prevent accidental commits

**Current .gitignore patterns**:
```
*_SCRATCH.md
*.draft.md
*.tmp.md
*_BACKFILL_STATUS.md
*_BACKFILL_FIX.md
```

## Reference Rules

### ✅ GOOD: Hierarchical References

```markdown
# In README.md
For detailed architecture, see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

# In docs/ARCHITECTURE.md
For Spark parallelization details, see [SPARK_BACKFILL_GUIDE.md](SPARK_BACKFILL_GUIDE.md)

# In CLAUDE.md
**BEFORE training models, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) section on "Model Persistence"**
```

### ❌ BAD: Orphaned or Circular References

```markdown
# Bad: Reference without parent link
See advanced_optimization.md for details  # Not linked from README!

# Bad: Circular reference
docs/A.md → docs/B.md → docs/A.md

# Bad: Flat list in CLAUDE.md eating context
Here's everything about the system:
[Full architecture explanation...]
[Complete model list...]
[Entire command reference...]
```

## Maintenance Workflow

### When Adding New Documentation

1. **Determine level**: Root docs/ or agent docs/?
2. **Create document** in appropriate docs/ folder
3. **Add reference** to parent README.md or CLAUDE.md
4. **Verify reachability** from root README.md
5. **Update CLAUDE.md** if this requires new "read X before Y" guidance

### When Updating Existing Documentation

1. **Update content** in canonical location
2. **Check references**: Ensure parent links are still accurate
3. **Update CLAUDE.md** if task guidance changes
4. **Remove temp docs** if consolidating from scratch work

### Weekly Cleanup

1. **Find temp docs**: `find . -name "*_SCRATCH.md" -o -name "*.draft.md"`
2. **Review each**: Extract valuable content to permanent docs
3. **Delete obsolete**: Remove what's no longer needed
4. **Verify gitignore**: Ensure patterns prevent commits

## AI Agent Guidelines

### For AI Agents Working in This Repo

**CRITICAL**: This repository uses hierarchical documentation. Before performing ANY task:

1. **Read relevant docs FIRST** (don't discover during execution)
2. Start with agent-level CLAUDE.md for navigation
3. Follow links to detailed docs/ files for specifics
4. Never create documentation without adding it to the hierarchy

**Example Workflow**:
```
Task: "Backfill forecasts using Spark"

Step 1: Read forecast_agent/CLAUDE.md → See reference to docs/SPARK_BACKFILL_GUIDE.md
Step 2: Read docs/SPARK_BACKFILL_GUIDE.md → Get cluster sizing, parameters
Step 3: Execute with full context (no discovery loops)
```

### When Creating Documentation

**Ask first**:
1. Does this belong in an existing doc?
2. Is this temporary scaffolding or permanent?
3. Where in the hierarchy does this fit?
4. How will users/agents discover this?

**If temporary**: Use `*_SCRATCH.md` naming and plan to consolidate or delete

**If permanent**: Add to appropriate docs/ folder and reference from parent

## Benefits of This Approach

### For Humans

- Single entry point (README.md) to find everything
- Concise overviews with links to details when needed
- No searching required - all paths are explicit
- Clear separation of overview vs. implementation details

### For AI Agents

- **Minimizes context usage**: Read only what's needed for the task
- **Reduces confusion**: Clear "read X before doing Y" guidance
- **Prevents discovery loops**: Get full context upfront
- **Enables efficient execution**: No mid-task doc hunting

### For Maintenance

- Easy to find docs that need updates (follow hierarchy)
- Clear ownership (each agent has their docs/)
- Prevents doc sprawl (everything has a place)
- Temp docs are explicit and cleaned regularly

## Current Status

**Completed**:
- ✅ Root-level documentation
  - CLAUDE.md (universal rules + collaboration philosophy)
  - docs/DOCUMENTATION_STRATEGY.md (this file)
  - docs/DATA_CONTRACTS.md (schema authority)

- ✅ forecast_agent hierarchical documentation
  - forecast_agent/README.md (concise, links to docs/)
  - forecast_agent/CLAUDE.md (PySpark patterns, gold tables, caching)
  - forecast_agent/docs/ARCHITECTURE.md
  - forecast_agent/docs/FORECASTING_EVOLUTION.md (V1 → V2 → V3)
  - forecast_agent/docs/SPARK_BACKFILL_GUIDE.md
  - forecast_agent/ml_lib/QUICKSTART.md (3-step workflow)
  - forecast_agent/ml_lib/VALIDATION_WORKFLOW.md (5-phase validation)
  - forecast_agent/ml_lib/MODEL_SELECTION_STRATEGY.md (fit many, publish few)
  - forecast_agent/deprecated/README.md (legacy ground_truth context)

- ✅ research_agent hierarchical documentation
  - research_agent/README.md (concise, links to docs/)
  - research_agent/CLAUDE.md (Lambda patterns, testing, gold builds)
  - research_agent/docs/ (6 detailed guides)
  - research_agent/tests/README.md (testing structure)
  - research_agent/tests/ (organized validation/health_checks/monitoring)
  - research_agent/DECISIONS_AND_LEARNINGS.md (final report reference)

- ✅ trading_agent documentation
  - trading_agent/README.md (navigation to docs/)
  - trading_agent/CLAUDE.md (ownership notice only)
  - trading_agent/docs/ (DATABRICKS_GUIDE.md, MULTI_MODEL_ANALYSIS.md)

## Summary

**One Rule**: Every document must be reachable from README.md through explicit hierarchical links.

**Enforcement**: CLAUDE.md files at each level remind AI agents to read docs BEFORE starting tasks, minimizing context usage and confusion.

**Maintenance**: Regular cleanup of temp docs, consolidation into permanent hierarchy, verification of reference completeness.
