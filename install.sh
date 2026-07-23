#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_HOME="${HOME}/.local/share/hebrew-fuzzy-tui"
BIN_HOME="${HOME}/.local/bin"

mkdir -p "$APP_HOME" "$BIN_HOME"

if [ ! -d "$APP_HOME/venv" ]; then
  python3 -m venv "$APP_HOME/venv"
fi

"$APP_HOME/venv/bin/python" -m pip install --upgrade pip
"$APP_HOME/venv/bin/pip" install "textual>=0.70" "rapidfuzz>=3.0"

# Preserve the user's working database on upgrades.
if [ ! -f "$APP_HOME/hebrew.db" ]; then
  cp "$SOURCE_DIR/hebrew.db" "$APP_HOME/hebrew.db"
fi

rm -f "$APP_HOME/hebrew_tui.py" "$APP_HOME/import_tanakh.py"
cp "$SOURCE_DIR/hebrew_tui.py" "$SOURCE_DIR/import_tanakh.py" "$APP_HOME/"

cat > "$BIN_HOME/hebrew-fuzzy" <<EOF
#!/usr/bin/env bash
exec "$APP_HOME/venv/bin/python" "$APP_HOME/hebrew_tui.py" "\$@"
EOF

cat > "$BIN_HOME/hebrew-fuzzy-import-tanakh" <<EOF
#!/usr/bin/env bash
exec "$APP_HOME/venv/bin/python" "$APP_HOME/import_tanakh.py" "\$@"
EOF

chmod +x "$BIN_HOME/hebrew-fuzzy" "$BIN_HOME/hebrew-fuzzy-import-tanakh"

echo
echo "Hebrew Fuzzy Study v10 installed."
echo "Existing notes/database were preserved if already present."
echo
echo "Import/refresh Tanakh:"
echo "  hebrew-fuzzy-import-tanakh"
echo
echo "Launch:"
echo "  hebrew-fuzzy"
