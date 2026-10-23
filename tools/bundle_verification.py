#!/usr/bin/env python3
"""Bundle explicitly referenced replay/PoC files, or check a relocated bundle.

This copies evidence; it does not execute inputs, validate vulnerabilities, or
upgrade admission decisions. Source task and canonical case bytes stay frozen.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def directory_digest(directory):
    digest = hashlib.sha256()
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'PoC contains a symbolic link: {path}')
        if path.is_file():
            digest.update(path.relative_to(directory).as_posix().encode())
            digest.update(b'\0')
            digest.update(path.read_bytes())
            digest.update(b'\0')
    return digest.hexdigest()


def bundle(source_release, root):
    roster = read(root / 'data/roster.json')
    source_roster = read(source_release / 'roster.json')
    originals = {r['project'] + '/' + str(r['bug_id']): r for r in source_roster['entries']}
    output = root / 'verification'
    cases = []

    for entry in roster['entries']:
        key = entry['project'] + '/' + str(entry['bug_id'])
        original = originals[key]
        hashes = {kind: entry[kind]['sha256'] for kind in ('buggy', 'benign')}
        if any(hashes[kind] != original[kind]['sha256'] for kind in hashes):
            raise ValueError(f'Task identity changed before evidence export: {key}')
        relative_case = Path(original['season']) / 'data/verification/projects' / entry['project'] / 'cases' / str(entry['bug_id']) / 'case.json'
        source_case = source_release / relative_case
        canonical = read(source_case)
        result = {'key': key, 'admission': entry['source'], 'task_hashes': hashes,
                  'canonical_record_source': str(source_case), 'canonical_record_sha256': sha(source_case),
                  'canonical_record_path': (Path('data') / relative_case).as_posix(),
                  'assets': [], 'warnings': [], 'poc_path': None,
                  'historical_replay_reference': None, 'fresh_replay_performed': False}
        destination = output / 'projects' / entry['project'] / 'cases' / str(entry['bug_id'])

        def copy(source, target, purpose):
            if source.is_symlink() or not source.is_file():
                raise ValueError(f'Expected regular evidence file: {source}')
            if source.stat().st_size > 20 * 1024 * 1024:
                raise ValueError(f'Evidence file exceeds 20 MiB export bound: {source}')
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and sha(target) != sha(source):
                raise ValueError(f'Refusing to replace changed evidence: {target}')
            shutil.copy2(source, target)
            result['assets'].append({'source_path': str(source), 'path': target.relative_to(root).as_posix(),
                                     'sha256': sha(target), 'bytes': target.stat().st_size, 'purpose': purpose})

        evidence = canonical.get('evidence') or {}
        replay_path = evidence.get('replay')
        if not replay_path:
            result['warnings'].append('Canonical record has no external replay-file reference; preserved admission evidence is in data/.')
        elif not Path(replay_path).is_file():
            result['warnings'].append('Referenced replay file unavailable during export.')
        else:
            source_replay = Path(replay_path)
            replay = read(source_replay)
            result['historical_replay_reference'] = replay_path
            copy(source_replay, destination / 'replay.json', 'historical replay')
            for kind, path in [('report', evidence.get('report')),
                               ('agent_verdict', (evidence.get('agent') or {}).get('verdict'))]:
                if path and Path(path).is_file():
                    copy(Path(path), destination / (kind + ('.md' if kind == 'report' else '.json')), kind)
            info = replay.get('poc') or {}
            source_poc = Path(info['poc_dir']) if info.get('poc_dir') else None
            if source_poc and source_poc.is_dir() and not source_poc.is_symlink():
                target_poc = output / 'pocs' / entry['project'] / str(entry['bug_id'])
                for path in sorted(source_poc.rglob('*')):
                    if path.is_symlink():
                        raise ValueError(f'Cannot bundle PoC symlink: {path}')
                    if path.is_file():
                        copy(path, target_poc / path.relative_to(source_poc), 'reproducer asset')
                result['poc_path'] = target_poc.relative_to(root).as_posix()
                result['poc_directory_sha256'] = directory_digest(target_poc)
                result['has_run_sh'] = (target_poc / 'run.sh').is_file()
                result['input_name'] = info.get('input_name')
                executions = replay.get('agent_executions') or (evidence.get('agent') or {}).get('executions') or {}
                expected = {v.get('poc_sha256') for v in executions.values() if isinstance(v, dict) and v.get('poc_sha256')}
                result['recorded_agent_poc_digests'] = sorted(expected)
                result['matches_recorded_agent_poc_digest'] = (expected == {result['poc_directory_sha256']}) if expected else None
                if expected and expected != {result['poc_directory_sha256']}:
                    result['warnings'].append('Available PoC bytes do not match every saved agent-execution digest; not certified as the executed input.')
                result['recorded_commands'] = sorted({v['command'] for v in executions.values() if isinstance(v, dict) and v.get('command')})
            else:
                result['warnings'].append('Referenced PoC directory unavailable during export.')
        cases.append(result)

    summary = {'cases': len(cases), 'replay_files_bundled': sum(bool(c['historical_replay_reference']) for c in cases),
               'poc_directories_bundled': sum(bool(c['poc_path']) for c in cases),
               'agent_digest_matches': sum(c.get('matches_recorded_agent_poc_digest') is True for c in cases),
               'agent_digest_mismatches': sum(c.get('matches_recorded_agent_poc_digest') is False for c in cases),
               'files': sum(len(c['assets']) for c in cases), 'bytes': sum(a['bytes'] for c in cases for a in c['assets']),
               'fresh_replay_performed': False}
    manifest = {'schema_version': 1, 'description': 'Partial portable archive of explicitly referenced historical verification assets; coverage is not a new verification verdict.',
                'source_roster_sha256': sha(source_release / 'roster.json'), 'summary': summary, 'cases': cases}
    write(output / 'manifest.json', manifest)
    return summary


def check(root):
    manifest = read(root / 'verification/manifest.json')
    entries = {e['project'] + '/' + str(e['bug_id']): e for e in read(root / 'data/roster.json')['entries']}
    errors = []
    cases = manifest['cases']
    counts = collections.Counter(c['key'] for c in cases)
    if set(counts) != set(entries) or any(count != 1 for count in counts.values()):
        errors.append('Verification index must cover every retained case exactly once.')
    paths = set()
    for case in cases:
        entry = entries.get(case['key'])
        if entry and case['task_hashes'] != {k: entry[k]['sha256'] for k in ('buggy', 'benign')}:
            errors.append(f'Task binding mismatch: {case["key"]}')
        record = root / case['canonical_record_path']
        if not record.is_file() or sha(record) != case['canonical_record_sha256']:
            errors.append(f'Canonical record changed/missing: {case["key"]}')
        for asset in case['assets']:
            path = root / asset['path']
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
                errors.append(f'Missing/unsafe asset: {asset["path"]}')
            elif sha(path) != asset['sha256']:
                errors.append(f'Changed asset: {asset["path"]}')
            if asset['path'] in paths:
                errors.append(f'Duplicate asset: {asset["path"]}')
            paths.add(asset['path'])
        if case.get('poc_path'):
            directory = root / case['poc_path']
            if not directory.resolve().is_relative_to(root.resolve()):
                errors.append(f'Unsafe PoC root: {case["key"]}')
            elif directory_digest(directory) != case['poc_directory_sha256']:
                errors.append(f'PoC directory changed: {case["key"]}')
    observed = {p.relative_to(root).as_posix() for folder in ['verification/projects', 'verification/pocs']
                for p in (root / folder).rglob('*') if p.is_file()}
    if observed != paths:
        errors.append('Unindexed or missing verification assets.')
    return {'cases': len(cases), 'files_checked': len(paths), 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--source-release', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.check:
        result = check(root)
    elif args.source_release:
        result = bundle(args.source_release.resolve(), root)
    else:
        parser.error('Specify --check or --source-release.')
    print(json.dumps(result, indent=2))
    return bool(result.get('errors'))


if __name__ == '__main__':
    sys.exit(main())
