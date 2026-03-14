#!/bin/bash

# Academic Project Portfolio - Automated Cleanup Script
# This script performs initial cleanup and structure improvements

echo "🚀 Starting Academic Project Portfolio Cleanup..."
echo "=============================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# 1. Clean Jupyter Notebooks
echo ""
echo "📓 Cleaning Jupyter Notebooks..."
echo "--------------------------------"

cleanup_notebooks() {
    local count=0
    while IFS= read -r notebook; do
        if jupyter nbconvert --clear-output --inplace "$notebook" 2>/dev/null; then
            print_status "Cleaned: $(basename "$notebook")"
            ((count++))
        else
            print_warning "Failed to clean: $(basename "$notebook")"
        fi
    done < <(find . -name "*.ipynb" -not -path "./.git/*")
    echo "   Cleaned $count notebooks total"
}

cleanup_notebooks

# 2. Remove Python cache files
echo ""
echo "🗑️  Removing Python Cache Files..."
echo "--------------------------------"

remove_pycache() {
    local count=0
    while IFS= read -r dir; do
        rm -rf "$dir"
        ((count++))
    done < <(find . -type d -name "__pycache__" -not -path "./.git/*")

    while IFS= read -r file; do
        rm -f "$file"
        ((count++))
    done < <(find . -name "*.pyc" -not -path "./.git/*")

    print_status "Removed $count cache files/directories"
}

remove_pycache

# 3. Check for large files
echo ""
echo "📊 Checking for Large Files (>10MB)..."
echo "--------------------------------"

check_large_files() {
    local found=0
    while IFS= read -r file; do
        size=$(du -h "$file" | cut -f1)
        print_warning "Large file: $file ($size)"
        ((found++))
    done < <(find . -size +10M -type f -not -path "./.git/*" 2>/dev/null)

    if [ $found -eq 0 ]; then
        print_status "No large files found"
    else
        echo "   Consider moving $found large file(s) to Git LFS or .gitignore"
    fi
}

check_large_files

# 4. Check for missing documentation
echo ""
echo "📚 Checking Documentation Status..."
echo "--------------------------------"

check_documentation() {
    for dir in cloud_app_demo computer_vision_demo nlp_demo rag_demo ucberkeley-capstone; do
        if [ -d "$dir" ]; then
            if [ -f "$dir/README.md" ]; then
                lines=$(wc -l < "$dir/README.md")
                if [ "$lines" -gt 10 ]; then
                    print_status "$dir: README.md exists ($lines lines)"
                else
                    print_warning "$dir: README.md exists but is minimal ($lines lines)"
                fi
            else
                print_error "$dir: Missing README.md"
            fi

            if [ -f "$dir/requirements.txt" ] || [ -f "$dir/pyproject.toml" ] || [ -f "$dir/environment.yml" ]; then
                print_status "$dir: Has dependency file"
            else
                print_error "$dir: Missing requirements.txt"
            fi
        fi
    done
}

check_documentation

# 5. Create basic structure for projects missing READMEs
echo ""
echo "🏗️  Creating Basic Structure for Undocumented Projects..."
echo "--------------------------------------------------------"

create_basic_structure() {
    for dir in computer_vision_demo nlp_demo rag_demo; do
        if [ -d "$dir" ] && [ ! -f "$dir/README.md" ]; then
            cat > "$dir/README.md" << 'EOF'
# Project Title

## Overview
[Brief description of the project]

## Setup
```bash
pip install -r requirements.txt
```

## Usage
[How to run the project]

## Results
[Key findings or outputs]

## Technologies Used
- Python 3.9+
- [List key libraries]

## Future Improvements
- [ ] Add comprehensive documentation
- [ ] Improve code modularity
- [ ] Add unit tests
EOF
            print_status "Created basic README.md for $dir"
        fi

        if [ -d "$dir" ] && [ ! -f "$dir/requirements.txt" ]; then
            # Create a basic requirements.txt
            echo "# Auto-generated - please review and update" > "$dir/requirements.txt"
            echo "jupyter>=1.0.0" >> "$dir/requirements.txt"
            echo "numpy>=1.21.0" >> "$dir/requirements.txt"
            echo "pandas>=1.3.0" >> "$dir/requirements.txt"
            echo "matplotlib>=3.4.0" >> "$dir/requirements.txt"
            print_status "Created basic requirements.txt for $dir (needs review)"
        fi
    done
}

create_basic_structure

# 6. Git status check
echo ""
echo "📝 Git Repository Status..."
echo "-------------------------"

if [ -d ".git" ]; then
    modified=$(git status --porcelain | wc -l)
    if [ "$modified" -gt 0 ]; then
        print_warning "There are $modified uncommitted changes"
        echo ""
        echo "   To commit cleanup changes:"
        echo "   git add ."
        echo "   git commit -m 'chore: Clean notebooks and add basic documentation structure'"
    else
        print_status "Working directory clean"
    fi
else
    print_error "Not a git repository"
fi

# 7. Summary and next steps
echo ""
echo "=============================================="
echo "📋 CLEANUP SUMMARY"
echo "=============================================="
echo ""
echo "Automated cleanup complete! Next manual steps:"
echo ""
echo "1. Review and update the auto-generated README.md files"
echo "2. Update requirements.txt with actual dependencies"
echo "3. Review the PROJECT_IMPROVEMENT_PLAN.md for detailed tasks"
echo "4. Consider creating a main repository README.md"
echo "5. Add large files to .gitignore if found"
echo ""
echo "Priority Projects Needing Attention:"

for dir in computer_vision_demo nlp_demo rag_demo; do
    if [ -d "$dir" ]; then
        echo "  - $dir: Add comprehensive documentation and clean code structure"
    fi
done

echo ""
echo "✨ Done! Check PROJECT_IMPROVEMENT_PLAN.md for the full improvement roadmap."