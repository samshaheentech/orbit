#!/bin/bash
# Run once from the agent folder: bash ~/agent/install.sh
set -e

AGENT_HOME="$(cd "$(dirname "$0")" && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
RUNNER_LABEL="com.sam.agent-runner"
SERVER_LABEL="com.sam.agent-server"

export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "==> Checking prerequisites..."
command -v claude >/dev/null 2>&1 || { echo "ERROR: claude not found. Install Claude Code and run 'claude login' first."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found. Install via Homebrew: brew install python3"; exit 1; }
echo "    claude: $(claude --version 2>/dev/null | head -1)"
echo "    python3: $(python3 --version)"

echo "==> Creating directories..."
mkdir -p "$AGENT_HOME"/{queue,running,done,blocked,reports,logs,state,worktrees,system,config/lanes,briefs/data} "$LAUNCHD_DIR"

echo "==> Making scripts executable..."
chmod +x "$AGENT_HOME/run.sh" "$AGENT_HOME/server.py" "$AGENT_HOME/install.sh"

echo "==> Installing launchd jobs..."
for LABEL in "$RUNNER_LABEL" "$SERVER_LABEL"; do
  SRC="$AGENT_HOME/launchd/$LABEL.plist"
  DST="$LAUNCHD_DIR/$LABEL.plist"
  sed "s|__HOME__|$HOME|g" "$SRC" > "$DST"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$DST" 2>/dev/null || launchctl load "$DST"
  echo "    $LABEL: loaded"
done

echo "==> Verifying server..."
sleep 2
if curl -sf http://localhost:4242/api/health >/dev/null; then
  echo "    Server: running at http://localhost:4242"
else
  echo "    Server: not responding yet — check $AGENT_HOME/logs/server.err"
fi

cat <<EOF

Done. Your agent is installed.

  Tasks          $AGENT_HOME/queue/         copy _TEMPLATE.md → 010-taskname.md
  Morning brief  http://localhost:4242       opens in any browser
  Logs           $AGENT_HOME/logs/
  Config         $AGENT_HOME/config/user.md

Test a fire now:
  bash $AGENT_HOME/run.sh

Watch a run live:
  tail -f $AGENT_HOME/logs/*.err

Pause the schedule:
  launchctl bootout gui/$(id -u)/$RUNNER_LABEL

Resume the schedule:
  launchctl bootstrap gui/$(id -u) $LAUNCHD_DIR/$RUNNER_LABEL.plist

Keep Mac awake overnight (on power):
  System Settings → Battery → Options → prevent sleep when display is off
  Or: sudo pmset -c sleep 0

EOF
