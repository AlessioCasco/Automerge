# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.12] - 2025-07-24
- Dependabot Pip: Bump pygments from 2.19.1 to 2.19.2 #72
- Fixed import system to support both direct script execution (`python3 src/main.py`) and module execution (`python3 -m src.main`)
- Resolved relative import issues that prevented running the script directly
- Fixed multiline f-string syntax errors that caused linting failures
- Improved code formatting and PEP 8 compliance
- Added more tests
- Added `run_tests.py`
- Added coverage report + CI

## [1.0.11] - 2025-07-17
-  Dependabot Pip: Bump rich from 13.9.4 to 14.0.0 #63
-  Updated `values.yaml`
-  Split code into modules + handle dismissed PRs #71
-  Dependabot Pip: Bump certifi from 2025.1.31 to 2025.7.14 #70
-  Dependabot Pip: Bump urllib3 from 2.3.0 to 2.5.0 #69
-  Dependabot Pip: Bump requests from 2.32.3 to 2.32.4 #67
-  Dependabot Pip: Bump charset-normalizer from 3.4.1 to 3.4.2 #66

## [1.0.10] - 2025-03-14
-  Testing nonroot, vs sha due to incompatibility CPU #62

## [1.0.9] - 2025-03-14
-  Use distroless for docker to reduce vulnerabilities #61

## [1.0.8] - 2025-03-05
-  Dependabot Pip: Bump charset-normalizer from 3.4.0 to 3.4.1 #60
-  Dependabot Pip: Bump certifi from 2024.8.30 to 2025.1.31 #59
-  Dependabot Pip: Bump urllib3 from 2.2.3 to 2.3.0 #58
-  Dependabot Pip: Bump pygments from 2.18.0 to 2.19.1 #57

## [1.0.7] - 2025-02-18
-  Dependabot Pip: Bump rich from 13.8.0 to 13.9.4 (#56)
-  Dependabot Pip: Bump charset-normalizer from 3.3.2 to 3.4.0 (#54)
-  Dependabot Pip: Bump urllib3 from 2.2.2 to 2.2.3 (#51)
-  Dependabot Pip: Bump idna from 3.8 to 3.10 (#52)

## [1.0.6] - 2024-09-4
- Fixes #7 added the `--force` parameter
- Dependabot Pip: Bump pygments from 2.17.2 to 2.18.0 (#45)
- Dependabot Pip: Bump idna from 3.7 to 3.8 (#46)
- Dependabot Pip: Bump certifi from 2024.7.4 to 2024.8.30 (#47)
- Dependabot Pip: Bump rich from 13.7.1 to 13.8.0 (48)

## [1.0.5] - 2024-07-25
- Increased timeout for state return to 4 min.
- Dependabot Pip: Bump certifi from 2024.2.2 to 2024.7.4 (#43)
- Dependabot Pip: Bump urllib3 from 2.2.1 to 2.2.2 (#42)
- Dependabot Github Actions: Bump docker/build-push-action from 5 to 6 (#41)
- Dependabot Pip: Bump requests from 2.31.0 to 2.32.3 (#40)
- Dependabot Pip: Bump certifi from 2024.2.2 to 2024.6.2 (#39)
- Dependabot Pip: Bump pygments from 2.17.2 to 2.18.0 (#36)
- Dependabot Pip: Bump idna from 3.6 to 3.7 (#35)

## [1.0.4] - 2024-03-08
- Handle case when the PR has conflicts (dirty)
- When renovate comments that there is a new version of the dependency, we close the PR and let it open a new one.
- Handle pagination on the comments API
- Handle when the state of the PR is Dismissed
- Bump pre-commit repos
- Dependabot Pip: Bump rich from 13.7.0 to 13.7.1 #33
- Dependabot Pip: Bump urllib3 from 2.1.0 to 2.2.1 #32
- Dependabot Pip: Bump certifi from 2023.11.17 to 2024.2.2 #31

## [1.0.3] - 2023-12-06
- Dependabot Pip: Bump pygments from 2.17.1 to 2.17.2 #29
- Dependabot Pip: Bump idna from 3.4 to 3.6 #28

## [1.0.2] - 2023-11-20
- Dependabot Pip: Bump pygments from 2.16.1 to 2.17.1 #27
- Dependabot Pip: Bump certifi from 2023.7.22 to 2023.11.17 #26
- Dependabot Pip: Bump rich from 13.6.0 to 13.7.0 #25
- Dependabot Pip: Bump urllib3 from 2.0.6 to 2.1.0 #24
- Dependabot Pip: Bump charset-normalizer from 3.3.0 to 3.3.2 #23

## [1.0.1] - 2023-09-27
- Bumped to python 3.12.0 #20
- Fixing multi tag vuln scan + bump dependencies (#16)
- Added trivy #15

## [1.0.0] - 2023-09-20
- Supporting regex in pull request titles. (#12)
  - Breaking changes: config requires the key `prefixes` to be replaced to `filters`

## [0.1.1] - 2023-09-18
- Dependabot Pip: Bump rich from 13.5.2 to 13.5.3 (#9)

## [0.1.0] - 2023-09-14
- First version, initial commit
