#!/bin/bash

# =============================================================================
# init.sh - AI Daily News Bot 初始化脚本
# =============================================================================
# 在每个开发会话开始时运行此脚本，确保环境正确配置
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Initializing AI Daily News Bot...${NC}"

# 检查 Python 版本
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "Found: $PYTHON_VERSION"
else
    echo "Error: Python3 not found. Please install Python 3.11+"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "Activating virtual environment..."
source venv/bin/activate

# 安装依赖
if [ -f "requirements.txt" ]; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
else
    echo "Warning: requirements.txt not found. Skipping dependency installation."
fi

# 创建必要的目录
echo "Creating necessary directories..."
mkdir -p data
mkdir -p output/reports
mkdir -p logs

# 检查 .env 文件
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Warning: .env file not found. Please copy .env.example to .env and configure your API keys."
    else
        echo "Warning: No .env or .env.example found."
    fi
fi

# 初始化数据库（如果数据库不存在）
if [ ! -f "data/news.db" ]; then
    echo "Database not found. Run 'python scripts/init_db.py' to initialize."
fi

echo ""
echo -e "${GREEN}✓ Initialization complete!${NC}"
echo ""
echo "Available commands:"
echo "  python scripts/run_collector.py  - Run information collection"
echo "  python scripts/run_processor.py  - Run AI processing"
echo "  python scripts/run_generator.py  - Generate daily report"
echo "  python scripts/init_db.py        - Initialize database"
echo "  uvicorn app.main:app --reload    - Start API server"
echo ""
