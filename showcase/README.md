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
