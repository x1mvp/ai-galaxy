#!/bin/bash
set -e

echo "🚀 Setting up x1mvp Portfolio Environment..."

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ $(echo "$python_version >= 3.9" | bc -l) -eq 0 ]]; then
    echo "❌ Python 3.9+ required, found $python_version"
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip setuptools wheel

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Install development dependencies
echo "🛠️ Installing development tools..."
pip install -e ".[dev,testing,monitoring]"

# Setup pre-commit hooks
echo "🔧 Setting up pre-commit hooks..."
pre-commit install

# Create environment file
if [ ! -f .env ]; then
    echo "📝 Creating .env file..."
    cp .env.example .env
fi

# Setup database
echo "🗄️ Setting up database..."
alembic upgrade head

echo "✅ Setup complete! Run 'source venv/bin/activate' to start."
