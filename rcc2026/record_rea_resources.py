"""Bound REA startup separately from its validated metadata result."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

from windows_diagnostics import sanitize_log
from windows_probe import STUDIO_SHA256


def validate_evidence(text):
    result = json.loads(text.lstrip('\ufeff'))
    subject = result.get('subject') if isinstance(result, dict) else None
    digest = subject.get('digest') if isinstance(subject, dict) else None
    if (not isinstance(result, dict) or result.get('operation') != 'inspect_pe_resources'
            or not isinstance(digest, dict) or digest.get('sha256') != STUDIO_SHA256
            or not isinstance(result.get('normalized_result'), dict)
            or not isinstance(result['normalized_result'].get('resources'), list)):
        raise ValueError('REA did not return the expected pinned PE resource evidence')
    return result


def record(binary, output, timeout=210):
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    status = {'validated': False, 'status': 'not_started', 'expected_sha256': STUDIO_SHA256}
    try:
        if hashlib.sha256(binary.read_bytes()).hexdigest() != STUDIO_SHA256:
            raise ValueError('Studio executable hash mismatch')
        executable = shutil.which('npx')
        if executable is None:
            raise ValueError('npx is unavailable')
        process = subprocess.run([executable, '-y', 'rea-agents@6.7.0', 'inspect-pe-resources',
            str(binary.resolve()), '--max-file-bytes', '268435456', '--format', 'json'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8',
            errors='replace', timeout=timeout, check=False)
        status.update(exit_code=process.returncode, stdout_bytes=len(process.stdout.encode('utf-8')),
                      stderr_tail=sanitize_log(process.stderr[-4000:]))
        if process.returncode:
            status['status'] = 'nonzero_exit'
        else:
            result = validate_evidence(process.stdout)
            (output/'rea-pe-resources.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
            status.update(validated=True, status='validated', evidence_id=result.get('evidence_id'))
    except subprocess.TimeoutExpired:
        status['status'] = 'timeout'
        status['timeout_seconds'] = timeout
    except (ValueError, OSError) as exc:
        status.update(status='invalid_or_unavailable_evidence', error=sanitize_log(str(exc)))
    finally:
        status['elapsed_seconds'] = round(time.monotonic()-started, 3)
        (output/'rea-status.json').write_text(json.dumps(status, indent=2)+'\n', encoding='utf-8')
    return status


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    status = record(args.binary, args.output)
    print(json.dumps(status, indent=2))
    raise SystemExit(0 if status['validated'] else 1)
