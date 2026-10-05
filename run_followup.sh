#!/bin/bash
set -x
cd /home/user/maldives
python3 reprocess.py purge
python3 reprocess.py
python3 reconcile.py
python3 phase_b.py group
python3 dam_dash.py
python3 phase_b.py dam
python3 retry_sites.py
python3 phase_c.py
python3 phase_d.py cc wayback run all
python3 phase_e.py
python3 phase_f.py
python3 build_outputs.py
python3 qa.py
git add -A && git commit -q -m "Phases D-G, QA

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01HuKfdgdkSVamDCtYV6eLkT" && git push -q -u origin claude/gallant-johnson-ktui6q
echo FOLLOWUP_DONE
