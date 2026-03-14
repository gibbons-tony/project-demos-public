#!/bin/bash

# Parallel Notebook Showcase Builder
# Preserves originals while creating multiple display formats

set -e

echo "🚀 Building Parallel Notebook Showcase"
echo "======================================"
echo "✅ Original files will NOT be modified"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Create parallel structure for showcasing
echo -e "${BLUE}Creating showcase directory structure...${NC}"

mkdir -p showcase/{notebooks,html,markdown,images,metrics}
mkdir -p showcase/website/{assets,projects}

# Function to process notebook in parallel (non-destructive)
process_notebook_parallel() {
    local original_path="$1"
    local notebook_name=$(basename "$original_path" .ipynb)
    local project_name=$(dirname "$original_path")

    echo -e "${GREEN}Processing: ${notebook_name} (preserving original)${NC}"

    if [ -f "$original_path" ]; then
        # 1. Copy original to showcase for preservation
        cp "$original_path" "showcase/notebooks/${notebook_name}_original.ipynb"
        echo "  ✓ Preserved original"

        # 2. Create clean version for viewing/git
        jupyter nbconvert --clear-output --to notebook "$original_path" \
            --output "showcase/notebooks/${notebook_name}_clean.ipynb" 2>/dev/null || {
            echo -e "${YELLOW}  ⚠ Could not create clean version${NC}"
        }

        # 3. Execute and save with all outputs
        echo "  - Executing notebook..."
        jupyter nbconvert --to notebook --execute "$original_path" \
            --output "showcase/notebooks/${notebook_name}_executed.ipynb" \
            --ExecutePreprocessor.timeout=600 \
            --allow-errors 2>/dev/null || {
            # If execution fails, just copy original
            cp "$original_path" "showcase/notebooks/${notebook_name}_executed.ipynb"
            echo -e "${YELLOW}  ⚠ Execution failed, using original with outputs${NC}"
        }

        # 4. Create HTML version with outputs
        echo "  - Creating HTML showcase..."
        jupyter nbconvert --to html "showcase/notebooks/${notebook_name}_executed.ipynb" \
            --output "../html/${notebook_name}.html" \
            --template classic 2>/dev/null || {
            echo -e "${YELLOW}  ⚠ Could not create HTML${NC}"
        }

        # 5. Create markdown documentation
        echo "  - Extracting markdown report..."
        jupyter nbconvert --to markdown "showcase/notebooks/${notebook_name}_executed.ipynb" \
            --output "../markdown/${notebook_name}.md" 2>/dev/null || {
            echo -e "${YELLOW}  ⚠ Could not create markdown${NC}"
        }

        # 6. Extract metrics using Python
        python3 - << EOF 2>/dev/null || echo "  ⚠ Metrics extraction skipped"
import json
import re
import nbformat

try:
    with open("showcase/notebooks/${notebook_name}_executed.ipynb") as f:
        nb = nbformat.read(f, as_version=4)

    metrics = {}
    for cell in nb.cells:
        if cell.cell_type == 'code' and hasattr(cell, 'outputs'):
            for output in cell.outputs:
                if 'text/plain' in output.get('data', {}):
                    text = output['data']['text/plain']
                    # Look for accuracy
                    if match := re.search(r'accuracy[:\s]+([0-9.]+)', text, re.IGNORECASE):
                        metrics['accuracy'] = float(match.group(1))
                    # Look for other metrics
                    if match := re.search(r'precision[:\s]+([0-9.]+)', text, re.IGNORECASE):
                        metrics['precision'] = float(match.group(1))
                    if match := re.search(r'recall[:\s]+([0-9.]+)', text, re.IGNORECASE):
                        metrics['recall'] = float(match.group(1))

    if metrics:
        with open("showcase/metrics/${notebook_name}_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"  ✓ Extracted {len(metrics)} metrics")
except Exception as e:
    pass
EOF

        echo "  ✓ Completed ${notebook_name}"
    fi
}

# Process all notebooks in parallel structure
echo ""
echo -e "${BLUE}Processing notebooks in parallel...${NC}"

# Find all notebooks
notebook_count=0
for notebook in $(find . -name "*.ipynb" -not -path "./showcase/*" -not -path "./.ipynb_checkpoints/*" -not -path "./.git/*"); do
    process_notebook_parallel "$notebook"
    ((notebook_count++))
done

echo ""
echo -e "${GREEN}Processed $notebook_count notebooks${NC}"

# Create main showcase index
echo ""
echo -e "${BLUE}Creating showcase website...${NC}"

cat > showcase/website/index.html << 'EOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Notebooks Showcase</title>
    <style>
        :root {
            --primary: #667eea;
            --secondary: #764ba2;
            --dark: #2d3748;
            --light: #f7fafc;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
        }

        header {
            text-align: center;
            color: white;
            padding: 40px 0;
        }

        header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        header p {
            font-size: 1.2em;
            opacity: 0.95;
        }

        .notebook-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 25px;
            margin-top: 40px;
        }

        .notebook-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: transform 0.3s, box-shadow 0.3s;
        }

        .notebook-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 40px rgba(0,0,0,0.15);
        }

        .notebook-card h3 {
            color: var(--primary);
            margin-bottom: 10px;
            font-size: 1.4em;
        }

        .project-type {
            display: inline-block;
            padding: 4px 10px;
            background: var(--light);
            color: var(--dark);
            border-radius: 20px;
            font-size: 0.85em;
            margin-bottom: 15px;
        }

        .metrics {
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }

        .metrics h4 {
            color: var(--dark);
            margin-bottom: 8px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .metric-item {
            display: inline-block;
            margin: 5px 10px 5px 0;
            padding: 5px 10px;
            background: white;
            border-radius: 5px;
            font-size: 0.9em;
        }

        .metric-value {
            font-weight: bold;
            color: var(--primary);
        }

        .view-options {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }

        .view-btn {
            flex: 1;
            padding: 10px;
            text-align: center;
            background: var(--primary);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            transition: background 0.3s;
            font-weight: 500;
        }

        .view-btn:hover {
            background: var(--secondary);
        }

        .view-btn.secondary {
            background: white;
            color: var(--primary);
            border: 2px solid var(--primary);
        }

        .view-btn.secondary:hover {
            background: var(--primary);
            color: white;
        }

        footer {
            text-align: center;
            color: white;
            margin-top: 60px;
            padding: 20px;
        }

        footer a {
            color: white;
            text-decoration: none;
            margin: 0 10px;
        }

        footer a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Notebook Showcase</h1>
            <p>Interactive notebooks with preserved results and visualizations</p>
        </header>

        <div class="notebook-grid" id="notebook-grid">
            <!-- Notebooks will be inserted here by JavaScript -->
        </div>

        <footer>
            <p>Created with Jupyter Notebooks | All content preserved</p>
            <div style="margin-top: 10px;">
                <a href="https://github.com/yourusername/project_demos_public">GitHub</a>
                <a href="https://linkedin.com/in/yourusername">LinkedIn</a>
            </div>
        </footer>
    </div>

    <script>
        // Notebook data (will be populated by the script)
        const notebooks = [
EOF

# Add notebook entries to the HTML
for notebook_html in showcase/html/*.html; do
    if [ -f "$notebook_html" ]; then
        name=$(basename "$notebook_html" .html)

        # Check if metrics exist
        metrics_file="showcase/metrics/${name}_metrics.json"
        if [ -f "$metrics_file" ]; then
            metrics=$(cat "$metrics_file")
        else
            metrics="{}"
        fi

        # Determine project type from path
        project_type="Machine Learning"
        if [[ "$name" == *"vision"* ]]; then
            project_type="Computer Vision"
        elif [[ "$name" == *"nlp"* ]]; then
            project_type="NLP"
        elif [[ "$name" == *"rag"* ]]; then
            project_type="RAG/LLM"
        fi

        cat >> showcase/website/index.html << EOF
            {
                name: "$name",
                type: "$project_type",
                htmlPath: "../html/${name}.html",
                markdownPath: "../markdown/${name}.md",
                notebookPath: "../notebooks/${name}_clean.ipynb",
                metrics: $metrics
            },
EOF
    fi
done

# Complete the HTML file
cat >> showcase/website/index.html << 'EOF'
        ];

        // Function to create notebook cards
        function createNotebookCard(notebook) {
            const card = document.createElement('div');
            card.className = 'notebook-card';

            // Format name
            const displayName = notebook.name
                .replace(/_/g, ' ')
                .replace(/\b\w/g, c => c.toUpperCase());

            // Build metrics HTML
            let metricsHtml = '';
            if (notebook.metrics && Object.keys(notebook.metrics).length > 0) {
                metricsHtml = '<div class="metrics"><h4>Performance Metrics</h4>';
                for (const [key, value] of Object.entries(notebook.metrics)) {
                    const formattedValue = value < 1 ? (value * 100).toFixed(1) + '%' : value.toFixed(3);
                    metricsHtml += `<span class="metric-item">${key}: <span class="metric-value">${formattedValue}</span></span>`;
                }
                metricsHtml += '</div>';
            }

            card.innerHTML = `
                <h3>${displayName}</h3>
                <span class="project-type">${notebook.type}</span>
                ${metricsHtml}
                <div class="view-options">
                    <a href="${notebook.htmlPath}" class="view-btn" target="_blank">View HTML</a>
                    <a href="${notebook.notebookPath}" class="view-btn secondary" target="_blank">Clean Notebook</a>
                </div>
            `;

            return card;
        }

        // Populate the grid
        const grid = document.getElementById('notebook-grid');
        notebooks.forEach(notebook => {
            grid.appendChild(createNotebookCard(notebook));
        });
    </script>
</body>
</html>
EOF

echo -e "${GREEN}✓ Created showcase website${NC}"

# Create a README for the showcase
cat > showcase/README.md << 'EOF'
# Notebook Showcase

This directory contains multiple formats of all project notebooks, preserving all content while providing clean versions for different use cases.

## Directory Structure

```
showcase/
├── notebooks/         # All notebook versions
│   ├── *_original.ipynb    # Original with outputs preserved
│   ├── *_clean.ipynb        # No outputs (git-friendly)
│   └── *_executed.ipynb     # Fresh execution with all outputs
├── html/             # HTML renderings with all outputs
├── markdown/         # Markdown exports
├── metrics/          # Extracted performance metrics (JSON)
├── images/           # Extracted visualizations
└── website/          # Static website for viewing
```

## Viewing Options

1. **Local Website**: Open `showcase/website/index.html` in your browser
2. **HTML Notebooks**: Open any file in `showcase/html/` to see full results
3. **Clean Notebooks**: Use files in `showcase/notebooks/*_clean.ipynb` for git
4. **Original Notebooks**: Preserved in `showcase/notebooks/*_original.ipynb`

## Key Features

- ✅ Original notebooks completely preserved
- ✅ All outputs and visualizations retained
- ✅ Clean versions for version control
- ✅ HTML for easy sharing and viewing
- ✅ Metrics automatically extracted
- ✅ Beautiful showcase website

## Usage

To update the showcase after notebook changes:
```bash
./build_parallel_showcase.sh
```

This will rebuild all formats while preserving your originals.
EOF

# Summary report
echo ""
echo "======================================"
echo -e "${GREEN}✅ Parallel Showcase Build Complete!${NC}"
echo "======================================"
echo ""
echo "📁 Created in ./showcase/:"
echo "  • $(ls showcase/notebooks/*.ipynb 2>/dev/null | wc -l) notebook versions"
echo "  • $(ls showcase/html/*.html 2>/dev/null | wc -l) HTML renderings"
echo "  • $(ls showcase/markdown/*.md 2>/dev/null | wc -l) Markdown reports"
echo "  • $(ls showcase/metrics/*.json 2>/dev/null | wc -l) metrics files"
echo ""
echo "🎯 Your original notebooks are UNTOUCHED"
echo ""
echo "📊 View your showcase:"
echo "  1. Open showcase/website/index.html in browser"
echo "  2. Or run: python -m http.server -d showcase/website"
echo ""
echo "✨ All notebook content preserved and beautifully presented!"