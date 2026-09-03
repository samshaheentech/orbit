#!/bin/bash
# Run once after cloning: bash ~/git/orbit/install.sh
set -e

ORBIT_HOME="$(cd "$(dirname "$0")" && pwd)"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
RUNNER_LABEL="com.sam.orbit-runner"
SERVER_LABEL="com.sam.orbit-server"

export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "==> Checking prerequisites..."
command -v claude >/dev/null 2>&1 || { echo "ERROR: claude not found. Install Claude Code and run 'claude login' first."; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found. Install via Homebrew: brew install python3"; exit 1; }
echo "    claude: $(claude --version 2>/dev/null | head -1)"
echo "    python3: $(python3 --version)"

echo "==> Creating directories..."
mkdir -p "$ORBIT_HOME"/{queue,running,done,blocked,reports,logs,state,worktrees,system,config/lanes,briefs/data} "$LAUNCHD_DIR"

echo "==> Making scripts executable..."
chmod +x "$ORBIT_HOME/run.sh" "$ORBIT_HOME/server.py" "$ORBIT_HOME/install.sh"

echo "==> Installing launchd jobs..."
for LABEL in "$RUNNER_LABEL" "$SERVER_LABEL"; do
  SRC="$ORBIT_HOME/launchd/$LABEL.plist"
  DST="$LAUNCHD_DIR/$LABEL.plist"
  sed "s|__ORBIT__|$ORBIT_HOME|g" "$SRC" > "$DST"
  launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$DST" 2>/dev/null || launchctl load "$DST"
  echo "    $LABEL: loaded"
done

echo "==> Verifying server..."
sleep 2
if curl -sf http://localhost:4242/api/health >/dev/null; then
  echo "    Server: running at http://localhost:4242"
else
  echo "    Server: not responding yet — check $ORBIT_HOME/logs/server.err"
fi

cat <<EOF

Done. Orbit is installed.

  Tasks          $ORBIT_HOME/queue/         copy _TEMPLATE.md → 010-taskname.md
  Orbit          http://localhost:4242       opens in any browser
  Logs           $ORBIT_HOME/logs/
  Config         $ORBIT_HOME/config/user.md

Test a fire now:
  bash $ORBIT_HOME/run.sh

Watch a run live:
  tail -f $ORBIT_HOME/logs/*.err

Pause the schedule:
  launchctl bootout gui/$(id -u)/$RUNNER_LABEL

Resume the schedule:
  launchctl bootstrap gui/$(id -u) $LAUNCHD_DIR/$RUNNER_LABEL.plist

Keep Mac awake overnight (on power):
  System Settings → Battery → Options → prevent sleep when display is off
  Or: sudo pmset -c sleep 0

EOF
