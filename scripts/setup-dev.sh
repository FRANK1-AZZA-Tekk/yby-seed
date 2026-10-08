#!/usr/bin/env bash
set -e

echo "🚀 Setting up YBY SEED development environment..."

# Install Python dependencies
if [ -f "tests/requirements.txt" ]; then
    echo "📦 Installing Python dependencies..."
    pip install --no-cache-dir -r tests/requirements.txt
fi

# Install PlatformIO for ESP32 development
if ! command -v pio &> /dev/null; then
    echo "📦 Installing PlatformIO..."
    pip install --no-cache-dir platformio
fi

# Install MkDocs for documentation
if ! command -v mkdocs &> /dev/null; then
    echo "📚 Installing MkDocs..."
    pip install --no-cache-dir mkdocs mkdocs-material
fi

# Pull Ollama model
if command -v docker &> /dev/null; then
    echo "🤖 Pulling Ollama model..."
    docker-compose exec -T ollama ollama pull qwen2.5-coder:3b-instruct-q4_K_M || true
fi

echo "✅ Development environment ready!"
echo ""
echo "📌 Next steps:"
echo "   1. Edit .env with your API keys"
echo "   2. Run: make test"
echo "   3. Access Node-RED: http://localhost:1880"
echo "   4. Read docs: http://localhost:8000 (after 'mkdocs serve')"
