#!/bin/bash
set -x
cd /home/user/maldives
python3 phase_d.py cc wayback run all
python3 phase_f.py
python3 build_outputs.py
python3 qa.py
git add -A && git commit -q -m "Phase D archives; final fact packs, outputs, QA

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01HuKfdgdkSVamDCtYV6eLkT" && git push -q -u origin claude/gallant-johnson-ktui6q
echo FINAL_DONE
