#!/usr/bin/env python3
"""Validate the staged SecPRBench release offline, without models or source repos."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path
import sys

# Imports are relative to the script so validation works from any working directory.
from export_release import EXCLUDED, HELD, content_hash, sha256, summarize


def validate(root):
    root = Path(root).resolve()
    errors, warnings = [], []

    def require(condition, message):
        if not condition:
            errors.append(message)

    def local(relative):
        require(isinstance(relative, str) and not Path(relative).is_absolute(), f'Nonportable operational path: {relative}')
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError(f'Operational path escapes release: {relative}')
        return path

    def read(relative):
        return json.loads(local(relative).read_bytes())

    try:
        manifest = read('provenance/dataset_manifest.json')
        roster = read('data/roster.json')
        policy = read('provenance/dataset_policy.json')
        issues = read('provenance/dataset_issues.json')
        exclusions = read('provenance/dataset_exclusions.json')
        decisions = read('provenance/dataset_decisions.json')
        evidence = read('provenance/dataset_evidence_index.json')
        instances_meta = read('instances/manifest.json')
        results = read('artifacts/results/results_265_opus55_high.json')
        record_hashes = read('provenance/dataset_result_records.json')
        summary = read('artifacts/results/summary_265.json')
        expected_files = set(manifest['files'])
        actual_files = {p.relative_to(root).as_posix() for sub in ('data', 'instances', 'artifacts/results')
                        for p in local(sub).rglob('*') if p.is_file()}
        actual_files |= {p.relative_to(root).as_posix() for p in local('provenance').glob('dataset_*.json')
                         if p.name != 'dataset_manifest.json'}
        require(actual_files == expected_files, f'Manifest file inventory differs: missing={sorted(expected_files-actual_files)}, unlisted={sorted(actual_files-expected_files)}')
        for relative, entry in manifest['files'].items():
            path = local(relative)
            require(path.is_file(), f'Missing file: {relative}')
            if path.is_file():
                require(path.stat().st_size == entry['bytes'], f'Size mismatch: {relative}')
                require(sha256(path) == entry['sha256'], f'SHA-256 mismatch: {relative}')
        entries = roster['entries']
        keys = [f"{e['project']}/{e['bug_id']}" for e in entries]
        keyset = set(keys)
        require(len(entries) == len(keyset) == 265, 'Expected exactly 265 unique paired cases')
        require(not (keyset & (EXCLUDED | HELD)), 'Excluded/held case present in active roster')
        require(roster['path_base'] == 'data', 'Roster paths must resolve relative to data/')
        require(policy['intro_committer_date_minimum'] is None, 'Introduction-age cutoff must be absent')
        require(set(policy['exclude_case_keys']) == EXCLUDED, 'Exclusion policy differs from approved filter')
        require(set(policy['held_case_keys']) == HELD, 'Hold policy differs from approved filter')
        require(policy['case_count'] == manifest['case_count'] == instances_meta['paired_bug_count'] == 265, 'Case count metadata mismatch')
        require(policy['task_count'] == manifest['task_count'] == instances_meta['instance_count'] == 530, 'Task count metadata mismatch')
        excluded_rows = exclusions['cases']
        require({x['case_key'] for x in excluded_rows} == EXCLUDED | HELD and len(excluded_rows) == 9, 'Exclusion ledger mismatch')
        require(all(x['payloads_included'] is False for x in excluded_rows), 'Excluded payload must not be bundled')
        for x in excluded_rows:
            require(x['status'] == ('held' if x['case_key'] in HELD else 'excluded'), f"Wrong exclusion status: {x['case_key']}")
            require(bool(x['reason']), f"Missing exclusion reason: {x['case_key']}")
            for kind in ('buggy', 'benign'):
                require(len(x['original_tasks'][kind]['sha256']) == 64, f"Missing excluded original hash: {x['case_key']}")
                require(not local('data/' + x['original_tasks'][kind]['path']).exists(), f"Excluded task file is present: {x['case_key']}")
        ledger = {x['key']: x for x in decisions['cases']}
        require(len(ledger) == len(decisions['cases']) == 274, 'Decision ledger must describe all 274 original cases')
        require(set(ledger) == keyset | EXCLUDED | HELD, 'Decision ledger membership mismatch')
        old = {k for k in keyset if datetime.fromisoformat(ledger[k]['intro_committer_date'].replace('Z', '+00:00')).year < 2021}
        require(len(old) == policy['retained_pre2021_case_count'] == 36, 'All 36 pre-2021 introductions must remain')
        for key in keyset:
            d = ledger[key]
            require(d['release_status'] == 'retained', f'Wrong retained decision: {key}')
            fix_date = datetime.fromisoformat(d['canonical_fix_date'].replace('Z', '+00:00')).date().isoformat()
            require(policy['fix_committer_date_start_inclusive'] <= fix_date < policy['fix_committer_date_end_exclusive'], f'Canonical fixing date outside window: {key}')
        counts = dict(sorted(Counter(e['project'] for e in entries).items()))
        require(counts == manifest['project_case_counts'] == instances_meta['project_case_counts'], 'Project case counts mismatch')
        require(dict(sorted(Counter(e['season'] for e in entries).items())) == manifest['season_case_counts'], 'Season case counts mismatch')
        require(dict(sorted(Counter(e['source'] for e in entries).items())) == manifest['admission_counts'], 'Admission counts mismatch')
        instances = [json.loads(line) for line in local('instances/secprbench.jsonl').read_text().splitlines()]
        indexed = {i['instance_id']: i for i in instances}
        require(len(instances) == len(indexed) == 530, 'Expected exactly 530 unique instances')
        require({i['case_key'] for i in instances} == keyset, 'Instance case membership mismatch')
        require(set(evidence['cases']) == keyset, 'Evidence index membership mismatch')
        task_hashes, task_paths = {}, set()
        for entry in entries:
            key = f"{entry['project']}/{entry['bug_id']}"
            for kind in ('buggy', 'benign'):
                spec = entry[kind]
                require(not Path(spec['path']).is_absolute() and '..' not in Path(spec['path']).parts,
                        f'Nonportable roster path: {key}/{kind}')
                relative = 'data/' + spec['path']
                path = local(relative)
                task_paths.add(relative)
                require(sha256(path) == spec['sha256'], f'Roster task hash mismatch: {key}/{kind}')
                task = json.loads(path.read_bytes())
                require(task['task_id'] == spec['task_id'], f'Task ID mismatch: {key}/{kind}')
                require(task['bug_id'] == entry['bug_id'], f'Task bug ID mismatch: {key}/{kind}')
                require(isinstance(task['files'], list) and bool(task['files']), f'Missing task files: {key}/{kind}')
                require(len(task['files']) <= 30, f'File size cap exceeded: {key}/{kind}')
                changed = sum(f.get('additions', 0) + f.get('deletions', 0) for f in task['files'])
                require(changed <= 2000, f'Line size cap exceeded: {key}/{kind}')
                iid = f"{entry['project']}__{entry['bug_id']}__{kind}"
                instance = indexed[iid]
                require(instance['task_path'] == relative and instance['task_sha256'] == spec['sha256'], f'Instance binding mismatch: {iid}')
                require(all(instance.get(k) == v for k, v in task.items()), f'Instance task contents differ: {iid}')
                require(instance['evidence_paths'] == evidence['cases'][key], f'Instance evidence mismatch: {iid}')
                task_hashes[(key, kind)] = spec['sha256']
                require(manifest['files'][relative]['exact_source_bytes'] is True, f'Task not recorded as immutable copy: {relative}')
            case_path = f"data/{entry['season']}/data/verification/projects/{entry['project']}/cases/{entry['bug_id']}/case.json"
            require(case_path in evidence['cases'][key], f'Missing verification evidence: {key}')
            for relative in evidence['cases'][key]:
                meta = manifest['files'][relative]
                require(meta['role'] == 'evidence' and meta['case_key'] == key and (meta['exact_source_bytes'] or meta.get('host_paths_redacted')), f'Evidence binding mismatch: {relative}')
                require(local(relative).is_file(), f'Evidence not bundled: {relative}')
            # All portable, hash-bound adjudication references must also resolve.
            def check_references(value):
                if isinstance(value, dict):
                    if 'path' in value and 'sha256' in value:
                        p = local('data/' + value['path'])
                        require(p.is_file() and sha256(p) == value['sha256'], f'Adjudication reference changed/missing: {value["path"]}')
                    for v in value.values():
                        check_references(v)
                elif isinstance(value, list):
                    for v in value:
                        check_references(v)
            check_references(entry.get('adjudication_evidence', {}))
        require(task_paths == {p for p, v in manifest['files'].items() if v['role'] == 'task'}, 'Task file inventory differs from active roster')
        for project in counts:
            project_instances = [json.loads(line) for line in local(f'instances/{project}.jsonl').read_text().splitlines()]
            require(project_instances == [i for i in instances if i['project'] == project], f'Project JSONL differs from global instances: {project}')
        require(set(results['tasks']) == keyset, 'Frozen result tasks differ from release')
        require(results['policy']['denominator'] == 265, 'Frozen result denominator mismatch')
        require(results['derived_from']['new_model_calls'] is False, 'Results must be identified as historical')
        require(results['derived_from']['sha256'] == manifest['source_inputs']['paper_results']['sha256'], 'Original paper result hash mismatch')
        hashes = {(r['model'], r['case_key'], r['task_type']): r['sha256'] for r in record_hashes['records']}
        require(len(hashes) == len(record_hashes['records']), 'Duplicate historical record bindings')
        seen, groups = set(), defaultdict(set)
        for r in results['records']:
            rid = (r['key'], r['task'], r['task_type'])
            require(rid not in seen, f'Duplicate result record: {rid}')
            seen.add(rid)
            require(r['task'] in keyset, f'Excluded result present: {rid}')
            require(r['task_type'] in ('buggy', 'benign'), f'Invalid result task type: {rid}')
            require(r.get('task_sha256') == task_hashes.get((r['task'], r['task_type'])), f'Result/task hash mismatch: {rid}')
            require(content_hash(r) == hashes.get(rid), f'Historical result record changed: {rid}')
            if (r.get('judge') or {}).get('task_sha256'):
                require(r['judge']['task_sha256'] == r['task_sha256'], f'Judge/task hash mismatch: {rid}')
            groups[(r['key'], r['task_type'])].add(r['task'])
        require(seen == set(hashes), 'Result hash ledger membership mismatch')
        require(len(groups) == 16 and len(seen) == 4240, 'Expected 8 model arms x 2 task types x 265 cases = 4240 frozen records')
        for group, keys_for_group in groups.items():
            require(keys_for_group == keyset, f'Incomplete frozen result assignments: {group}')
        for key, taskmeta in results['tasks'].items():
            require(content_hash(taskmeta) == record_hashes['task_metadata_sha256'][key], f'Historical task metadata changed: {key}')
            for kind in ('buggy', 'benign'):
                require(taskmeta['task_hashes'][kind] == task_hashes[(key, kind)], f'Frozen task metadata hash mismatch: {key}/{kind}')
                require(sha256(local(results['portable_task_paths'][key][kind])) == task_hashes[(key, kind)], f'Nonportable frozen task link: {key}/{kind}')
        require(summary == summarize(results), 'Frozen summary is not the deterministic filtered recount')
        require(set(issues['repair_required']) == {'sqlite/FORUM-8f384febcc9b', 'curl/CVE-2025-0167', 'curl/CVE-2026-5545', 'curl/CVE-2026-9079', 'curl/GH-17830', 'curl/GH-19039'}, 'Known immutable artifact limitations missing')
        warnings.extend(f'{key}: {note}' for key, note in issues['repair_required'].items())
        warnings.append(issues['external_artifacts'])
        warnings.append(issues['companion_snapshot'])
        warnings.append(issues['judge_scope'])
        return {'ok': not errors, 'cases': len(keyset), 'tasks': len(task_paths),
                'files_checked': len(manifest['files']), 'evidence_files': sum(v['role'] == 'evidence' for v in manifest['files'].values()),
                'pre2021_cases_retained': len(old), 'excluded': 8, 'held': 1,
                'historical_result_records': len(results['records']),
                'errors': errors, 'warnings': warnings,
                'scope': 'Offline consistency and exact-file validation; no historical builds, replay, patch applicability checks, or live model calls.'}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f'Validation could not complete: {type(exc).__name__}: {exc}')
        return {'ok': False, 'errors': errors, 'warnings': warnings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    report = validate(args.root)
    print(json.dumps(report, indent=2))
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
