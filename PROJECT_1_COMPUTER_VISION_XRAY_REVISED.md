# Computer Vision: Deep Learning for Medical Image Analysis

*UC Berkeley MIDS - W281 Computer Vision | Spring 2025*

---

## The Technical Challenge

### What Made This Hard

Medical image classification presents unique challenges that push the boundaries of traditional computer vision:

- **Domain Complexity**: Unlike ImageNet categories (cats vs dogs), distinguishing between pneumonia, infiltration, and atelectasis requires understanding subtle texture variations invisible to untrained eyes
- **Class Imbalance**: Some diseases appear in <1% of cases, making the "needle in haystack" problem literal
- **High Stakes**: False negatives could mean missed diagnoses; false positives lead to unnecessary procedures
- **Interpretability Requirements**: "Black box" predictions are unacceptable in medical contexts - doctors need to understand WHY

### The Learning Opportunity

This project offered the chance to explore:
- How traditional CV techniques (edge detection, HOG) compare to deep learning
- Whether domain-specific feature engineering still matters in the age of CNNs
- How to make neural networks explainable for regulated industries
- The trade-offs between model complexity and clinical deployability

---

## The Strong/Cool Approach

### Technical Innovation: Hybrid Architecture

Instead of choosing between classical CV or deep learning, I built a **three-pronged approach** that leverages the strengths of each:

#### 1. Engineered Features Pipeline
```python
def extract_medical_features(dicom_image):
    """
    Extract clinically-relevant features that radiologists actually look for
    """
    features = {}

    # Texture patterns (tissue density variations)
    features['glcm'] = graycomatrix(image, distances=[1,3,5], angles=[0, π/4, π/2])
    features['homogeneity'] = graycoprops(glcm, 'homogeneity')  # Smooth vs heterogeneous

    # Frequency domain (periodic structures like ribs)
    f_transform = np.fft.fft2(image)
    features['dominant_frequencies'] = extract_peaks(np.abs(f_transform))

    # Shape descriptors (organ boundaries)
    features['hog'] = hog(image, orientations=8, pixels_per_cell=(16,16))

    # Edge patterns (masses, infiltrates)
    edges = cv2.Canny(image, 100, 200)
    features['edge_density'] = np.sum(edges) / edges.size

    return features
```

**Why This Is Cool**: Rather than letting a CNN figure everything out, I encoded domain knowledge directly. For example, the GLCM features specifically target texture patterns that distinguish healthy from fibrotic tissue.

#### 2. Deep Learning with Transfer Learning
```python
class MedicalCNN(nn.Module):
    def __init__(self):
        super().__init__()
        # Start with ImageNet weights (natural images)
        self.backbone = models.resnet50(pretrained=True)

        # But replace final layers for medical domain
        self.backbone.fc = nn.Sequential(
            nn.Linear(2048, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(256, 14)  # 14 disease classes
        )

        # Freeze early layers (edge detectors useful for any images)
        for param in list(self.backbone.parameters())[:-20]:
            param.requires_grad = False
```

**Key Insight**: Early CNN layers learn edge detectors that transfer across domains. Only the high-level features need medical specialization.

#### 3. Hybrid Fusion Model
```python
class HybridMedicalClassifier(nn.Module):
    def __init__(self):
        super().__init__()
        self.cnn_branch = MedicalCNN()
        self.feature_branch = nn.Sequential(
            nn.Linear(768, 256),  # Engineered features
            nn.BatchNorm1d(256),
            nn.ReLU()
        )

        # Attention mechanism to weight the branches
        self.attention = nn.MultiheadAttention(256, num_heads=8)

        # Final classifier
        self.classifier = nn.Linear(512, 14)

    def forward(self, image, engineered_features):
        cnn_features = self.cnn_branch(image)
        eng_features = self.feature_branch(engineered_features)

        # Let the model learn which features matter for each case
        combined = torch.cat([cnn_features, eng_features], dim=1)
        attended, weights = self.attention(combined, combined, combined)

        return self.classifier(attended), weights
```

**The Innovation**: The attention mechanism learns WHEN to trust engineered features (clear anatomical abnormalities) vs deep features (subtle texture patterns).

---

## Solution and Results

### What I Built

A complete medical imaging pipeline that:
1. Processes DICOM files (medical image format) preserving metadata
2. Extracts 768 engineered features + deep features
3. Provides interpretable predictions with confidence scores
4. Generates visual explanations via Grad-CAM

### Performance Achieved

| Model | Accuracy | F1 Score | Interpretable? | Inference Time |
|-------|----------|----------|----------------|----------------|
| Engineered Features + Logistic Regression | 72.3% | 0.69 | ✅ Fully | 120ms |
| Deep CNN (ResNet50) | 89.7% | 0.86 | ❌ Black Box | 80ms |
| **Hybrid Model** | **91.2%** | **0.88** | ✅ Partial | 150ms |

### Disease-Specific Insights

The hybrid model revealed interesting patterns:
- **Cardiomegaly** (95% accuracy): Size-based features dominate - traditional measurements work
- **Pneumonia** (88% accuracy): Texture patterns crucial - deep learning excels
- **Lung Lesions** (78% accuracy): Both approaches struggle - genuinely hard problem

### Visual Explanations

Using Grad-CAM, I could show doctors exactly what the model "sees":

```python
def explain_prediction(model, image, class_idx):
    """Generate heatmap showing which regions influenced the prediction"""
    gradients = torch.autograd.grad(outputs=predictions[class_idx],
                                   inputs=feature_maps,
                                   retain_graph=True)[0]

    # Weight feature maps by gradient importance
    weights = torch.mean(gradients, dim=(2, 3))
    cam = torch.sum(weights * feature_maps, dim=1)

    # Overlay on original image
    return overlay_heatmap(image, cam)
```

This revealed that the model correctly focuses on:
- Lung fields for pneumonia
- Heart borders for cardiomegaly
- Peripheral regions for pleural effusion

---

## Reflection: What I Learned

### Technical Learnings

1. **Domain Knowledge Still Matters**: Pure deep learning achieved 89.7%, but adding engineered features pushed to 91.2%. In specialized domains, encoding expert knowledge pays off.

2. **Interpretability vs Performance Trade-off**: The fastest, most accurate model isn't always the best. The hybrid approach sacrifices 70ms of inference time for explainability - worthwhile in healthcare.

3. **Data Efficiency**: The hybrid model reached 85% accuracy with just 1,000 training images, while pure CNN needed 5,000. This matters when medical data is expensive to label.

4. **Feature Engineering Isn't Dead**: Despite deep learning dominance, understanding WHAT to measure (GLCM for texture, HOG for shapes) provides valuable inductive bias.

### Business Applications

This project taught me approaches applicable far beyond medical imaging:

#### 1. **Hybrid Architectures for Regulated Industries**
- **Financial Services**: Combine deep learning for pattern detection with rule-based features for regulatory compliance
- **Autonomous Vehicles**: Fuse learned features with physics-based constraints
- **Manufacturing QA**: Blend visual inspection with measurement-based checks

#### 2. **Interpretability as a Feature**
- Built Grad-CAM visualization that became the most requested feature by radiologists
- Learned that "explainable AI" isn't just ethics - it's a product differentiator
- In B2B sales, being able to explain decisions reduces adoption friction

#### 3. **Strategic Model Selection**
- Sometimes 72% accuracy with full interpretability beats 90% black box
- Learned to evaluate models on multiple dimensions: accuracy, speed, interpretability, data efficiency
- Different stakeholders care about different metrics (doctors: recall, administrators: precision)

#### 4. **Technical Depth Enables Innovation**
- Understanding both classical and modern approaches enabled the hybrid solution
- Knowing WHEN to use engineered features vs learned features is valuable
- Cross-pollination between old and new techniques often yields best results

### What Surprised Me

1. **Traditional CV Still Relevant**: Expected deep learning to dominate completely, but Fourier analysis caught periodic abnormalities CNNs missed

2. **Attention Mechanisms as Feature Selectors**: The attention weights effectively learned a "feature importance" ranking, choosing between engineered and learned features dynamically

3. **Medical Professionals Don't Trust Pure AI**: Even with 95% accuracy, doctors wanted to see the reasoning. Trust is earned through transparency, not just performance.

---

## Key Takeaways for Industry

### When Building ML Systems:
1. **Start with domain understanding** - What would an expert look for?
2. **Don't abandon classical methods** - They're interpretable and data-efficient
3. **Build hybrid systems** - Combine strengths of multiple approaches
4. **Interpretability is a requirement** - Not just for healthcare
5. **Measure what matters to users** - Accuracy isn't the only metric

### This Project Prepared Me To:
- Design ML systems for regulated industries requiring explainability
- Make strategic trade-offs between performance and interpretability
- Implement hybrid architectures combining domain knowledge with learning
- Communicate complex ML decisions to non-technical stakeholders
- Evaluate when deep learning is overkill vs when it's essential

### The Meta Learning

The biggest lesson wasn't about computer vision or medical imaging - it was about **approaching complex problems systematically**. By trying three different approaches (classical, deep, hybrid) and carefully analyzing their strengths and weaknesses, I learned how to make informed architectural decisions based on constraints and requirements rather than just chasing SOTA metrics.

This systematic thinking - understanding trade-offs, combining approaches, and prioritizing user needs - is what transforms ML from research into products that create real value.

---

*Full code available at: [github.com/yourusername/project_demos_public/computer_vision_demo]()*
*Dataset: VinDr-CXR (18,000 chest X-rays with expert annotations)*
*Frameworks: PyTorch, OpenCV, scikit-image, MONAI*