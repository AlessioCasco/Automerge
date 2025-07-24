![CI](https://github.com/AlessioCasco/automerge/actions/workflows/ci.yml/badge.svg)
![Lint & tests](https://github.com/AlessioCasco/automerge/actions/workflows/at-every-commit.yml/badge.svg)
![Docker Build](https://github.com/AlessioCasco/automerge/actions/workflows/build_and_push.yml/badge.svg)
# Automerge for GitHub and Atlantis

Used to automatically merge terraform dependencies pull requests in GitHub that result in no differences.

Tools like [dependabot](https://github.com/dependabot) or [renovate](https://github.com/renovatebot/renovate) can create a lot of pull requests if you have different providers or modules in your terraform code. Most of the time these changes result in no terraform differences and can be merged automatically without any intervention.

Automerge does exactly this: Checks every PR that has a title that matches a specific string, plans it and if the terraform plan results in `No changes` it approves and merges the PR.

It works along with the [atlantis](runatlantis.io) tool.

## Dependencies
Automerge (for now) works only with [github](github.com) repos and [atlantis](runatlantis.io), so you need to have a working Atlantis installation to use it.

## Configuration
```json
{
  "access_token" : "token",
  "filters" : [
    "^\\[DEPENDENCIES\\] Update Terraform",
    "^\\[DEPENDABOT\\]",
    "^\\[Dependabot\\]"
  ],
  "github_user" : "AlessioCasco",
  "owner" : "my_company",
  "repos" : [
    "terraform-vault",
    "terraform-aws"
  ]
}
```

* `access_token`: Token (classic) from GitHub that needs to have the following Scopes:
  * Full control of private repositories.
* `filters`: Regex that Automerge uses to filter the pull requests it has to consider.
  * This is usually what you set in the [prefix](https://docs.github.com/en/code-security/dependabot/dependabot-version-updates/configuration-options-for-the-dependabot.yml-file#commit-message) option for dependabot or the equivalent [commitMessagePrefix](https://docs.renovatebot.com/configuration-options/#commitmessageprefix) option for renovate.
  * Be aware that you need to escape the backslashes in the JSON string to properly represent the regular expressions, [see the configuration section](#configuration) for an example.
* `github_user`: GitHub user that owns the `access_token`.
* `owner`: Owner of the repos where we want to check the pull requests.
* `repos`: list of repo names that you want to check pull requests from (note that they all need to be under the same owner).
  * ie `https://github.com/Owner/repo/`


## GitHub Config
### Branch protection
If you [Require status checks from Atlantis to pass before merging](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks) on your [Branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule), make sure that the atlantis ones are set to `atlantis/plan` only.
Automerge will never apply anything (for now) so having an `atlantis/apply` check set as required will break the ability for automerge to merge pull requests.
This because automerge does not `bypass branch protections`. Before merging any pull request it waits that all checks are green.

### Codeowners
Since the GitHub user leveraged by Automerge has to be able to comment, approve and merge pull requests, depending on your GitHub configs it may be required to add such a user in the [codeowners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) file and also as writer for the repository.

## Usage
### Options
```bash
options:
  -h, --help            show this help message and exit
  --config_file CONFIG_FILE
                        JSON file holding the GitHub access token, default is .config.json
  --approve_all         Approves all PRs that match the filters in the config
```

### Python
Create a config file (by default it should be placed in ./config.json)
And run the following:
```bash
# Install dependencies
pip3 install -r requirements.txt
# Run it
python3 main.py
```

### Docker
```bash
docker run -d -v ./config.json:/app/config.json --name automerge alessiocasco/automerge:latest
```

### Helm
Move to `/charts/automerge`, tune your `values.yaml` file and run:
```
helm install -f values.yaml automerge -n <your_namespace> .
```

## Testing and Development

### Manual Testing Commands
```bash
# Install dependencies (including coverage)
pip install -r requirements.txt

# Run tests only
python -m unittest discover -s ./tests -p 'test_*.py' -v
```
### Manual Coverage Commands
```bash
# Run tests with coverage
coverage run -m unittest discover -s ./tests -p 'test_*.py'

# Generate coverage report
coverage report

# Generate HTML coverage report
coverage html
```
### Manual ruff Commands
```bash
# Run code linting
ruff check .

# Auto-fix linting issues
ruff check . --fix
```

### Running Specific Tests
```bash
# Run tests for a specific module
python -m unittest tests.test_config -v

# Run a specific test class
python -m unittest tests.test_github_client.TestIsApproved -v

# Run a single test method
python -m unittest tests.test_config.TestValidateConfig.test_validate_config_success -v

# Run tests matching a pattern
python -m unittest discover -s ./tests -p 'test_github*' -v

# Run tests with verbose output
python -m unittest discover -s ./tests -p 'test_*.py' -v

# Run tests and stop on first failure
python -m unittest discover -s ./tests -p 'test_*.py' --failfast
```

### Continuous Integration
The project uses GitHub Actions for CI/CD with:
- **Python Coverage Comment Action**: Automatically comments coverage reports on PRs
- **Multi-version testing**: Tests against Python 3.9, 3.10, 3.11, and 3.12
- **Code linting**: Uses Ruff for code quality checks
- **Coverage reporting**: Generates detailed coverage reports

Coverage reports are automatically generated and commented on pull requests, helping maintain code quality standards.

### Test File Organization

The test suite is organized in the `tests/` directory with the following structure:

```
tests/
├── test_config.py          # Configuration loading and validation tests
├── test_github_client.py   # GitHub API interaction tests
├── test_pr_processor.py    # Pull request processing logic tests
├── test_utils.py           # Utility function tests
├── test_main.py            # Main application tests
├── test_dismissed_prs.py   # Dismissed PR handling tests
└── test_conf.py            # Test utilities and mock objects
```

**Test Naming Conventions:**
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<functionality>_<scenario>`

**Example Test Structure:**
```python
class TestGitHubClient(unittest.TestCase):
    def setUp(self):
        # Test setup code

    def test_is_approved_true(self):
        # Test when PR is approved

    def test_is_approved_false(self):
        # Test when PR is not approved

    def test_is_approved_error_handling(self):
        # Test error scenarios
```

### Development Workflow
1. Make your changes
2. Run tests: `python run_tests.py --full_no_web`
3. Fix any linting issues: `ruff check . --fix`
4. Commit your changes

## Usage
This tool is intended to run as a k8s cronjob during the night; every ~15 minutes for a couple of hours so it can close as many pull requests as possible.
Something like:
```cron
*/20 3-5 * * *
```

## What it does at every run:
* Gets all pull requests from every repo listed in the config
* Filters out the ones that don't have the prefix set in the config
  * If the pull request is new and has no comments:
    * Syncs the branch with master if needed, waits for all the checks to pass and finally writes `atlantis plan` as a comment into the pull request
  * If the pull request is planned and has no diffs:
    * Approves the pull request and merges it
  * If the pull request is planned and has diffs:
    * Writes comment `This PR will be ignored by automerge` into the pull request, unlocks it and sets an `automerge_ignore` label.
    * All future runs of Automerge will ignore this pull request (see option `--force` to override this)
  * If the pull request was planned but had errors:
    * Automerge will try to plan it again
  * If the pull request was planned by no projects were actually planned (Usually happens when the pull request bumps something in a module and Atlantis )
    * Automerge sets the following label `automerge_no_project` and ignores it.

## Ignored pull requests and labels:
Automerge ignores all pull requests having terraform differences or that result in no projects being planned. It marks the first ones with a `automerge_ignore` label and the others with `automerge_no_project`, so you can filter by label with the following GitHub query `is:open label:automerge_ignore ` for example and take action.

## Know issues:
* Automerge does not work really well with repos that have Atlantis set to automatic plan every time there is a change in the code. This conflicts with the syncing from master + the `atlantis plan` comments and may end up with errors shown in the comments.
  * We may add a parameter to the config where we define the behaviour of automerge for specific repos.
    * ie: instead of syncing from master and comment, we can only sync
* Atlantis [doesn't have an API to unlock pull requests](https://github.com/runatlantis/atlantis/issues/733), so we can't unlock everything before starting automerge, this may result in automerge being unable to plan specific pull requests until the lock is manually released. A solution may be to intercept the message, unlock it and plan it on the next run.
