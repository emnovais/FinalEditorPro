"""Explicit CLI; never launches Final Cut Pro or installs software."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from .core import export_xml, json_bytes, local_media, metadata, plan, sha256


def probe(path, executable):
    p = local_media(path)
    if not Path(executable).is_absolute():
        raise ValueError('ffprobe path must be absolute')
    tool = Path(executable).resolve(strict=True)
    if not tool.is_file() or not os.access(tool, os.X_OK):
        raise ValueError('ffprobe must be an approved executable')
    # No shell, no network protocols, no automatic install or PATH discovery.
    result = subprocess.run(
        [str(tool), '-v', 'error', '-protocol_whitelist', 'file',
         '-show_streams', '-show_format', '-of', 'json', str(p)],
        check=True, capture_output=True, timeout=120)
    return json.loads(result.stdout)


def journal(folder, action, **details):
    with (folder / 'operations.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(dict(time=datetime.now(timezone.utc).isoformat(),
                               action=action, **details)) + '\n')
        f.flush()
        os.fsync(f.fileno())


def publish(project, output):
    """New run directory only. Failed runs retain their diagnostic journal."""
    xml = export_xml(project)
    out = Path(output).expanduser().absolute()
    if any(x.lower().endswith(('.fcpbundle', '.fcplibrary')) for x in out.resolve().parts):
        raise ValueError('Cannot write inside a Final Cut library')
    if not out.parent.is_dir() or out.parent.resolve() != out.parent:
        raise ValueError('Output parent must exist and have no symlink components')
    out.mkdir(mode=0o700)  # exclusive: never reuse or overwrite an existing run
    journal(out, 'begin', sources=[dict(path=m['path'], sha256=m['sha256']) for m in project['media']])
    try:
        for name, data in [('project.json', json_bytes(project)), ('timeline.fcpxml', xml)]:
            with (out / name).open('xb') as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            journal(out, 'created', file=name, sha256=sha256(out / name))
        # Rehash after publication too: never certify a changed source.
        from .core import validate
        validate(project)
        journal(out, 'complete')
    except Exception as exc:
        journal(out, 'failed', error=type(exc).__name__)
        raise
    return out


def undo(folder):
    """Park only known artifacts whose hashes still match; preserve the ledger."""
    if Path(folder).is_symlink():
        raise ValueError('Symlink run forbidden')
    out = Path(folder).resolve(strict=True)
    if any(x.lower().endswith(('.fcpbundle', '.fcplibrary')) for x in out.parts):
        raise ValueError('Final Cut libraries forbidden')
    if out.is_symlink() or (out / 'operations.jsonl').is_symlink():
        raise ValueError('Symlink journal forbidden')
    rows = [json.loads(x) for x in (out / 'operations.jsonl').read_text().splitlines()]
    created = [r for r in rows if r['action'] == 'created']
    for r in created:
        if r['file'] not in ('project.json', 'timeline.fcpxml'):
            raise ValueError('Unknown artifact in journal')
        p = out / r['file']
        if p.is_symlink() or not p.is_file() or sha256(p) != r['sha256']:
            raise ValueError('Artifact missing/modified; refusing undo')
    parked = out / 'undone'
    parked.mkdir(mode=0o700)
    for r in created:
        (out / r['file']).rename(parked / r['file'])
        journal(out, 'parked', file=r['file'])
    journal(out, 'undo_complete')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    build = sub.add_parser('build')
    build.add_argument('media', nargs='+')
    build.add_argument('--ffprobe', required=True, help='Absolute path to approved ffprobe')
    build.add_argument('--output', required=True, help='New directory in an existing parent')
    build.add_argument('--name', default='AI Rough Cut')
    edit = sub.add_parser('export')
    edit.add_argument('project')
    edit.add_argument('--output', required=True)
    revert = sub.add_parser('undo')
    revert.add_argument('run')
    args = parser.parse_args()
    if args.command == 'undo':
        undo(args.run)
    elif args.command == 'export':
        publish(json.loads(Path(args.project).read_text()), args.output)
    else:
        # Fingerprint before and after probing, not just after metadata extraction.
        media = []
        for path in args.media:
            original = sha256(local_media(path))
            item = metadata(path, probe(path, args.ffprobe))
            if original != item['sha256']:
                raise ValueError('Media changed during probe')
            media.append(item)
        publish(plan(media, args.name), args.output)


if __name__ == '__main__':
    main()
