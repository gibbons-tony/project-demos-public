---
layout: default
title: Team
nav_order: 3
description: "Meet the UC Berkeley MIDS students behind Caramanta"
---

# Team
{: .no_toc }

## Table of contents
{: .no_toc .text-delta }

1. TOC
{:toc}

---

## About the Team

Caramanta is the result of a collaborative capstone project by four UC Berkeley Master of Information and Data Science (MIDS) students. Our team brings together diverse expertise in data engineering, machine learning, software development, and quantitative finance.

---

## Team Members

### Connor Watson
**Role:** Forecast Agent Lead
{: .label .label-purple }

Connor led the development of the Forecast Agent, implementing the ML model suite and Spark parallelization architecture. His work on the "Train-Once Pattern" and forecast manifest tracking enabled the 180x speedup achievement.

**Key Contributions:**
- 15+ ML model implementations (ARIMA, Prophet, XGBoost, LSTM, TFT)
- Spark parallel backfill architecture
- Forecast manifest tracking system
- Model persistence and caching strategy

**Background:** Software engineering background with focus on distributed systems and ML infrastructure.

---

### Stuart Holland
**Role:** Research Agent Lead
{: .label .label-green }

Stuart architected the unified data platform that serves as the foundation for all forecasting and trading operations. His innovative forward-fill interpolation strategy achieved the 90% data reduction while maintaining complete market coverage.

**Key Contributions:**
- Unified data architecture design
- Bronze/Silver/Gold medallion implementation
- 6 AWS Lambda data collection functions
- 90% data reduction achievement

**Background:** Data engineering expertise with experience in cloud infrastructure and ETL pipelines.

---

### Francisco Munoz
**Role:** Trading Agent Specialist
{: .label .label-yellow }

Francisco developed the trading strategy optimization framework and implemented the rigorous statistical validation process that ensures only high-performing models make it to production.

**Key Contributions:**
- 9 trading strategy implementations
- Statistical validation framework (Diebold-Mariano testing)
- 70%+ accuracy threshold discovery
- Backtesting and performance metrics

**Background:** Quantitative finance background with expertise in algorithmic trading and risk management.

---

### Tony Gibbons
**Role:** Trading Agent Lead & Integration
{: .label .label-red }

Tony led the Trading Agent development and orchestrated the integration of all three agents into a cohesive end-to-end system. His work on the Rolling Horizon MPC controller enables dynamic decision-making in production.

**Key Contributions:**
- Rolling Horizon MPC controller
- End-to-end system integration
- Production deployment architecture
- Parameter optimization framework

**Background:** Software engineering and quantitative methods with focus on optimization and control systems.

---

## Project Timeline

| Phase | Duration | Lead | Deliverables |
|:------|:---------|:-----|:-------------|
| **Research & Planning** | Weeks 1-2 | All | Project scope, data sources, architecture design |
| **Data Infrastructure** | Weeks 3-6 | Stuart | Bronze→Silver→Gold pipeline, unified data |
| **ML Model Development** | Weeks 7-11 | Connor | 15+ models, Spark parallelization |
| **Trading Strategies** | Weeks 9-13 | Francisco, Tony | 9 strategies, statistical validation |
| **Integration & Testing** | Weeks 12-14 | All | End-to-end system, performance tuning |
| **Production Deployment** | Week 15 | Tony | Live system, monitoring, documentation |

---

## Collaboration & Tools

### Development Practices

**Version Control:**
- GitHub for code collaboration
- Branching strategy for parallel development
- Pull request reviews for code quality

**Communication:**
- Weekly team meetings
- Slack for daily coordination
- Shared documentation in Confluence

**Project Management:**
- Agile methodology with 2-week sprints
- JIRA for task tracking
- Regular retrospectives for continuous improvement

### Technology Stack

| Layer | Technologies | Primary Owner |
|:------|:------------|:--------------|
| **Data Collection** | AWS Lambda, S3, EventBridge | Stuart |
| **Data Platform** | Databricks, Delta Lake, PySpark | Stuart |
| **ML Framework** | scikit-learn, Prophet, XGBoost, PyTorch | Connor |
| **Optimization** | SciPy, NumPy, MPC | Tony |
| **Trading Logic** | Python, Pandas, Statistical Testing | Francisco |
| **Deployment** | Databricks Workflows, Git | Tony |

---

## Key Achievements by Agent

### Research Agent (Stuart)

**Data Architecture Innovation:**
- Designed unified data table with continuous daily coverage
- Implemented forward-fill interpolation for gap handling
- Achieved 90% data reduction (75k → 7.6k rows)
- Zero null values through intelligent data engineering

**Infrastructure Excellence:**
- 6 AWS Lambda functions for automated data collection
- Bronze/Silver/Gold medallion architecture
- Delta Lake for ACID transactions and time-travel
- Cost-efficient serverless infrastructure ($0.20/day)

### Forecast Agent (Connor)

**ML Performance Breakthrough:**
- 180x speedup evolution (V1 → V2 → V3)
- Train-Once Pattern with persistent model storage
- Parallel Spark backfills for efficient training
- Forecast manifest for metadata tracking

**Model Diversity:**
- 15+ models spanning statistical, tree-based, and deep learning
- "Fit many, publish few" strategy (93% compute savings)
- Comprehensive hyperparameter optimization
- Cross-validation across multiple time windows

### Trading Agent (Francisco & Tony)

**Strategy Development:**
- 9 distinct trading strategies for different market conditions
- Statistical validation framework (Diebold-Mariano)
- 70%+ accuracy threshold discovery
- Rolling Horizon MPC for dynamic optimization

**System Integration:**
- End-to-end pipeline from data collection to trading signals
- Automated backfilling and performance monitoring
- Production-grade error handling and logging
- Real-time decision-making capability (<5 min latency)

---

## Academic Supervision

### UC Berkeley Faculty Advisors

**Program:** Master of Information and Data Science (MIDS)

**Institution:** UC Berkeley School of Information

**Capstone Year:** 2024

---

## Acknowledgments

We would like to thank:

- **UC Berkeley MIDS Faculty** for guidance and mentorship throughout the capstone project
- **Industry Mentors** who provided domain expertise in commodity trading and quantitative finance
- **Databricks** for providing the cloud platform that enabled our scalable ML infrastructure
- **Open Source Community** for the excellent libraries (Prophet, XGBoost, PyTorch) that powered our models

---

## Contact & Links

### Project Resources

- **GitHub Repository:** [github.com/gibbonstony/ucberkeley-capstone](https://github.com/gibbonstony/ucberkeley-capstone)
- **Live System:** [studiomios.wixstudio.com/caramanta](https://studiomios.wixstudio.com/caramanta)
- **Technical Documentation:** This site

### Team LinkedIn Profiles

- Connor Watson: [LinkedIn](#)
- Stuart Holland: [LinkedIn](#)
- Francisco Munoz: [LinkedIn](#)
- Tony Gibbons: [LinkedIn](#)

### For Inquiries

For questions about the Caramanta project, please contact us through the UC Berkeley School of Information.

---

## Project Status

**Current Status:** Complete
{: .label .label-green }

**Completion Date:** December 2024

**Future Work:** See [Results & Metrics](results.md#future-work) for planned enhancements and next steps.

---

<small>[← Results & Metrics](results.md) | [Back to Home](index.md)</small>
