#!/bin/bash
set -x
cd /home/user/maldives
python3 -c "import lib; s=lib.run_queue(); lib.print_progress(); lib.run_log('B+', f'destination-dining pass: {s}')"
python3 phase_f.py
python3 build_outputs.py
python3 final_report.py
python3 qa.py
git add -A && git commit -q -m "Destination-dining pass: reclassified library, new pages, fact packs, outputs

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01HuKfdgdkSVamDCtYV6eLkT" && git push -q -u origin claude/gallant-johnson-ktui6q
echo DINING_DONE
