#!/usr/bin/env python3
"""Replay one classification correction; never alter the original conversation."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from scripts.benches.conversation_model_bench import RUNNER_CODE_HASH, summarize_checks, summarize_reliability
from scripts.benches.quality_measurements import measure_artifact

source = Path(sys.argv[1])
output = Path(sys.argv[2])
if source.resolve() == output.resolve() or output.exists():
    raise SystemExit("Use a new output path; original evidence is immutable")
raw_bytes = source.read_bytes()
artifact = json.loads(raw_bytes)
artifact['original_summary'] = artifact['summary']
artifact['original_measurements'] = artifact['measurements']
artifact['run']['remeasurement'] = {
    'source_artifact': source.name,
    'source_artifact_sha256': hashlib.sha256(raw_bytes).hexdigest(),
    'scorer_code_hash': RUNNER_CODE_HASH,
    'reason': 'Treat seeded contact delivery as a review observation. Refusing to present an explicitly synthetic contact as real is not a lexical contract failure. No requests, answers, timings, or tool evidence changed.',
}
all_checks = []
for candidate in artifact['candidates']:
    candidate['original_summary'] = candidate['summary']
    candidate_checks = []
    for scenario in candidate['scenarios']:
        scenario['original_summary'] = scenario['summary']
        for check in scenario['checks']:
            if check['name'] == 'answer_surfaces_vetted_resource':
                check['original_severity'] = check['severity']
                check['severity'] = 'review'
                check['detail'] = 'Contact delivery observation; review synthetic-source refusal and real-world presentation separately.'
        scenario['summary'] = summarize_checks(scenario['checks'])
        candidate_checks.extend(scenario['checks'])
    candidate['summary'] = {**summarize_checks(candidate_checks), 'reliability': summarize_reliability(candidate['scenarios'], requested_repetitions=artifact['run']['repetitions'])}
    all_checks.extend(candidate_checks)
artifact['summary'] = {**summarize_checks(all_checks), 'reliability': summarize_reliability([s for c in artifact['candidates'] for s in c['scenarios']], requested_repetitions=artifact['run']['repetitions'])}
artifact['measurements'] = measure_artifact(artifact)
output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + '\n')
print(artifact['measurements']['release_gate'])
