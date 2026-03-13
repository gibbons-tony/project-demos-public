# Legacy GDELT Components

This folder contains experimental and deprecated GDELT pipeline components that are **NOT actively used** in production.

---

## Why These Are Legacy

The GDELT pipeline architecture evolved through several iterations:

1. **Initial Approach (berkeley-datasci210-capstone-processor)**
   - Single monolithic Lambda handling all stages
   - Replaced by modular pipeline with separate Bronze/Silver stages

2. **Step Function Orchestration Experiments**
   - Various Step Function definitions for orchestrating Bronze→Silver
   - Replaced by simpler EventBridge scheduled Lambdas
   - Step Functions added complexity without clear benefits for this use case

3. **Alternative Bronze Processing Approaches**
   - Experiments with different SQS loading strategies
   - Experiments with batch date generation
   - Current approach: Direct CSV→Bronze via SQS trigger

---

## Current Production System

See: `../ACTIVE_COMPONENTS.md` for the active architecture

**Summary:**
- **Discovery:** `gdelt-daily-discovery` (EventBridge scheduled)
- **Bronze:** `gdelt-bronze-transform` (SQS triggered)
- **Silver:** `gdelt-silver-transform` (EventBridge scheduled)

---

## Contents of This Folder

### lambda_functions/

**berkeley-datasci210-capstone-processor/**
- Original monolithic GDELT processor
- Deployed in AWS but not actively used
- Replaced by: Modular pipeline (discovery → bronze → silver)

**gdelt-csv-sqs-loader/**
- Experimental SQS loader
- Never used in production
- Current approach: Discovery Lambda directly queues to SQS

**gdelt-generate-date-batches/**
- Experimental batch date generator
- Deployed in AWS but not actively used
- Current approach: Date-by-date processing via SQS

**gdelt-jsonl-to-silver/**
- Old direct JSONL→Silver converter
- Replaced by: `gdelt-silver-transform` (Bronze→Silver)
- Skipped the Bronze layer (no longer recommended)

**gdelt-queue-monitor/**
- Monitoring utility Lambda
- Deployed in AWS but not actively used
- Current approach: Direct AWS Console/CloudWatch monitoring

### step_functions/

All Step Function definitions are **DISABLED** in favor of EventBridge scheduled Lambdas:

**gdelt_bronze_silver_pipeline.json**
- Old Bronze→Silver orchestration
- Replaced by: EventBridge schedules

**gdelt_daily_incremental_pipeline.json**
- Experimental daily incremental pipeline
- Replaced by: EventBridge schedules (simpler, more reliable)

**gdelt_daily_master_pipeline.json**
- Experimental master pipeline
- Replaced by: EventBridge schedules

**groundtruth_gdelt_backfill_sqs.json**
- Old backfill orchestration via SQS
- Replaced by: Direct SQS triggers on Lambda

**groundtruth_gdelt_backfill_with_bronze_silver.json**
- Old combined backfill orchestration
- Replaced by: Separate Bronze and Silver backfill queues

---

## Why EventBridge Won Over Step Functions

**Advantages of current EventBridge approach:**
1. **Simpler:** No state machine JSON to maintain
2. **More reliable:** Each stage is independent
3. **Easier to debug:** Each Lambda can be tested separately
4. **Cost-effective:** No Step Function execution charges
5. **Flexible:** Easy to adjust schedules or add new stages

**When Step Functions might be useful:**
- Complex multi-branch workflows
- Need for advanced error handling/retry logic
- Workflows with conditional paths

For our use case (linear daily pipeline), EventBridge is sufficient.

---

## Can These Be Deleted?

**Lambda Functions in AWS:**
- Can be deleted if confirmed not in use
- Recommend keeping for 30 days in case of rollback need
- After 30 days: Safe to delete

**Code in This Folder:**
- Keep in git history for reference
- Could be deleted from main branch after verifying new system is stable
- Recommend keeping for 1-2 months post-deployment

---

## Migration History

- **Nov 19, 2025:** Backfill pipeline deployed (JSONL→Bronze→Silver)
- **Nov 21, 2025:** Daily incremental pipeline deployed (Discovery→CSV→Bronze→Silver)
- **Nov 22, 2025:** Discovery Lambda optimized (streaming fix)
- **Nov 22, 2025:** Legacy files moved to this folder

---

**Status:** These components are preserved for historical reference only. Do not deploy or modify.
