#!/usr/bin/env python3
"""Export the reviewed current-274 snapshot without changing frozen task/evidence bytes.

The three explicit source inputs are needed only by maintainers rebuilding the
release. Running or validating the release requires none of these source paths.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

EXCLUDED = frozenset({
    'firefox/1950061', 'ffmpeg/268d0b6527cb', 'ffmpeg/bd75fad85f37',
    'ffmpeg/c14b837dedad', 'ffmpeg/db7ff135744d', 'openssl/GH-26346',
    'curl/GH-19377', 'curl/GH-19269',
})
HELD = frozenset({'ffmpeg/TESTCASE-4015241140b49b26'})
RELEASE = 'secprbench-265-20261010'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, sort_keys=True, ensure_ascii=False) + '\n' for row in rows))


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def summarize(results):
    """Recount frozen target-hit verdicts; companion hits are NOT false positives."""
    groups = defaultdict(list)
    for row in results['records']:
        groups[(row['key'], row['task_type'])].append(row)
    n = len(results['tasks'])
    return {
        'schema_version': 1, 'release': RELEASE, 'case_count': n,
        'task_count': 2 * n, 'record_count': len(results['records']),
        'new_model_calls': False,
        'interpretation': 'Deterministic recount of frozen current-274 records after membership filtering. Target hits on companion tasks are not calibrated false-positive rates. Missing or incomplete results stay in the denominator.',
        'by_model_and_task_type': [
            {'model': model, 'label': results['labels'].get(model, model),
             'task_type': kind, 'assigned': n, 'records': len(rows),
             'scanned': sum(r.get('scanned') is True for r in rows),
             'judged': sum(r.get('judged') is True for r in rows),
             'target_hits': sum(r.get('detected') is True for r in rows),
             'target_hit_rate': sum(r.get('detected') is True for r in rows) / n}
            for (model, kind), rows in sorted(groups.items())
        ],
    }


def export(source, audit_path, results_path, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    audit_path, results_path = Path(audit_path).resolve(), Path(results_path).resolve()
    if source == output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Output and source release must be separate trees')
    audit, roster, results = read(audit_path), read(source / 'roster.json'), read(results_path)
    assert set(audit['summary']['exclude_from_security_core']) == EXCLUDED
    assert set(audit['summary']['hold_for_security_boundary']) == HELD
    all_keys = {f"{e['project']}/{e['bug_id']}" for e in roster['entries']}
    assert len(roster['entries']) == len(all_keys) == 274
    assert set(results['tasks']) == all_keys
    decisions = {x['key']: x for x in audit['cases']}
    assert set(decisions) == all_keys
    kept = all_keys - EXCLUDED - HELD
    assert len(kept) == 265
    # Never remove an existing release silently. A fresh directory is intentional.
    for target in ('data', 'instances', 'artifacts/results'):
        if (output / target).exists():
            raise ValueError(f'Export destination already exists: {output / target}')
    inventory = {}

    def copy_exact(relative, key, role):
        src, dst = source / relative, output / 'data' / relative
        if src.is_symlink() or not src.resolve().is_relative_to(source):
            raise ValueError(f'Unsafe source: {relative}')
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        digest = sha256(src)
        assert sha256(dst) == digest
        inventory[dst.relative_to(output).as_posix()] = {
            'sha256': digest, 'bytes': src.stat().st_size,
            'source_relative_path': str(relative), 'case_key': key,
            'role': role, 'exact_source_bytes': True,
        }

    entries, instances, evidence_index = [], [], {}
    old_instances = {r['instance_id']: r for r in map(json.loads, (source / 'instances.jsonl').read_text().splitlines())}
    for entry in roster['entries']:
        key = f"{entry['project']}/{entry['bug_id']}"
        if key not in kept:
            continue
        entries.append(deepcopy(entry))
        season, project, bug = entry['season'], entry['project'], entry['bug_id']
        evidence_paths = []
        for directory in (f'{season}/data/verification/projects/{project}/cases/{bug}',
                          f'{season}/data/source_evidence/{project}/{bug}',
                          f'{season}/data/human_evidence/{project}/{bug}'):
            for p in sorted((source / directory).rglob('*')):
                if p.is_file():
                    relative = p.relative_to(source).as_posix()
                    copy_exact(relative, key, 'evidence')
                    evidence_paths.append('data/' + relative)
        evidence_index[key] = evidence_paths
        for kind in ('buggy', 'benign'):
            spec = entry[kind]
            assert sha256(source / spec['path']) == spec['sha256']
            assert results['tasks'][key]['task_hashes'][kind] == spec['sha256']
            copy_exact(spec['path'], key, 'task')
            task = read(source / spec['path'])
            old = old_instances[f'{project}__{bug}__{kind}']
            assert old['task_sha256'] == spec['sha256']
            instance = deepcopy(task)
            instance.update({
                'schema_version': 1, 'instance_id': old['instance_id'],
                'project': project, 'repo_url': old['repo_url'], 'task_type': kind,
                'season': season, 'verification_source': entry['source'],
                'task_path': 'data/' + spec['path'], 'task_sha256': spec['sha256'],
                'case_key': key, 'fix_date': entry['fix_date'],
                'date_basis': entry['date_basis'], 'evidence_paths': evidence_paths,
                'release_caveats': [decisions[key]['notes']] if decisions[key].get('notes') else [],
            })
            instances.append(instance)
    new_roster = deepcopy(roster)
    new_roster.update({'name': RELEASE, 'path_base': 'data', 'entries': entries,
                       'eligibility_policy': '../provenance/dataset_policy.json',
                       'source_release': source.name,
                       'release_status': 'staged_with_known_limitations'})
    write(output / 'data/roster.json', new_roster)
    instances.sort(key=lambda x: x['instance_id'])
    jsonl(output / 'instances/secprbench.jsonl', instances)
    for project in sorted({e['project'] for e in entries}):
        jsonl(output / f'instances/{project}.jsonl', [i for i in instances if i['project'] == project])
    counts = dict(sorted(Counter(e['project'] for e in entries).items()))
    write(output / 'instances/manifest.json', {
        'schema_version': 1, 'version': '0.1.0', 'release': RELEASE,
        'instance_count': 530, 'paired_bug_count': 265, 'project_case_counts': counts,
        'by_project': {p: n * 2 for p, n in counts.items()},
        'global_file': 'instances/secprbench.jsonl',
        'roster': 'data/roster.json', 'task_path_base': 'repository',
        'size_cap': {'files_changed': 30, 'lines_changed': 2000},
        'exact_task_bytes': True, 'status': 'staged_with_known_limitations',
    })
    write(output / 'provenance/dataset_policy.json', {
        'schema_version': 1, 'release': RELEASE,
        'source_case_count': 274, 'case_count': 265, 'task_count': 530,
        'filter_basis': 'The 2026-10-10 security-scope audit: eight exclusions and one held case. Introduction age is not an exclusion.',
        'intro_committer_date_minimum': None,
        'fix_committer_date_start_inclusive': '2025-01-01',
        'fix_committer_date_end_exclusive': '2026-07-01',
        'canonical_fix_aliases_preserved': True,
        'retained_pre2021_case_count': len(audit['summary']['old_intro_committer_dates']),
        'exclude_case_keys': sorted(EXCLUDED), 'held_case_keys': sorted(HELD),
        'known_repair_cases_retained': True,
        'artifact_policy': 'Frozen tasks and supporting JSON are byte-for-byte copies; no new introduction, patch repair, historical build, replay, or model invocation. Corrections require a new artifact version and new evidence where identities change.',
        'paper_policy_status': 'The release omits the introduction-age cutoff by user direction; the manuscript is not edited by this export.',
    })
    exclusions = []
    for key in sorted(EXCLUDED | HELD):
        e = next(e for e in roster['entries'] if f"{e['project']}/{e['bug_id']}" == key)
        exclusions.append({'case_key': key, 'status': 'held' if key in HELD else 'excluded',
                           'reason': decisions[key]['notes'], 'season': e['season'],
                           'original_tasks': {kind: deepcopy(e[kind]) for kind in ('buggy', 'benign')},
                           'payloads_included': False})
    write(output / 'provenance/dataset_exclusions.json', {'schema_version': 1, 'cases': exclusions})
    write(output / 'provenance/dataset_issues.json', {
        'schema_version': 1,
        'status': 'Known limitations are recorded, not repaired or silently relabeled.',
        'repair_required': audit['summary']['repair_cases'],
        'evidence_scope_notes': audit['summary']['retain_with_evidence_notes'],
        'external_artifacts': 'Original evidence JSON records may reference historical absolute paths, logs, PoCs, build images, or model trajectories not bundled here. These are provenance only, not runtime dependencies. No claim of complete historical replay portability is made.',
        'companion_snapshot': 'Historical companion review runs may use the upstream fixing tree while verification evaluates the composed repaired tree; evidence does not transfer automatically between these identities.',
        'judge_scope': 'Frozen companion target-hit verdicts are not calibrated false-alarm measurements. Judge audit and snapshot alignment remain publication work.',
    })
    ledger = []
    for key in sorted(all_keys):
        row = deepcopy(decisions[key])
        for field in ('buggy_task_path', 'companion_task_path', 'verification_path'):
            row[field] = Path(row[field]).relative_to(source).as_posix()
        row['release_status'] = 'held' if key in HELD else 'excluded' if key in EXCLUDED else 'retained'
        ledger.append(row)
    write(output / 'provenance/dataset_decisions.json', {'schema_version': 1, 'cases': ledger})
    write(output / 'provenance/dataset_evidence_index.json', {
        'schema_version': 1, 'path_base': 'repository', 'cases': evidence_index,
        'historical_embedded_paths': 'Kept byte-for-byte in evidence; use this index for bundled evidence.',
    })
    filtered = deepcopy(results)
    filtered['tasks'] = {k: v for k, v in results['tasks'].items() if k in kept}
    filtered['records'] = [r for r in results['records'] if r['task'] in kept]
    referred = set(strings({'tasks': filtered['tasks'], 'records': filtered['records']}))
    filtered['source_files'] = {p: h for p, h in results['source_files'].items() if p in referred}
    filtered['release'] = RELEASE
    filtered['policy']['denominator'] = len(kept)
    filtered['derived_from'] = {'filename': results_path.name, 'sha256': sha256(results_path),
                                'captured_at': results['captured_at'], 'original_case_count': 274,
                                'operation': 'Membership-only filtering; per-case metadata and records retained unchanged.',
                                'new_model_calls': False}
    filtered['portable_task_paths'] = {
        f"{e['project']}/{e['bug_id']}": {k: 'data/' + e[k]['path'] for k in ('buggy', 'benign')}
        for e in entries}
    write(output / 'artifacts/results/results_265_opus55_high.json', filtered)
    write(output / 'artifacts/results/summary_265.json', summarize(filtered))
    write(output / 'provenance/dataset_result_records.json', {
        'schema_version': 1,
        'hash_encoding': 'SHA-256 of canonical JSON: sorted keys, compact separators, UTF-8, ensure_ascii=False.',
        'records': [{'model': r['key'], 'case_key': r['task'], 'task_type': r['task_type'], 'sha256': content_hash(r)} for r in filtered['records']],
        'task_metadata_sha256': {k: content_hash(v) for k, v in filtered['tasks'].items()},
    })
    # Hash all managed release files after writing. The manifest itself is excluded
    # to avoid a circular checksum; its own bytes are protected by Git/release tag.
    managed = [p for sub in ('data', 'instances', 'artifacts/results') for p in (output / sub).rglob('*') if p.is_file()]
    managed += list((output / 'provenance').glob('dataset_*.json'))
    for p in sorted(managed):
        rel = p.relative_to(output).as_posix()
        if rel == 'provenance/dataset_manifest.json':
            continue
        inventory.setdefault(rel, {'role': 'derived', 'exact_source_bytes': False})
        inventory[rel].update({'sha256': sha256(p), 'bytes': p.stat().st_size})
    write(output / 'provenance/dataset_manifest.json', {
        'schema_version': 1, 'release': RELEASE, 'case_count': len(kept), 'task_count': len(instances),
        'project_case_counts': counts,
        'season_case_counts': dict(sorted(Counter(e['season'] for e in entries).items())),
        'admission_counts': dict(sorted(Counter(e['source'] for e in entries).items())),
        'source_inputs': {label: {'filename': p.name, 'sha256': sha256(p), 'bytes': p.stat().st_size}
                          for label, p in [('roster', source / 'roster.json'), ('source_instances', source / 'instances.jsonl'), ('audit', audit_path), ('paper_results', results_path)]},
        'files': inventory,
        'manifest_checksum_scope': 'All data, instance, derived result, and dataset provenance files, except this manifest itself. Code/docs are protected by Git rather than this dataset manifest.',
    })
    return {'release': RELEASE, 'cases': len(kept), 'tasks': len(instances), 'files': len(inventory),
            'evidence_files': sum(v['role'] == 'evidence' for v in inventory.values()),
            'results': len(filtered['records']), 'output': str(output)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-release', type=Path, required=True)
    p.add_argument('--audit', type=Path, required=True)
    p.add_argument('--paper-results', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1])
    a = p.parse_args()
    print(json.dumps(export(a.source_release, a.audit, a.paper_results, a.output), indent=2))


if __name__ == '__main__':
    main()
