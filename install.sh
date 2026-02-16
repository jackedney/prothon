#!/bin/sh
set -e

WRAPPER_DIR="$HOME/.local/bin"
WRAPPER="$WRAPPER_DIR/prothon"

mkdir -p "$WRAPPER_DIR"

cat > "$WRAPPER" << 'EOF'
#!/bin/sh
exec uvx --from "git+https://github.com/jackedney/prothon" prothon "$@"
EOF

chmod +x "$WRAPPER"

# Check if ~/.local/bin is in PATH
case ":$PATH:" in
  *":$WRAPPER_DIR:"*) ;;
  *)
    echo "NOTE: $WRAPPER_DIR is not in your PATH."
    echo "Add this to your shell profile:"
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

echo "Installed prothon to $WRAPPER"
