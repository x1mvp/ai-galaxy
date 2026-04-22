#!/bin/bash
set -e

echo "🔄 Updating dependencies..."

# Create backup
cp requirements.txt requirements.txt.backup

# Update all packages
pip-review --local --interactive

# Generate new requirements
pip freeze > requirements-new.txt

# Sort and format
python -c "
import re
with open('requirements-new.txt', 'r') as f:
    packages = f.read().splitlines()

# Filter out development packages
filtered = [p for p in packages if not any(
    p.startswith(prefix) for prefix in ['pytest', 'black', 'isort', 'ruff', 'mypy']
)]

# Sort by package name
filtered.sort()

with open('requirements.txt', 'w') as f:
    f.write('\n'.join(filtered))
"

echo "✅ Dependencies updated!"
echo "📋 Review requirements.txt and commit changes"
