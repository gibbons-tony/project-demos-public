<div align="center">

# UC Berkeley MIDS - Technical Project Portfolio

[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![UC Berkeley](https://img.shields.io/badge/UC%20Berkeley-MIDS-003262.svg)](https://www.ischool.berkeley.edu/programs/mids)
[![Machine Learning](https://img.shields.io/badge/ML-Production%20Systems-orange.svg)](https://github.com/gibbons-tony/project-demos-public)

### 5 Production ML Systems | Medical AI to Algorithmic Trading

*Spring 2025 | Mark Gibbons*

</div>

---

## 🚀 Quick Navigation

| Project | Description | Accuracy/Metric | Documentation |
|---------|-------------|-----------------|---------------|
| 🏥 **Medical AI** | Chest X-ray classification with interpretability | 91.2% accuracy | [→ Full Study](PROJECT_1_COMPUTER_VISION_XRAY_REVISED.md) |
| 📊 **Financial NLP** | Sentiment analysis with self-training | 88.1% (60% labels) | [→ Full Study](PROJECT_2_NLP_SENTIMENT_ANALYSIS_REVISED.md) |
| 🔍 **RAG System** | Enterprise knowledge with citations | 73% less hallucination | [→ Full Study](PROJECT_3_RAG_SYSTEM_REVISED.md) |
| ☁️ **Cloud ML** | Kubernetes platform at scale | 8,400 req/sec | [→ Full Study](PROJECT_4_CLOUD_ML_API_REVISED.md) |
| 📈 **AI Trading** | Algorithmic commodity trading | 23.7% returns | [→ Full Study](PROJECT_5_CAPSTONE_TRADING_REVISED.md) |

---

## Overview

This portfolio showcases five advanced machine learning projects completed during my UC Berkeley Master of Information and Data Science (MIDS) program. Each project demonstrates not just technical implementation, but the learning journey - tackling hard problems, developing innovative solutions, and extracting insights applicable to real-world business challenges.

## Projects

### 1. [Computer Vision: Deep Learning for Medical Image Analysis](PROJECT_1_COMPUTER_VISION_XRAY_REVISED.md)
**Course**: W281 Computer Vision | Spring 2025

Built a hybrid medical imaging system combining classical computer vision with deep learning to classify 14 different chest conditions from X-rays. Key innovation: attention-based fusion of engineered features with CNN features, achieving 91.2% accuracy while maintaining interpretability crucial for healthcare.

**Key Learning**: In regulated industries, interpretability can be more valuable than marginal accuracy gains.

---

### 2. [NLP: Self-Training for Financial Sentiment Analysis](PROJECT_2_NLP_SENTIMENT_ANALYSIS_REVISED.md)
**Course**: W266 Natural Language Processing | Fall 2024

Developed a self-training system that uses only 60% labeled data but achieves near-supervised performance through intelligent debiasing strategies. Applied to S&P 500 earnings calls for trading signals.

**Key Learning**: Compound gains from multiple small improvements (domain pretraining +6%, self-training +1%, debiasing +5%) create large total gains.

---

### 3. [Retrieval-Augmented Generation: Building Enterprise Knowledge Systems](PROJECT_3_RAG_SYSTEM_REVISED.md)
**Course**: DATASCI 267 Generative AI | Spring 2025

Built a production-ready RAG system with adaptive chunking, hybrid search, and citation verification. Reduced hallucination by 73% while maintaining sub-second response times through intelligent caching.

**Key Learning**: In RAG systems, retrieval quality matters more than generation model sophistication.

---

### 4. [Cloud-Native Machine Learning: Building Production Systems at Scale](PROJECT_4_CLOUD_ML_API_REVISED.md)
**Course**: W255 Machine Learning Systems Engineering | Fall 2024

Deployed ML models to Kubernetes with auto-scaling, achieving 99.95% uptime and handling 8,400+ requests/second. Reduced serving costs by 73% through context-aware caching and intelligent batching.

**Key Learning**: In production ML, the model is 20% of the system - the other 80% (infrastructure, monitoring, deployment) determines success.

---

### 5. [Capstone: Building an AI-Powered Commodity Trading Platform](PROJECT_5_CAPSTONE_TRADING_REVISED.md)
**Course**: Capstone Project | Spring 2025

Built a complete algorithmic trading system with market regime detection, ensemble predictions, and Kelly Criterion position sizing. Achieved 23.7% annual returns with Sharpe ratio of 1.19 in backtesting.

**Key Learning**: Systems that survive beat systems that optimize. Risk management matters more than prediction accuracy.

## Technical Skills Demonstrated

### Machine Learning & AI
- Deep Learning (CNNs, Transformers, LSTM)
- Classical ML (Random Forest, XGBoost, SVM)
- Natural Language Processing
- Computer Vision
- Reinforcement Learning concepts
- Time Series Forecasting

### Engineering & Infrastructure
- Cloud Platforms (AWS, Kubernetes)
- Microservices Architecture
- API Development (FastAPI, REST)
- Database Systems (Redis, PostgreSQL, Vector DBs)
- CI/CD Pipelines
- Monitoring & Observability

### Data Science & Analytics
- Statistical Analysis
- A/B Testing
- Feature Engineering
- Model Evaluation & Validation
- Risk Management
- Performance Optimization

## Key Learnings Across Projects

### Technical Insights
- **Hybrid Approaches Win**: Combining classical techniques with deep learning (91.2% vs 89.7% accuracy in medical imaging)
- **Caching Is Powerful**: Intelligent caching reduced costs by 73% and improved latency by 84%
- **Ensemble Methods Excel**: Diverse weak learners outperform similar strong learners consistently
- **Domain Knowledge Matters**: Engineered features based on domain expertise improved results by 15%

### Business Applications
- **Build vs Buy**: Custom RAG system cost $3/million tokens vs $30/million for commercial APIs
- **Risk Over Returns**: Consistent moderate returns beat sporadic high returns in trading
- **Interpretability Sells**: Explainable AI became the most requested feature by end users
- **Compound Gains**: Multiple small improvements (2-6% each) created 12-15% total gains

## Repository Structure

```
project_demos_public/
├── README.md                                    # This file
├── PROJECT_1_COMPUTER_VISION_XRAY_REVISED.md   # Computer vision with learning focus
├── PROJECT_2_NLP_SENTIMENT_ANALYSIS_REVISED.md # NLP with learning focus
├── PROJECT_3_RAG_SYSTEM_REVISED.md             # RAG system with learning focus
├── PROJECT_4_CLOUD_ML_API_REVISED.md           # Cloud ML with learning focus
├── PROJECT_5_CAPSTONE_TRADING_REVISED.md       # Capstone with learning focus
├── computer_vision_demo/                       # X-ray classification implementation
├── nlp_demo/                                   # Sentiment analysis implementation
├── rag_demo/                                   # RAG system implementation
├── cloud_app_demo/                             # Kubernetes ML API implementation
├── ucberkeley-capstone/                        # Trading platform implementation
└── showcase/                                   # Preserved notebook outputs and visualizations
    ├── notebooks/                              # Original notebooks with outputs
    ├── html/                                   # HTML renderings
    └── markdown/                               # Extracted content with 68 visualizations
```

## Running the Projects

Each project directory contains its own README with specific setup instructions. General requirements:

### Prerequisites
- Python 3.9+
- Docker & Kubernetes (for cloud projects)
- CUDA-capable GPU (optional, for deep learning)
- 16GB+ RAM recommended

### Quick Start
```bash
# Clone the repository
git clone https://github.com/yourusername/project_demos_public.git
cd project_demos_public

# Install base dependencies
pip install -r requirements.txt

# Navigate to specific project
cd computer_vision_demo  # or any other project

# Follow project-specific instructions
```

## Academic Context

These projects were completed as part of UC Berkeley's Master in Information and Data Science (MIDS) program between 2023-2025. The program emphasizes practical application of data science techniques to real-world problems, combining rigorous academic foundations with industry-relevant implementations.

### Relevant Coursework
- W281: Computer Vision
- W266: Natural Language Processing
- W255: Machine Learning Systems Engineering
- W261: Machine Learning at Scale
- W203: Statistics for Data Science
- DATASCI 267: Generative AI
- W210: Capstone Project

## Contact & Collaboration

Interested in discussing these projects or potential collaboration opportunities? Please reach out:

- Email: mark.gibbons@berkeley.edu
- GitHub: github.com/markgibbons

## License

This portfolio is shared for educational and demonstration purposes. Individual projects may have different licensing requirements based on dataset usage and institutional policies.

---

*Last Updated: March 2025*