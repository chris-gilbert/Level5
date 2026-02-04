#!/bin/bash
set -e

echo "🛡️ Level5: Initializing Sovereign Environment..."

# 1. Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# 2. Install Requirements & Resolve Conflicts
echo "pip: Installing and resolving dependencies..."
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt || echo "⚠️ Ignoring initial resolution conflicts (expected)..."

# Force-upgrade to latest stable (overriding restrictive library pins)
echo "pip: Forcing latest stable versions (Mandate 3)..."
./venv/bin/pip install --upgrade --no-deps \
    solana==0.36.11 \
    solders==0.27.1 \
    starlette==0.52.1 \
    toolz==1.1.0 \
    construct-typing==0.7.0 \
    construct==2.10.70 \
    websockets==16.0

# 3. Apply Professional Patches
# anchorpy 0.21.0 has a conflict with pytest-xprocess 1.0.2 layout
echo "🩹 Applying infrastructure patches..."
# Find the actual path dynamically in case of OS differences
PATCH_TARGET=$(./venv/bin/python3 -c "import anchorpy; print(anchorpy.__path__[0] + '/pytest_plugin.py')")
if [ -f "$PATCH_TARGET" ]; then
    sed -i 's/from pytest_xprocess import getrootdir/from xprocess.pytest_xprocess import getrootdir/g' "$PATCH_TARGET"
    echo "   - anchorpy: getrootdir patch applied to $PATCH_TARGET"
fi

# 4. Initialize Local Database
echo "🗄️ Initializing SQLite (WAL Mode)..."
./venv/bin/python3 -c "from services.proxy import database; database.init_db()"

echo "🚀 Level5 is ready for action."
echo "   Run: ./venv/bin/python3 services/proxy/main.py"
