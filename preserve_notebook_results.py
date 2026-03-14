#!/usr/bin/env python3
"""
Preserve and showcase notebook results professionally.
Extracts narratives, code, results, and visualizations into a structured format.
"""

import json
import base64
import re
from pathlib import Path
import nbformat
from datetime import datetime
import hashlib

class NotebookPreserver:
    """Extract and preserve all valuable content from Jupyter notebooks."""

    def __init__(self, notebook_path):
        self.notebook_path = Path(notebook_path)
        self.notebook_name = self.notebook_path.stem
        self.output_dir = Path('preserved_content') / self.notebook_name
        self.output_dir.mkdir(parents=True, exist_ok=True)

        with open(notebook_path) as f:
            self.notebook = nbformat.read(f, as_version=4)

        self.results = {
            'metadata': {
                'name': self.notebook_name,
                'path': str(notebook_path),
                'processed': datetime.now().isoformat(),
                'cell_count': len(self.notebook.cells)
            },
            'narrative': [],
            'code_snippets': [],
            'results': [],
            'visualizations': [],
            'metrics': {}
        }

    def extract_all(self):
        """Extract all valuable content from the notebook."""
        print(f"📓 Processing {self.notebook_name}...")

        for idx, cell in enumerate(self.notebook.cells):
            if cell.cell_type == 'markdown':
                self._extract_markdown(cell, idx)
            elif cell.cell_type == 'code':
                self._extract_code(cell, idx)

        self._save_results()
        self._create_showcase()
        return self.results

    def _extract_markdown(self, cell, idx):
        """Extract narrative content from markdown cells."""
        content = cell.source.strip()
        if not content:
            return

        # Categorize markdown content
        categories = {
            'overview': ['overview', 'introduction', 'objective', 'goal'],
            'methodology': ['method', 'approach', 'technique', 'algorithm'],
            'results': ['result', 'finding', 'performance', 'accuracy'],
            'conclusion': ['conclusion', 'summary', 'future', 'discussion']
        }

        category = 'general'
        for cat, keywords in categories.items():
            if any(keyword in content.lower() for keyword in keywords):
                category = cat
                break

        self.results['narrative'].append({
            'cell_index': idx,
            'category': category,
            'content': content
        })

    def _extract_code(self, cell, idx):
        """Extract code and its outputs."""
        code = cell.source.strip()
        if not code:
            return

        # Store important code snippets
        if self._is_important_code(code):
            self.results['code_snippets'].append({
                'cell_index': idx,
                'code': code,
                'description': self._describe_code(code)
            })

        # Process outputs
        if hasattr(cell, 'outputs'):
            for output_idx, output in enumerate(cell.outputs):
                self._process_output(output, idx, output_idx)

    def _is_important_code(self, code):
        """Identify important code snippets to preserve."""
        important_patterns = [
            r'class\s+\w+',  # Class definitions
            r'def\s+\w+',    # Function definitions
            r'model\s*=',    # Model definitions
            r'accuracy|precision|recall|f1',  # Metrics
            r'fit\(|train\(|predict\(',  # Training/prediction
            r'import\s+',    # Key imports
        ]
        return any(re.search(pattern, code, re.IGNORECASE) for pattern in important_patterns)

    def _describe_code(self, code):
        """Generate a description of what the code does."""
        descriptions = {
            r'import': 'Import statements',
            r'class\s+\w+': 'Class definition',
            r'def\s+\w+': 'Function definition',
            r'model\s*=': 'Model initialization',
            r'\.fit\(': 'Model training',
            r'\.predict\(': 'Making predictions',
            r'accuracy': 'Performance metrics calculation'
        }

        for pattern, description in descriptions.items():
            if re.search(pattern, code, re.IGNORECASE):
                return description
        return 'Code implementation'

    def _process_output(self, output, cell_idx, output_idx):
        """Process and categorize cell outputs."""
        output_type = output.get('output_type', '')

        # Handle different output types
        if output_type in ['stream', 'execute_result', 'display_data']:
            data = output.get('data', {})

            # Text output (results, metrics)
            if 'text/plain' in data:
                text = data['text/plain']
                self._extract_metrics_from_text(text)
                self.results['results'].append({
                    'cell_index': cell_idx,
                    'type': 'text',
                    'content': text[:500]  # Truncate long outputs
                })

            # Images (plots, visualizations)
            if 'image/png' in data:
                self._save_image(data['image/png'], cell_idx, output_idx)

            # HTML output
            if 'text/html' in data:
                html = data['text/html']
                self.results['results'].append({
                    'cell_index': cell_idx,
                    'type': 'html',
                    'preview': html[:200] + '...' if len(html) > 200 else html
                })

    def _extract_metrics_from_text(self, text):
        """Extract performance metrics from text output."""
        patterns = {
            'accuracy': r'accuracy[:\s]+([0-9.]+)',
            'precision': r'precision[:\s]+([0-9.]+)',
            'recall': r'recall[:\s]+([0-9.]+)',
            'f1_score': r'f1[:\s\-_]+score[:\s]+([0-9.]+)',
            'loss': r'loss[:\s]+([0-9.]+)',
            'auc': r'auc[:\s]+([0-9.]+)',
            'rmse': r'rmse[:\s]+([0-9.]+)',
            'mae': r'mae[:\s]+([0-9.]+)'
        }

        for metric, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = float(match.group(1))
                    self.results['metrics'][metric] = value
                    print(f"  ✓ Found {metric}: {value}")
                except ValueError:
                    pass

    def _save_image(self, image_data, cell_idx, output_idx):
        """Save image output and create reference."""
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)

        # Create unique filename
        hash_obj = hashlib.md5(image_bytes[:1000])
        image_hash = hash_obj.hexdigest()[:8]
        filename = f"cell_{cell_idx}_output_{output_idx}_{image_hash}.png"
        filepath = self.output_dir / 'images'
        filepath.mkdir(exist_ok=True)
        image_path = filepath / filename

        # Save image
        with open(image_path, 'wb') as f:
            f.write(image_bytes)

        # Store reference
        self.results['visualizations'].append({
            'cell_index': cell_idx,
            'filename': filename,
            'path': str(image_path),
            'size': len(image_bytes)
        })

        print(f"  ✓ Saved visualization: {filename}")

    def _save_results(self):
        """Save extracted results to JSON."""
        json_path = self.output_dir / f"{self.notebook_name}_extracted.json"
        with open(json_path, 'w') as f:
            # Create serializable version
            serializable = {
                k: v for k, v in self.results.items()
                if k != 'visualizations'  # Skip image data
            }
            serializable['visualizations'] = [
                {'filename': v['filename'], 'cell_index': v['cell_index']}
                for v in self.results['visualizations']
            ]
            json.dump(serializable, f, indent=2)
        print(f"  ✓ Saved results to {json_path}")

    def _create_showcase(self):
        """Create a beautiful showcase document."""
        showcase_path = self.output_dir / f"{self.notebook_name}_showcase.md"

        with open(showcase_path, 'w') as f:
            # Title and metadata
            f.write(f"# {self.notebook_name.replace('_', ' ').title()}\n\n")
            f.write(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n")

            # Overview section
            f.write("## Overview\n\n")
            overview_texts = [n['content'] for n in self.results['narrative']
                             if n['category'] == 'overview']
            if overview_texts:
                f.write(overview_texts[0][:500] + '\n\n')

            # Key Metrics
            if self.results['metrics']:
                f.write("## Performance Metrics\n\n")
                f.write("| Metric | Value |\n")
                f.write("|--------|-------|\n")
                for metric, value in self.results['metrics'].items():
                    if value < 1:  # Assume percentage
                        f.write(f"| {metric.title()} | {value:.1%} |\n")
                    else:
                        f.write(f"| {metric.title()} | {value:.3f} |\n")
                f.write("\n")

            # Visualizations
            if self.results['visualizations']:
                f.write("## Visualizations\n\n")
                for viz in self.results['visualizations'][:5]:  # Top 5
                    f.write(f"![Result](images/{viz['filename']})\n\n")

            # Key Code
            f.write("## Implementation Highlights\n\n")
            for snippet in self.results['code_snippets'][:3]:  # Top 3
                f.write(f"### {snippet['description']}\n\n")
                f.write("```python\n")
                f.write(snippet['code'][:500])  # Truncate if long
                f.write("\n```\n\n")

            # Conclusions
            f.write("## Conclusions\n\n")
            conclusions = [n['content'] for n in self.results['narrative']
                          if n['category'] == 'conclusion']
            if conclusions:
                f.write(conclusions[0] + '\n\n')

            # How to reproduce
            f.write("## Reproducibility\n\n")
            f.write("To reproduce these results:\n\n")
            f.write("1. Install dependencies: `pip install -r requirements.txt`\n")
            f.write(f"2. Run the notebook: `jupyter notebook {self.notebook_name}.ipynb`\n")
            f.write("3. Execute all cells in order\n\n")

        print(f"  ✓ Created showcase: {showcase_path}")


def process_all_notebooks():
    """Process all notebooks in the current directory tree."""
    notebooks_found = list(Path('.').glob('**/*.ipynb'))
    notebooks_found = [nb for nb in notebooks_found
                       if 'checkpoint' not in str(nb) and '.ipynb_checkpoints' not in str(nb)]

    print(f"Found {len(notebooks_found)} notebooks to process\n")

    all_results = {}
    for notebook_path in notebooks_found:
        preserver = NotebookPreserver(notebook_path)
        results = preserver.extract_all()
        all_results[str(notebook_path)] = results['metrics']

    # Create master summary
    summary_path = Path('preserved_content') / 'PORTFOLIO_SUMMARY.md'
    with open(summary_path, 'w') as f:
        f.write("# Portfolio Summary\n\n")
        f.write(f"Processed {len(all_results)} projects\n\n")

        f.write("## Projects Overview\n\n")
        for path, metrics in all_results.items():
            f.write(f"### {Path(path).stem}\n")
            if metrics:
                best_metric = max(metrics.items(), key=lambda x: x[1])
                f.write(f"**Best Result**: {best_metric[0]} = {best_metric[1]:.1%}\n\n")
            else:
                f.write("*Metrics extraction in progress*\n\n")

    print(f"\n✅ Complete! Check ./preserved_content/ for all extracted content")
    print(f"📊 Portfolio summary saved to {summary_path}")


if __name__ == '__main__':
    process_all_notebooks()