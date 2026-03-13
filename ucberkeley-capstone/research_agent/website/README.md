# Research Agent Web Page

**Location**: `research_agent/website/index.html`
**Theme Color**: `#22c55dff` (Green)
**Status**: Ready for integration into main capstone website

---

## Overview

Interactive web page documenting the Research Agent's complete data pipeline from AWS Lambda ingestion through Databricks Bronze/Silver/Gold layers.

## Features

✅ **Visual Pipeline Diagram**
- 5 stages: Lambda Ingestion → Landing → Bronze → Silver → Gold
- Color-coded status badges (Automated vs Manual)
- GitHub links to all scripts and Lambda functions

✅ **Interactive Components**
- Hover effects on pipeline stages
- Clickable GitHub links for every component
- Responsive grid layouts

✅ **Comprehensive Documentation**
- 6 data sources with EventBridge schedules
- Table schemas and deduplication strategies
- Data flow visualizations
- Key statistics dashboard

✅ **Research Agent Theme**
- Primary color: `#22c55dff` (green)
- Dark gradient background
- Clean, professional design matching existing presentation slides

---

## File Structure

```
research_agent/website/
├── index.html          # Main page (standalone, no external dependencies)
└── README.md           # This file
```

---

## GitHub Links

**⚠️ ACTION REQUIRED**: Replace `YOUR_ORG` in all GitHub links with your actual organization/username.

Search and replace in `index.html`:
```
YOUR_ORG → your-github-org
```

Example links to update:
- `https://github.com/YOUR_ORG/ucberkeley-capstone/blob/main/research_agent/infrastructure/lambda/functions/market-data-fetcher/app.py`
- `https://github.com/YOUR_ORG/ucberkeley-capstone/blob/main/research_agent/sql/create_gold_unified_data.sql`

---

## Integration into Main Website

This page is designed to be a **tab** in the capstone project's main website.

### Option 1: Standalone Page
Simply link to `research_agent/website/index.html` from the main navigation.

### Option 2: Embedded in Tabs
Extract the `<div class="container">` content and embed within a tabbed interface:

```html
<div id="research-agent-tab" class="tab-content">
    <!-- Copy content from index.html's .container div -->
</div>
```

### Option 3: iframe
```html
<iframe src="research_agent/website/index.html"
        width="100%"
        height="1000px"
        frameborder="0">
</iframe>
```

---

## Stats Displayed

- **6 Data Sources**: Market, VIX, FX, Weather, CFTC, GDELT
- **5 Lambda Functions**: Automated daily ingestion
- **~7K Rows**: Gold table (2 commodities × ~3,500 days)
- **67 Weather Regions**: Coffee/sugar growing areas
- **2 AM UTC**: Daily sync schedule

---

## Sections

1. **Header** - Agent badge, title, stats dashboard
2. **Pipeline Stages** - 5-stage visual flow with GitHub links
3. **Key Features** - Forward-filling, multi-regional weather, FX, sentiment
4. **Final Output** - Gold table schema
5. **GitHub Banner** - Link to full dependency graph documentation
6. **Footer** - Team credits

---

## External Dependencies

**None!** Page is completely self-contained:
- No external CSS frameworks
- No JavaScript libraries
- No image assets
- Works offline

All styles are inline in `<style>` tag.

---

## Related Documentation

- [GOLD_UNIFIED_DATA_DEPENDENCY_GRAPH.md](../infrastructure/GOLD_UNIFIED_DATA_DEPENDENCY_GRAPH.md) - Complete technical dependency graph
- [OBSOLETE_CODE_FINDINGS.md](../infrastructure/OBSOLETE_CODE_FINDINGS.md) - Unused components analysis
- [UNIFIED_DATA_ARCHITECTURE.md](../UNIFIED_DATA_ARCHITECTURE.md) - Data architecture details

---

## Viewing Locally

```bash
# Open in default browser
open research_agent/website/index.html

# Or navigate directly
cd research_agent/website
open index.html
```

---

## Customization

### Change Theme Color
Search for `--research-green: #22c55d` in the `:root` CSS variables and update:

```css
:root {
    --research-green: #YOUR_COLOR;
    --research-green-dark: #DARKER_SHADE;
    --research-green-light: #LIGHTER_SHADE;
}
```

### Add New Data Sources
Add a new `.component-card` div in the Stage 1 section:

```html
<div class="component-card">
    <div class="component-name">🔔 New Data Source</div>
    <div class="component-detail">EventBridge: rule-name</div>
    <div class="component-detail">Lambda: function-name</div>
    <div class="component-detail">Source: API Name</div>
    <div class="component-detail">Output: s3://.../path/</div>
    <a href="https://github.com/.../app.py" class="component-link" target="_blank">View Code</a>
</div>
```

---

**Document Owner**: Research Agent
**Last Updated**: 2025-12-05
**Status**: Ready for final deliverables
