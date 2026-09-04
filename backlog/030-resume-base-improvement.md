---
lane: career
exec: lanes/career/resume_loop.py --force-base
model: fable-5-1
weight: heavy
dir: ~/git/orbit
---
# Resume: base improvement run

## What this does
Runs the blind resume loop against the champion with no posting: the improver proposes a general challenger, two graders score it, and it surfaces only if both agree it beats v33. One-shot; the weekly base run inside `130` continues on its own.
