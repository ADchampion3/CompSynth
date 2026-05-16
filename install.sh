#!/usr/bin/env bash
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${CYAN}ℹ${RESET} %s\n" "$*"; }
ok()    { printf "${GREEN}✔${RESET} %s\n" "$*"; }
warn()  { printf "${YELLOW}⚠${RESET} %s\n" "$*"; }
error() { printf "${RED}✖${RESET} %s\n" "$*"; }

# ── Resolve script directory ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Check uv ────────────────────────────────────────────────────────────
UV=""

resolve_uv() {
    if command -v uv &>/dev/null; then
        UV="$(command -v uv)"
        return 0
    fi

    # Check common locations
    local candidates=(
        "$HOME/.local/bin/uv"
        "$HOME/.cargo/bin/uv"
        "/usr/local/bin/uv"
    )
    for c in "${candidates[@]}"; do
        if [[ -x "$c" ]]; then
            UV="$c"
            return 0
        fi
    done
    return 1
}

if resolve_uv; then
    ok "Found uv: $UV"
else
    warn "uv not found in PATH."
    echo ""
    echo "  ${BOLD}1)${RESET} Install uv automatically (recommended)"
    echo "  ${BOLD}2)${RESET} Provide the path to uv manually"
    echo "  ${BOLD}3)${RESET} Abort"
    echo ""
    while true; do
        read -rp "Choose [1/2/3]: " choice
        case "$choice" in
            1)
                info "Installing uv..."
                curl -LsSf https://astral.sh/uv/install.sh | sh
                # Re-check after install
                if resolve_uv; then
                    ok "uv installed: $UV"
                else
                    error "uv still not found after installation. Please restart your shell and try again."
                    exit 1
                fi
                break
                ;;
            2)
                while true; do
                    read -rp "Enter path to uv binary: " uv_path
                    uv_path="${uv_path/#\~/$HOME}"
                    if [[ -x "$uv_path" ]]; then
                        UV="$uv_path"
                        ok "Using uv at: $UV"
                        break 2
                    else
                        error "Not an executable file: $uv_path"
                    fi
                done
                ;;
            3)
                error "Aborted."
                exit 1
                ;;
            *)
                warn "Invalid choice. Enter 1, 2, or 3."
                ;;
        esac
    done
fi

# ── uv sync ─────────────────────────────────────────────────────────────
info "Installing Python dependencies with uv sync..."
"$UV" sync
ok "Python dependencies installed."

# ── .env ────────────────────────────────────────────────────────────────
if [[ ! -f .env ]] && [[ -f .env.example ]]; then
    cp .env.example .env
    ok "Created .env from .env.example (edit it to fill in your API keys)"
else
    info ".env already exists, skipping."
fi

# ── subscriptions.yaml ─────────────────────────────────────────────────
if [[ ! -f subscriptions.yaml ]] && [[ -f subscriptions.example.yaml ]]; then
    cp subscriptions.example.yaml subscriptions.yaml
    ok "Created subscriptions.yaml from subscriptions.example.yaml"
else
    if [[ ! -f subscriptions.yaml ]]; then
        warn "subscriptions.yaml not found. You can create one later."
    else
        info "subscriptions.yaml already exists, skipping."
    fi
fi

# ── Data directories ───────────────────────────────────────────────────
mkdir -p data logs output
ok "Created data/, logs/, output/ directories."

# ── Verify ──────────────────────────────────────────────────────────────
info "Verifying installation..."
if "$UV" run compsynth --version &>/dev/null; then
    VERSION="$("$UV" run compsynth --version 2>/dev/null || echo "unknown")"
    ok "compsynth $VERSION installed successfully."
else
    warn "compsynth --version check failed. Try running 'uv run compsynth --version' manually."
fi

# ── Frontend (optional) ────────────────────────────────────────────────
echo ""
read -rp "Install frontend dependencies? [Y/n]: " fe_choice
case "$fe_choice" in
    n|N|no|No|NO)
        info "Skipping frontend. You can install later with: cd frontend && npm install"
        ;;
    *)
        if [[ -f frontend/package.json ]]; then
            if command -v npm &>/dev/null; then
                info "Installing frontend dependencies..."
                (cd frontend && npm install)
                ok "Frontend dependencies installed."
            else
                warn "npm not found. Install Node.js 18+ to set up the frontend."
            fi
        else
            warn "frontend/package.json not found, skipping."
        fi
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
ok "Setup complete!"
echo ""
echo "  Quick start:"
echo "    ${BOLD}compsynth serve${RESET}          # Start API server"
echo "    ${BOLD}cd frontend && npm run dev${RESET}  # Start frontend"
echo ""
echo "  First time? Run:"
echo "    ${BOLD}compsynth doctor${RESET}           # Check your setup"
echo "    ${BOLD}compsynth status${RESET}            # System health"
echo ""
echo "  Edit ${BOLD}.env${RESET} to configure LLM API keys."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
