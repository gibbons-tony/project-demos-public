#!/bin/bash

# Notebook Display Setup Script
# Preserves notebook content while making it git-friendly and web-viewable

set -e

echo "📓 Setting up Notebook Display System"
echo "====================================="

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Create directory structure
echo -e "${BLUE}Creating directory structure...${NC}"

mkdir -p notebooks/{clean,rendered,executed,reports}
mkdir -p docs/{assets,images,projects}
mkdir -p _site

# Function to process a notebook
process_notebook() {
    local notebook_path="$1"
    local notebook_name=$(basename "$notebook_path" .ipynb)
    local project_dir=$(dirname "$notebook_path")

    echo -e "${GREEN}Processing: ${notebook_name}${NC}"

    # 1. Create a clean version (no outputs) for git
    if [ -f "$notebook_path" ]; then
        echo "  - Creating clean version for git..."
        jupyter nbconvert --clear-output --to notebook "$notebook_path" \
            --output "notebooks/clean/${notebook_name}.ipynb" 2>/dev/null || {
            echo -e "${YELLOW}  Warning: Could not clean ${notebook_name}${NC}"
        }

        # 2. Create HTML version with outputs
        echo "  - Creating HTML version..."
        jupyter nbconvert --to html "$notebook_path" \
            --output "notebooks/rendered/${notebook_name}.html" \
            --ExecutePreprocessor.timeout=600 2>/dev/null || {
            echo -e "${YELLOW}  Warning: Could not create HTML for ${notebook_name}${NC}"
        }

        # 3. Create markdown version
        echo "  - Creating markdown report..."
        jupyter nbconvert --to markdown "$notebook_path" \
            --output "notebooks/reports/${notebook_name}_report.md" 2>/dev/null || {
            echo -e "${YELLOW}  Warning: Could not create markdown for ${notebook_name}${NC}"
        }
    fi
}

# Process all notebooks
echo -e "${BLUE}Processing notebooks...${NC}"
for notebook in $(find . -name "*.ipynb" -not -path "./notebooks/*" -not -path "./.git/*"); do
    process_notebook "$notebook"
done

# Create index.html for easy viewing
echo -e "${BLUE}Creating index.html...${NC}"

cat > docs/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ML Projects Portfolio</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        .container {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        h1 {
            color: #667eea;
            border-bottom: 3px solid #764ba2;
            padding-bottom: 10px;
        }
        .project-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .project-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            transition: transform 0.3s, box-shadow 0.3s;
        }
        .project-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }
        .project-card h2 {
            color: #667eea;
            margin-top: 0;
        }
        .project-links {
            margin-top: 15px;
        }
        .project-links a {
            display: inline-block;
            margin: 5px 10px 5px 0;
            padding: 8px 16px;
            background: #667eea;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            transition: background 0.3s;
        }
        .project-links a:hover {
            background: #764ba2;
        }
        .tech-stack {
            margin-top: 10px;
            font-size: 0.9em;
            color: #666;
        }
        .tech-stack span {
            display: inline-block;
            padding: 3px 8px;
            margin: 2px;
            background: #f0f0f0;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Machine Learning Projects Portfolio</h1>
        <p>Welcome to my collection of academic projects from UC Berkeley MIDS program.</p>

        <div class="project-grid">
            <!-- Computer Vision Project -->
            <div class="project-card">
                <h2>🔬 Computer Vision</h2>
                <p>X-ray classification using deep learning with transfer learning from ResNet50.</p>
                <div class="tech-stack">
                    <span>TensorFlow</span>
                    <span>Keras</span>
                    <span>CNN</span>
                </div>
                <div class="project-links">
                    <a href="../notebooks/rendered/xray_classification.html">View Results</a>
                    <a href="../notebooks/reports/xray_classification_report.md">Read Report</a>
                    <a href="https://github.com/yourusername/project_demos_public/tree/main/computer_vision_demo">GitHub</a>
                </div>
            </div>

            <!-- NLP Project -->
            <div class="project-card">
                <h2>📝 Natural Language Processing</h2>
                <p>Sentiment analysis and text classification experiments with modern NLP techniques.</p>
                <div class="tech-stack">
                    <span>NLTK</span>
                    <span>spaCy</span>
                    <span>Transformers</span>
                </div>
                <div class="project-links">
                    <a href="../notebooks/rendered/nlp_analysis.html">View Results</a>
                    <a href="../notebooks/reports/nlp_analysis_report.md">Read Report</a>
                    <a href="https://github.com/yourusername/project_demos_public/tree/main/nlp_demo">GitHub</a>
                </div>
            </div>

            <!-- RAG Project -->
            <div class="project-card">
                <h2>🤖 RAG System</h2>
                <p>Retrieval-Augmented Generation combining vector search with LLMs.</p>
                <div class="tech-stack">
                    <span>LangChain</span>
                    <span>FAISS</span>
                    <span>OpenAI</span>
                </div>
                <div class="project-links">
                    <a href="../notebooks/rendered/rag_demo.html">View Results</a>
                    <a href="../notebooks/reports/rag_demo_report.md">Read Report</a>
                    <a href="https://github.com/yourusername/project_demos_public/tree/main/rag_demo">GitHub</a>
                </div>
            </div>

            <!-- Cloud App Project -->
            <div class="project-card">
                <h2>☁️ Cloud ML API</h2>
                <p>Production-ready ML API with Kubernetes deployment and monitoring.</p>
                <div class="tech-stack">
                    <span>FastAPI</span>
                    <span>Docker</span>
                    <span>Kubernetes</span>
                    <span>Redis</span>
                </div>
                <div class="project-links">
                    <a href="https://github.com/yourusername/project_demos_public/tree/main/cloud_app_demo">View Project</a>
                    <a href="../cloud_app_demo/README.md">Documentation</a>
                </div>
            </div>

            <!-- Capstone Project -->
            <div class="project-card">
                <h2>🏆 UC Berkeley Capstone</h2>
                <p>Multi-agent commodity trading system with ML forecasting.</p>
                <div class="tech-stack">
                    <span>PySpark</span>
                    <span>Databricks</span>
                    <span>AWS Lambda</span>
                </div>
                <div class="project-links">
                    <a href="https://github.com/yourusername/project_demos_public/tree/main/ucberkeley-capstone">View Project</a>
                    <a href="../ucberkeley-capstone/README.md">Documentation</a>
                </div>
            </div>
        </div>

        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #e0e0e0; text-align: center; color: #666;">
            <p>© 2024 | Built with Jupyter, Python, and lots of ☕</p>
            <p>
                <a href="https://github.com/yourusername" style="color: #667eea;">GitHub</a> |
                <a href="https://linkedin.com/in/yourusername" style="color: #667eea;">LinkedIn</a>
            </p>
        </div>
    </div>
</body>
</html>
EOF

echo -e "${GREEN}✓ Created index.html${NC}"

# Create a Python script to extract key metrics from notebooks
echo -e "${BLUE}Creating metrics extraction script...${NC}"

cat > extract_metrics.py << 'EOF'
#!/usr/bin/env python3
"""Extract key metrics and visualizations from notebooks."""

import json
import re
import base64
from pathlib import Path
import nbformat

def extract_metrics(notebook_path):
    """Extract performance metrics from notebook outputs."""

    metrics = {
        'accuracy': None,
        'precision': None,
        'recall': None,
        'f1_score': None,
        'images': []
    }

    with open(notebook_path) as f:
        nb = nbformat.read(f, as_version=4)

    for cell in nb.cells:
        if cell.cell_type == 'code' and cell.outputs:
            for output in cell.outputs:
                # Look for text outputs with metrics
                if 'text/plain' in output.get('data', {}):
                    text = output['data']['text/plain']

                    # Search for common metric patterns
                    accuracy_match = re.search(r'accuracy[:\s]+([0-9.]+)', text, re.IGNORECASE)
                    if accuracy_match:
                        metrics['accuracy'] = float(accuracy_match.group(1))

                    precision_match = re.search(r'precision[:\s]+([0-9.]+)', text, re.IGNORECASE)
                    if precision_match:
                        metrics['precision'] = float(precision_match.group(1))

                # Extract images
                if 'image/png' in output.get('data', {}):
                    metrics['images'].append({
                        'type': 'png',
                        'data': output['data']['image/png'][:100] + '...'  # Truncate for display
                    })

    return metrics

if __name__ == '__main__':
    # Process all notebooks
    for notebook_path in Path('.').glob('**/*.ipynb'):
        if 'checkpoint' not in str(notebook_path):
            print(f"Processing {notebook_path}...")
            metrics = extract_metrics(notebook_path)

            # Save metrics to JSON
            output_path = Path('notebooks/reports') / f"{notebook_path.stem}_metrics.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(metrics, f, indent=2)

            print(f"  Saved metrics to {output_path}")
            if metrics['accuracy']:
                print(f"  Accuracy: {metrics['accuracy']:.2%}")
EOF

chmod +x extract_metrics.py
echo -e "${GREEN}✓ Created metrics extraction script${NC}"

# Create a simple local server script
echo -e "${BLUE}Creating local server script...${NC}"

cat > serve_local.py << 'EOF'
#!/usr/bin/env python3
"""Simple HTTP server to view the portfolio locally."""

import http.server
import socketserver
import webbrowser
from pathlib import Path

PORT = 8000

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="docs", **kwargs)

print(f"🌐 Starting local server at http://localhost:{PORT}")
print("📁 Serving from ./docs directory")
print("Press Ctrl+C to stop\n")

with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
    webbrowser.open(f'http://localhost:{PORT}')
    httpd.serve_forever()
EOF

chmod +x serve_local.py
echo -e "${GREEN}✓ Created local server script${NC}"

# Create GitHub Actions workflow for automatic deployment
echo -e "${BLUE}Creating GitHub Actions workflow...${NC}"

mkdir -p .github/workflows

cat > .github/workflows/deploy-portfolio.yml << 'EOF'
name: Deploy Portfolio

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install jupyter nbconvert

      - name: Process notebooks
        run: |
          ./setup_notebook_display.sh

      - name: Upload artifacts
        uses: actions/upload-pages-artifact@v2
        with:
          path: ./docs

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v2
EOF

echo -e "${GREEN}✓ Created GitHub Actions workflow${NC}"

# Summary
echo ""
echo "====================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "====================================="
echo ""
echo "📂 Created structure:"
echo "  notebooks/clean/     - Git-friendly notebooks (no outputs)"
echo "  notebooks/rendered/  - HTML versions with all outputs"
echo "  notebooks/reports/   - Markdown reports extracted"
echo "  docs/               - Website files"
echo ""
echo "🚀 Next steps:"
echo ""
echo "1. View locally:"
echo "   python serve_local.py"
echo ""
echo "2. Extract metrics:"
echo "   python extract_metrics.py"
echo ""
echo "3. Deploy to GitHub Pages:"
echo "   git add ."
echo "   git commit -m 'Setup portfolio display'"
echo "   git push"
echo ""
echo "4. Enable GitHub Pages:"
echo "   Go to Settings > Pages > Source: GitHub Actions"
echo ""
echo "Your portfolio will be live at:"
echo "https://[your-username].github.io/project_demos_public"
echo ""
echo "✨ Your notebooks are now preserved AND presentable!"