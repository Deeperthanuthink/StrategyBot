#!/bin/bash
# Setup script for CI/CD and code quality tools

echo "🚀 Setting up CI/CD and code quality tools..."

# Install development dependencies
echo "📦 Installing development dependencies..."
pip install --upgrade pip
pip install black flake8 pylint bandit safety pytest pytest-cov pre-commit

# Format code with Black
echo "✨ Formatting code with Black..."
black .

# Setup pre-commit hooks (optional)
echo "🪝 Setting up pre-commit hooks..."
pre-commit install

# Run checks
echo "🔍 Running code quality checks..."
echo ""
echo "1. Black formatting check:"
black --check .
echo ""

echo "2. Flake8 linting:"
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
echo ""

echo "3. Bandit security scan:"
bandit -r src/ -ll
echo ""

echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Review any warnings or errors above"
echo "2. Commit your changes: git add . && git commit -m 'Setup CI/CD pipeline'"
echo "3. Push to GitHub: git push origin main"
echo "4. Check GitHub Actions at: https://github.com/Deeperthanuthink/tradieralpaca/actions"
