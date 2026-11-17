"""Park only checksummed generated artifacts; never source media."""
import json,re
from ave.core import sha256
from ave.cli import journal
from ..analysis.pipeline import within_project


def undo(output):
    out=within_project(output)
    ledger=out/'operations.jsonl'
    if ledger.is_symlink():raise ValueError('Symlink ledger forbidden')
    rows=[json.loads(l) for l in ledger.read_text().splitlines()]
    if not any(r['action'] in ('editing_started','preview_complete') for r in rows):raise ValueError('Not an editing/preview run')
    records=[r for r in rows if r['action']=='created']
    # Preview final is also registered through preview_complete.
    records += [r for r in rows if r['action']=='preview_complete' and 'sha256' in r and r.get('file')]
    names=[r['file'] for r in records]
    if len(names)!=len(set(names)):raise ValueError('Duplicate artifact entries')
    allowed={'edl.json','timeline.fcpxml','comparison.json','review.html','validation.json','preview.mp4'}
    for row in records:
        name=row['file']
        if name not in allowed and not re.fullmatch(r'clip-\d{3}\.mov',name):raise ValueError('Unknown artifact')
        p=out/name
        if p.is_symlink() or sha256(p)!=row['sha256']:raise ValueError('Changed artifact; refusing undo')
    parked=out/'undone';parked.mkdir(mode=0o700)
    for row in records:(out/row['file']).rename(parked/row['file'])
    journal(out,'editing_undo_complete')
