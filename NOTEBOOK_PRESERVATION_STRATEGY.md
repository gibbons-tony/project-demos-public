# Notebook Content Preservation & Display Strategy

## The Challenge
Your notebooks contain valuable content that needs to be preserved and displayed:
- **Narrative Text**: Explanations, methodology, analysis
- **Results**: Model outputs, metrics, performance data
- **Visualizations**: Plots, confusion matrices, feature importance graphs
- **Code + Output**: The actual execution results that prove the work

Simply clearing outputs loses this critical demonstration value.

---

## Recommended Multi-Format Strategy

### 1. Three-Version Approach

```
project_demos_public/
├── notebooks/
│   ├── clean/           # Git-tracked clean notebooks
│   │   └── xray_classification.ipynb (no outputs)
│   ├── rendered/        # HTML/PDF versions for viewing
│   │   ├── xray_classification.html
│   │   └── xray_classification.pdf
│   └── reports/         # Extracted narrative + results
│       └── xray_classification_report.md
```

### 2. Automated Conversion Pipeline

```bash
#!/bin/bash
# convert_notebooks.sh

for notebook in notebooks/clean/*.ipynb; do
    name=$(basename "$notebook" .ipynb)

    # 1. Execute and save with outputs to temp
    jupyter nbconvert --to notebook --execute "$notebook" \
        --output="../executed/${name}.ipynb"

    # 2. Convert to HTML for web viewing
    jupyter nbconvert --to html "../executed/${name}.ipynb" \
        --output="../rendered/${name}.html" \
        --no-input  # Hide code, show only outputs

    # 3. Create full HTML with code
    jupyter nbconvert --to html "../executed/${name}.ipynb" \
        --output="../rendered/${name}_full.html"

    # 4. Extract to Markdown report
    jupyter nbconvert --to markdown "../executed/${name}.ipynb" \
        --output="../reports/${name}_report.md"

    # 5. Clean temp file
    rm "../executed/${name}.ipynb"
done
```

---

## Web Display Options

### Option A: GitHub Pages with Jupyter Book (Recommended)

```yaml
# _config.yml for Jupyter Book
title: Academic ML Projects Portfolio
author: Your Name

execute:
  execute_notebooks: 'off'  # Use pre-executed versions

html:
  use_repository_button: true
  use_issues_button: true

repository:
  url: https://github.com/yourusername/project_demos_public

sphinx:
  config:
    html_theme: sphinx_book_theme
```

**Structure:**
```
docs/
├── _config.yml
├── _toc.yml              # Table of contents
├── index.md              # Landing page
├── projects/
│   ├── computer_vision.md
│   ├── nlp_analysis.md
│   └── rag_system.md
└── notebooks/            # Embedded notebooks
    ├── xray_results.html
    └── nlp_results.html
```

**Benefits:**
- Beautiful, professional documentation site
- Searchable content
- Mobile-responsive
- Automatic deployment via GitHub Actions

### Option B: Static Site with MkDocs Material

```yaml
# mkdocs.yml
site_name: ML Projects Portfolio
theme:
  name: material
  features:
    - navigation.tabs
    - navigation.expand

plugins:
  - search
  - mkdocs-jupyter  # Renders notebooks

nav:
  - Home: index.md
  - Projects:
    - Computer Vision:
      - Overview: cv/index.md
      - Notebook: cv/xray_classification.ipynb
      - Results: cv/results.md
    - NLP:
      - Overview: nlp/index.md
      - Analysis: nlp/sentiment.ipynb
```

### Option C: Simple GitHub Rendering

```markdown
# Project README.md

## Live Demos

### View Notebooks with Results:
- [X-Ray Classification - View on nbviewer](https://nbviewer.org/github/yourusername/project_demos_public/blob/main/notebooks/rendered/xray_classification.ipynb)
- [View HTML Report](https://yourusername.github.io/project_demos_public/reports/xray_classification.html)

### Interactive Versions:
- [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/yourusername/project_demos_public/main?filepath=notebooks)
- [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/yourusername/project_demos_public)
```

---

## Content Extraction Strategy

### 1. Preserve Key Results in Markdown

```python
# extract_results.py
import json
import pandas as pd
from nbconvert import MarkdownExporter
import nbformat

def extract_notebook_results(notebook_path):
    """Extract key results and create summary report"""

    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    report = []
    report.append("# Project Results Summary\n")

    for cell in nb.cells:
        # Extract markdown cells
        if cell.cell_type == 'markdown':
            # Look for headers with "Results", "Conclusion", "Performance"
            if any(keyword in cell.source for keyword in ['Result', 'Conclusion', 'Performance']):
                report.append(cell.source)

        # Extract code outputs with visualizations
        elif cell.cell_type == 'code' and cell.outputs:
            for output in cell.outputs:
                if 'image/png' in output.get('data', {}):
                    # Save image and reference it
                    img_data = output['data']['image/png']
                    # Save as file and add to report
                    report.append(f"![Result](./images/{img_name}.png)")

                elif 'text/plain' in output.get('data', {}):
                    # Extract numeric results
                    text = output['data']['text/plain']
                    if 'accuracy' in text.lower() or 'score' in text.lower():
                        report.append(f"```\n{text}\n```")

    return '\n'.join(report)
```

### 2. Create Standalone Reports

```markdown
# Computer Vision Project Report

## Executive Summary
This project achieved 94.3% accuracy on chest X-ray classification using transfer learning with ResNet50.

## Methodology
[Extracted from notebook markdown cells]

## Key Results

### Model Performance
- **Accuracy**: 94.3%
- **Precision**: 92.1%
- **Recall**: 95.6%
- **F1-Score**: 93.8%

### Visualizations

#### Confusion Matrix
![Confusion Matrix](./assets/confusion_matrix.png)

#### ROC Curve
![ROC Curve](./assets/roc_curve.png)

#### Sample Predictions
![Predictions](./assets/sample_predictions.png)

## Technical Implementation

```python
# Key code snippet
model = tf.keras.applications.ResNet50(
    include_top=False,
    weights='imagenet',
    input_shape=(224, 224, 3)
)
```

## Conclusions
[Extracted from notebook conclusions]

## Reproducibility
To reproduce these results:
1. Install dependencies: `pip install -r requirements.txt`
2. Run training: `python train.py`
3. Evaluate: `python evaluate.py`
```

---

## Implementation Plan

### Phase 1: Preserve Existing Content (2 hours)
```bash
# 1. Create directory structure
mkdir -p notebooks/{clean,rendered,reports}
mkdir -p docs/assets
mkdir -p _site

# 2. Copy current notebooks to preserve them
cp *.ipynb notebooks/executed/

# 3. Generate HTML versions with outputs
for nb in notebooks/executed/*.ipynb; do
    jupyter nbconvert --to html "$nb" --output-dir notebooks/rendered/
done

# 4. Create clean versions for git
for nb in notebooks/executed/*.ipynb; do
    jupyter nbconvert --clear-output --to notebook "$nb" \
        --output-dir notebooks/clean/
done
```

### Phase 2: Extract and Structure Content (4 hours)

1. **Extract Images/Plots**
```python
# extract_images.py
from nbformat import read
import base64
import os

def extract_notebook_images(notebook_path, output_dir):
    nb = read(notebook_path, as_version=4)

    image_count = 0
    for cell_num, cell in enumerate(nb.cells):
        if cell.cell_type == 'code' and cell.outputs:
            for output in cell.outputs:
                if 'image/png' in output.get('data', {}):
                    image_data = output['data']['image/png']
                    image_bytes = base64.b64decode(image_data)

                    filename = f'cell_{cell_num}_output_{image_count}.png'
                    with open(f'{output_dir}/{filename}', 'wb') as f:
                        f.write(image_bytes)
                    image_count += 1

    return image_count
```

2. **Create Summary Documents**
```python
# create_summaries.py
def create_project_summary(notebook_path):
    """Generate a standalone report from notebook"""

    sections = {
        'overview': [],
        'methodology': [],
        'results': [],
        'code': [],
        'conclusions': []
    }

    # Parse notebook and categorize content
    # ... extraction logic ...

    # Generate markdown report
    return generate_markdown_report(sections)
```

### Phase 3: Setup Web Display (4 hours)

#### Using GitHub Pages + Jupyter Book

```bash
# Install Jupyter Book
pip install jupyter-book

# Create book structure
jupyter-book create portfolio_book

# Copy content
cp -r notebooks/* portfolio_book/notebooks/
cp -r reports/* portfolio_book/

# Build the book
jupyter-book build portfolio_book

# Deploy to GitHub Pages
ghp-import -n -p -f portfolio_book/_build/html
```

#### GitHub Actions for Automation

```yaml
# .github/workflows/build-book.yml
name: Build and Deploy Jupyter Book

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2

    - name: Setup Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9

    - name: Install dependencies
      run: |
        pip install jupyter-book
        pip install -r requirements.txt

    - name: Build the book
      run: |
        jupyter-book build docs

    - name: Deploy to GitHub Pages
      uses: peaceiris/actions-gh-pages@v3
      with:
        github_token: ${{ secrets.GITHUB_TOKEN }}
        publish_dir: ./docs/_build/html
```

---

## File Size Management

### Strategy for Large Notebooks

1. **Use Git LFS for Rendered Versions**
```bash
# .gitattributes
notebooks/rendered/*.html filter=lfs diff=lfs merge=lfs -text
notebooks/rendered/*.pdf filter=lfs diff=lfs merge=lfs -text
*.png filter=lfs diff=lfs merge=lfs -text
```

2. **Separate Branches**
```bash
# main branch - clean notebooks only
# rendered branch - notebooks with outputs
# gh-pages branch - built website

git checkout -b rendered
git add notebooks/executed/*.ipynb
git commit -m "Add executed notebooks with outputs"

git checkout main
# main only has clean notebooks
```

3. **External Storage for Large Assets**
- Host images on GitHub releases
- Use CDN for large datasets
- Link to Google Drive for supplementary materials

---

## Result: Professional Portfolio

### What Visitors See:

1. **GitHub Repository**
   - Clean, professional code
   - Comprehensive documentation
   - Small file sizes

2. **Portfolio Website** (yourname.github.io/projects)
   - Beautiful rendering of all notebooks
   - Interactive visualizations
   - Full narrative preserved
   - Professional appearance

3. **Multiple Access Methods**
   - View on GitHub (README with nbviewer links)
   - Interactive on Binder/Colab
   - Download and run locally
   - Read as static website

---

## Quick Start Commands

```bash
# 1. Setup structure
chmod +x setup_notebook_display.sh
./setup_notebook_display.sh

# 2. Generate all formats
python convert_notebooks.py

# 3. Build website
jupyter-book build docs

# 4. Preview locally
python -m http.server -d docs/_build/html

# 5. Deploy
./deploy_to_github_pages.sh
```

---

## Benefits of This Approach

✅ **Preserves Everything**: All text, results, and visualizations retained
✅ **Git-Friendly**: Clean notebooks in version control
✅ **Web-Ready**: Beautiful online portfolio
✅ **Professional**: Looks like production documentation
✅ **Searchable**: Full-text search on website
✅ **Reproducible**: Others can run the clean notebooks
✅ **Demonstrable**: Shows actual results and outputs

This strategy ensures your academic work is presented professionally while maintaining all the valuable content that demonstrates your capabilities.