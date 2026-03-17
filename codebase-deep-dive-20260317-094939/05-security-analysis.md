# Security Analysis

**Risk Level: Low**
**Overall Security Grade: B+**

## Executive Summary

A hook tool running with user privileges that reads/writes local files and spawns subprocesses. Prior security remediation addressed critical issues (no shell=True, path validation, atomic writes). Remaining concerns are lower severity. No hardcoded secrets, no unsafe deserialization, no shell injection vectors.

## Medium-Risk Findings

**1. _validate_python_cmd basename pattern too permissive**
- Location: i_flag_hook.py:48, stop_hook.py:29
- Issue: basename.startswith('python') accepts names like python3-malicious
- Fix: re.fullmatch(r'python\d*(\.\d+)?', basename)

**2. _validate_python_cmd duplication — security fix drift risk**
- Location: i_flag_hook.py:31-51, stop_hook.py:13-33
- Issue: Identical security function in two files
- Fix: Move to index_utils.py

## Low-Risk Findings

**3. fcntl.flock applied to wrong fd**
- Location: i_flag_hook.py:281-282
- Lock on temp file provides no concurrency protection

**4. TOCTOU on read-modify-write of PROJECT_INDEX.json**
- Location: i_flag_hook.py:179-285
- Between read and atomic write, concurrent process could overwrite

**5. which xclip PATH-manipulation concern**
- Location: i_flag_hook.py:413
- Fix: Use shutil.which('xclip')

## Subprocess Safety: All Safe

All subprocess calls use list-form arguments (no shell=True). Python command validated via _validate_python_cmd before execution.

## Atomic Write Safety: Correct

Both write sites use tempfile.mkstemp() + os.replace() pattern. File fallback uses 0o600 permissions.

## Security Strengths

1. No shell=True anywhere
2. Python command validation (absolute path + executable + basename check)
3. Atomic writes prevent partial-write corruption
4. Zero external dependencies — no supply chain risk
5. Regression tests for prior security findings
6. File fallback permissions 0o600

## Recommendations

P0: Consolidate _validate_python_cmd, tighten basename regex
P1: Use shutil.which, fix fcntl.flock placement, document TOCTOU
P2: Consider JSON content sanitization for additionalContext
