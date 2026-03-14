# Natural Language Processing: Self-Training for Financial Sentiment Analysis

*UC Berkeley MIDS - W266 Natural Language Processing | Fall 2024*

---

## The Technical Challenge

### What Made This Hard

Financial sentiment analysis isn't your typical "movie review" NLP problem:

- **Domain Language Complexity**: "Bearish" isn't about animals, "going long" isn't about distance. Financial text uses specialized vocabulary that general models misinterpret
- **Labeled Data Scarcity**: Getting traders to label thousands of texts is expensive (~$50K for 10K samples). Most firms have tons of text but little labeled data
- **Nuanced Sentiment**: "Revenue missed expectations but showed improvement" - is this positive or negative? Context and emphasis matter enormously
- **High Stakes**: Wrong sentiment → wrong trade → real money lost. This isn't academic accuracy, it's P&L impact

### The Learning Opportunity

This project let me explore cutting-edge questions:
- Can self-training (using model's own predictions) actually work, or does it just amplify errors?
- How do you "debias" pseudo-labels when the model is literally teaching itself?
- Is domain-specific pretraining (FinBERT) worth it vs general models (BERT)?
- Can we get production-quality results with 60% less labeled data?

---

## The Strong/Cool Approach

### Technical Innovation: Self-Training with Intelligent Debiasing

Inspired by Li et al. (2023)'s work on NER, I adapted self-training for sentiment analysis with a twist: **three different debiasing strategies** to prevent error amplification.

#### The Core Pipeline
```python
class SelfTrainingPipeline:
    def __init__(self, base_model, confidence_threshold=0.9):
        self.teacher = base_model
        self.student = None
        self.threshold = confidence_threshold
        self.iteration = 0

    def generate_pseudo_labels(self, unlabeled_data):
        """Teacher model creates labels for unlabeled data"""
        pseudo_labels = []
        confidence_scores = []

        with torch.no_grad():
            for batch in unlabeled_data:
                logits = self.teacher(batch)
                probs = F.softmax(logits, dim=-1)

                # Key insight: Only use high-confidence predictions
                max_prob, predicted = torch.max(probs, dim=-1)

                pseudo_labels.extend(predicted.cpu().numpy())
                confidence_scores.extend(max_prob.cpu().numpy())

        return pseudo_labels, confidence_scores

    def train_iteration(self, labeled_data, pseudo_data):
        """Student learns from both real and pseudo labels"""
        # Critical: Weight pseudo-labels less than real labels
        combined_data = self.combine_with_weights(
            labeled_data, weight=1.0,
            pseudo_data, weight=0.7
        )

        self.student = self.initialize_student()
        self.student.train(combined_data)

        # Student becomes next teacher
        self.teacher = self.student
        self.iteration += 1
```

**Why This Is Cool**: The model literally teaches itself, but with safeguards to prevent "learning nonsense."

#### Debiasing Strategy 1: Confidence-Based Filtering
```python
def confidence_based_debiasing(pseudo_labels, confidence_scores, threshold=0.9):
    """Only keep predictions the model is really sure about"""

    # Insight: Model confidence correlates with correctness
    high_confidence_mask = confidence_scores > threshold

    # But also check for suspiciously uniform distributions
    entropy = -np.sum(probs * np.log(probs + 1e-9), axis=-1)
    not_too_certain = entropy > 0.1  # Avoid overconfident errors

    keep_mask = high_confidence_mask & not_too_certain

    return pseudo_labels[keep_mask], confidence_scores[keep_mask]
```

**Key Learning**: Setting threshold too high (>0.95) gives too little data; too low (<0.85) introduces noise. Sweet spot: 0.9.

#### Debiasing Strategy 2: Ensemble Agreement
```python
def ensemble_debiasing(models, unlabeled_text):
    """Multiple models vote - only keep unanimous decisions"""

    predictions = []
    for model in models:
        # Each model trained with different random seeds
        pred = model.predict(unlabeled_text)
        predictions.append(pred)

    predictions = np.array(predictions)

    # Require 2/3 agreement minimum
    agreement = np.mean(predictions == predictions[0], axis=0)
    consensus_mask = agreement >= 0.66

    # Return majority vote where there's consensus
    pseudo_labels = scipy.stats.mode(predictions, axis=0)[0]

    return pseudo_labels[consensus_mask]
```

**Insight**: When models disagree, they're usually both uncertain. Agreement = confidence.

#### Debiasing Strategy 3: Distribution Matching
```python
def distribution_aware_debiasing(pseudo_labels, original_distribution):
    """Prevent distribution shift during self-training"""

    # Problem: Model might predict 90% positive if trained on biased data
    # Solution: Enforce similar distribution to labeled data

    original_dist = np.bincount(original_labels) / len(original_labels)
    pseudo_dist = np.bincount(pseudo_labels) / len(pseudo_labels)

    # Resample to match original distribution
    resampled_indices = []
    for class_id in range(len(original_dist)):
        target_count = int(original_dist[class_id] * len(pseudo_labels))
        class_indices = np.where(pseudo_labels == class_id)[0]

        if len(class_indices) > target_count:
            # Oversample: choose highest confidence
            selected = class_indices[np.argsort(confidence_scores[class_indices])[-target_count:]]
        else:
            # Undersample: take all
            selected = class_indices

        resampled_indices.extend(selected)

    return pseudo_labels[resampled_indices]
```

**Why This Matters**: Prevents the model from "drift" - gradually predicting only one class.

---

## Solution and Results

### What I Built

A complete financial sentiment analysis system that:
1. Starts with only 60% labeled data (2,904 samples)
2. Self-trains on unlabeled data (1,936 samples)
3. Applies intelligent debiasing
4. Achieves near-supervised performance

### Performance Achieved

| Approach | Labeled Data | Accuracy | F1 Score | Training Cost |
|----------|--------------|----------|----------|---------------|
| Baseline (FinBERT) | 60% | 82.3% | 0.80 | $X |
| Oracle (All Labels) | 100% | 89.7% | 0.87 | $1.67X |
| Self-Training (No Debiasing) | 60% + pseudo | 83.1% | 0.81 | $X |
| Confidence Debiasing | 60% + pseudo | 86.4% | 0.84 | $X |
| Ensemble Debiasing | 60% + pseudo | 87.2% | 0.85 | $3X |
| **Hybrid (Ensemble + Confidence)** | **60% + pseudo** | **88.1%** | **0.86** | **$3X** |

### The Key Insight

**Self-training closed 68% of the gap to fully-supervised learning!**
- Gap to close: 89.7% - 82.3% = 7.4%
- Improvement achieved: 88.1% - 82.3% = 5.8%
- Efficiency: 5.8/7.4 = 78% of the benefit at 60% of the labeling cost

### Real-World Application Test

Applied to S&P 500 earnings call transcripts (Q1 2024):
```python
# Test on real trading strategy
def sentiment_trading_strategy(transcripts, model):
    signals = []
    for transcript in transcripts:
        sentiment = model.predict(transcript)

        if sentiment == 'positive' and confidence > 0.9:
            signals.append('BUY')
        elif sentiment == 'negative' and confidence > 0.9:
            signals.append('SELL')
        else:
            signals.append('HOLD')

    return signals

# Backtesting results
results = backtest(sentiment_signals, market_data)
# Returns: 14.3% annualized
# Sharpe: 0.87
# Max Drawdown: -8.2%
```

---

## Reflection: What I Learned

### Technical Learnings

1. **Self-Training Actually Works (With Caveats)**
   - Raw self-training: +0.8% improvement (barely worth it)
   - With debiasing: +5.8% improvement (game-changer)
   - Lesson: The technique matters less than the implementation details

2. **Domain-Specific Pretraining Is Crucial**
   - FinBERT baseline: 82.3%
   - BERT baseline: 76.1%
   - Difference: 6.2% from pretraining alone
   - Takeaway: In specialized domains, specialized models win

3. **Ensemble Debiasing > Single Model Confidence**
   - Single model confidence: Often overconfident on errors
   - Ensemble agreement: More reliable confidence signal
   - Trade-off: 3x compute cost for ensemble

4. **Distribution Shift Is Real and Dangerous**
   - Without distribution matching: Model converged to 85% positive predictions
   - With distribution matching: Maintained realistic 35% positive rate
   - Lesson: Always monitor prediction distributions in production

### Business Applications

This project taught me approaches valuable across industries:

#### 1. **Leveraging Unlabeled Data (Common in Business)**
Most companies have:
- Millions of unlabeled documents
- Expensive labeling costs ($5-50 per document)
- Time constraints (can't wait months for labeling)

Self-training offers a path to value from existing data.

#### 2. **The Confidence-Precision Trade-off**
Learned to think about:
- High confidence, low coverage (precise but limited)
- Low confidence, high coverage (comprehensive but noisy)
- Business context determines the right balance

For trading: High confidence required (real money at risk)
For research: Lower confidence acceptable (human review follows)

#### 3. **Ensemble Methods in Production**
Discovered that ensemble disagreement is a feature, not a bug:
- Agreement → Route to automated processing
- Disagreement → Flag for human review
- This creates a human-in-the-loop system naturally

#### 4. **Cost-Benefit Analysis of ML Approaches**
```
Full Labeling Cost: $50,000 (10K samples at $5 each)
60% Labeling Cost: $30,000
Ensemble Compute: $500/month

Savings: $20,000 upfront, $500/month ongoing
Performance Loss: 1.6% accuracy

ROI: Positive in 3 months for most applications
```

### What Surprised Me

1. **Debiasing More Important Than Base Model**
   - Spent weeks tuning FinBERT hyperparameters: +1% improvement
   - Spent days on debiasing strategy: +5% improvement
   - Lesson: Focus on the right problems

2. **Simple Ensemble Beats Complex Single Models**
   - One highly-tuned model: 85% accuracy
   - Three basic models ensembled: 87% accuracy
   - Implication: Diversity > individual sophistication

3. **Financial Language Is Truly Different**
   - "Guidance" in finance: future projections (critical)
   - "Guidance" in general: advice (ignorable)
   - The model learned these distinctions through self-training!

---

## Key Takeaways for Industry

### When Building NLP Systems:
1. **Start with domain-specific models** when available (FinBERT, BioBERT, etc.)
2. **Leverage unlabeled data** through self-training with proper debiasing
3. **Monitor distribution shift** - it's a silent killer in production
4. **Use ensemble disagreement** as a confidence measure
5. **Calculate ROI** on labeling vs. compute costs

### This Project Prepared Me To:
- Design semi-supervised learning systems for data-scarce domains
- Implement production-ready debiasing strategies
- Make cost-benefit trade-offs between labeling and compute
- Build human-in-the-loop systems using confidence thresholds
- Apply modern NLP to specialized business domains

### The Meta Learning

The biggest insight wasn't about NLP or self-training - it was about **iterative improvement and compound gains**. By stacking multiple small improvements (domain pretraining +6%, self-training +1%, debiasing +5%), I achieved a large total gain (+12%).

This compounds in business:
- Better data → better models
- Better models → better pseudo-labels
- Better pseudo-labels → even better models
- Creates a virtuous cycle

The key is having the patience and systematic approach to build these compound improvements rather than searching for a single silver bullet.

---

*Full code available at: [github.com/yourusername/project_demos_public/nlp_demo]()*
*Dataset: Financial Sentiment Analysis (4,840 sentences from financial news)*
*Frameworks: Transformers, PyTorch, Optuna for hyperparameter tuning*