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
  ],
  "enable_ai_confidence_score" : false,
  "enable_ai_automerge_action" : false,
  "disable_pr_comments" : false,
  "ai_provider" : "github",
  "ai_config" : {
    "github" : {
      "api_base" : "http://localhost:4141",
      "model" : "claude-sonnet-4"
    },
    "claude-code" : {
      "api_base" : "https://api.anthropic.com",
      "api_key" : "your_anthropic_api_key_here",
      "model" : "claude-3-5-sonnet-20241022"
    }
  },
  "test_prs" : []
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
* `enable_ai_confidence_score`: Enable AI-powered confidence score calculation using GitHub Copilot (default: false).
  * When enabled, the system analyzes PRs to determine if they can be safely merged automatically.
  * Requires GitHub token with Copilot API permissions.
* `enable_ai_automerge_action`: Enable automatic merging for PRs with 100% confidence in development environments (default: false).
  * Only works when `enable_ai_confidence_score` is also enabled.
  * Auto-merge is restricted to development environments only.
  * Requires 100% confidence score for auto-merge.
* `disable_pr_comments`: Disable posting comments to PRs and print AI analysis only to terminal (default: false).
  * When enabled, AI confidence score analysis is printed to terminal instead of being posted as PR comments.
  * Useful for testing or when you want to avoid cluttering PRs with comments.
  * AI analysis is still performed and logged to terminal.
* `repos`: List of repositories to process for automerge and AI analysis (required).
  * These repositories are processed for standard merge and planning logic.
  * If `enable_ai_confidence_score` is enabled, AI analysis is performed for these repositories when PRs have diffs.
  * Can be empty to disable all processing.
* `ai_provider`: Choose the AI provider for confidence score calculation (default: "github").
  * Options: "github" (GitHub Copilot via proxy) or "claude-code" (Claude Code direct API).
  * Required when `enable_ai_confidence_score` is enabled.
* `ai_config`: Configuration for the selected AI provider.
  * **For GitHub Copilot**: Requires `api_base` (proxy URL) and `model` (model name).
  * **For Claude Code**: Requires `api_base` (API URL), `api_key` (Anthropic API key), and `model` (model name).
* `test_prs`: List of specific PRs to analyze for AI confidence score testing (optional).
  * Each test PR should be formatted as a dictionary with `repo` (string) and `pr_number` (integer) fields.
  * These PRs are analyzed regardless of their merge status when AI is enabled.
  * Useful for testing AI features on specific PRs.


### AI Provider Configuration

The tool supports two AI providers for confidence score calculation:

#### GitHub Copilot (via proxy)
```json
{
  "ai_provider": "github",
  "ai_config": {
    "github": {
      "api_base": "http://localhost:4141",
      "model": "claude-sonnet-4"
    }
  }
}
```

#### Claude Code (direct API)
```json
{
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_anthropic_api_key_here",
      "model": "claude-sonnet-4"
    }
  }
}
```

**Note:** If you encounter SSL certificate verification errors in local development environments, you can disable SSL verification by setting the environment variable:
```bash
export DISABLE_SSL_VERIFY=true
```
This should only be used in development/testing environments, never in production.

## GitHub Config
### Branch protection
If you [Require status checks from Atlantis to pass before merging](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/about-status-checks) on your [Branch protection rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule), make sure that the atlantis ones are set to `atlantis/plan` only.
Automerge will never apply anything (for now) so having an `atlantis/apply` check set as required will break the ability for automerge to merge pull requests.
This because automerge does not `bypass branch protections`. Before merging any pull request it waits that all checks are green.

### Codeowners
Since the GitHub user leveraged by Automerge has to be able to comment, approve and merge pull requests, depending on your GitHub configs it may be required to add such a user in the [codeowners](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners) file and also as writer for the repository.

## AI Confidence Score Feature

Automerge includes an AI-powered feature that analyzes pull requests to determine if they can be safely merged automatically. This feature uses GitHub Copilot to calculate confidence scores (0-100%) based on various factors.

### How It Works

1. **Context Extraction**: The system extracts relevant information from PRs:
   - Title and description
   - Repository and branch information
   - Labels
   - Terraform plan output from comments

2. **AI Analysis**: GitHub Copilot or Claude Code (setup) analyzes the PR context and provides a confidence score with explanation

3. **Environment Detection**: The system determines if the PR targets a development environment based on branch patterns

4. **Auto-Merge Logic**: Auto-merge is only enabled when:
   - `enable_ai_automerge_action` is set to `true`
   - The PR targets a development environment
   - The confidence score is exactly 100%

### Safety Rules

- **Production Protection**: Production/protected branches are never auto-merged
- **Development Only**: Only development environments can be auto-merged
- **100% Confidence**: Confidence score must be 100% for auto-merge
- **Fallback Logic**: System continues working even if AI is unavailable

### AI Repository Processing

The tool supports AI analysis for repositories specified in the `repos` list during the standard processing cycle:

1. **Standard Processing**: All repositories in the `repos` list are processed normally
   - PRs are categorized based on their state
   - Standard merge and planning logic applies

2. **AI Analysis**: When `enable_ai_confidence_score` is enabled and PRs have diffs:
   - AI confidence score analysis is performed
   - Auto-merge is applied if conditions are met (100% confidence + dev environment + `enable_ai_automerge_action` enabled)
   - Robust error handling for various failure scenarios

3. **Integration**: AI analysis is seamlessly integrated into the existing workflow
   - No separate processing cycles
   - No additional wait times
   - Maintains existing behavior when AI features are disabled

### AI Failure Handling

The system now provides detailed feedback when AI analysis cannot be performed:

- **No Plan Found**: When Atlantis hasn't generated a plan yet
- **Plan in Progress**: When Atlantis is still running the plan
- **Lock Conflicts**: When another PR has acquired the lock
- **Plan Errors**: When the Terraform plan contains errors
- **AI Service Errors**: When the AI service is unavailable

Each failure includes:
- Clear reason for the failure
- Detailed explanation
- Recommended action for resolution

### Example Output

The system adds a formatted comment to each analyzed PR:

```
🤖 **AI Confidence Score Analysis**

**Confidence Score:** 95%

**Explanation:** Safe provider update with no breaking changes

**Environment:** Development

**Auto-merge Status:** ❌ Disabled

---
*This analysis was performed by GitHub Copilot AI to assess the safety of automatic merging.*
```

### Environment Variables

You can also control the AI features via environment variables:

- `ENABLE_AI_CONFIDENCE_SCORE`: Override AI confidence score setting
- `ENABLE_AI_AUTOMERGE_ACTION`: Override AI auto-merge setting
- `LOG_LEVEL`: Set logging level (DEBUG, INFO, WARNING, ERROR)

### Logging Configuration

The tool supports detailed logging for debugging AI interactions:

```bash
# Enable debug logging via CLI
python -m src.main --config config.json --log_level DEBUG

# Enable debug logging via environment variable
export LOG_LEVEL=DEBUG
python -m src.main --config config.json
```

Debug logging will show:
- 🤖 AI API call details (URL, model, headers, payload)
- 🔍 PR analysis context (title, repository, branches, environment)
- 📝 Generated prompts and their length
- ✅ AI responses and parsing results
- 📊 Confidence scores and explanations
- 🔄 Fallback logic usage
- ❌ Error details and exceptions

### Terraform Plan Analysis

The AI confidence score calculation now specifically analyzes Terraform plans from the `tl-terraform` user:

- **Multi-comment Plans**: Handles plans split across multiple comments
- **Continuation Detection**: Recognizes "Continued plan output from previous comment." headers
- **Chronological Order**: Combines plan parts in the correct sequence
- **Latest Plan**: Always uses the most recent plan from the specified user

The system will:
1. Fetch all comments from the PR
2. Filter comments by the `tl-terraform` user
3. Sort by creation date (newest first)
4. Identify the latest complete plan (including continuations)
5. Combine all plan parts in chronological order
6. Remove continuation headers for clean output

### Test PRs Configuration

You can specify specific PRs for AI testing in your configuration:

```json
{
  "test_prs": [
    {
      "repo": "terraform-ops",
      "pr_number": 23680
    },
    {
      "repo": "terraform-aws",
      "pr_number": 123
    }
  ]
}
```

These PRs will be analyzed for AI confidence scores regardless of their merge status for testing the AI functionality.

### Error Handling

The system includes robust error handling:

- **AI Service Unavailable**: Falls back to pattern-based analysis
- **Network Errors**: Logs errors and continues with fallback
- **Invalid Responses**: Uses default confidence scores
- **Configuration Errors**: Disables AI features gracefully

### Testing AI Features

Run the AI feature tests:

```bash
python -m unittest tests.test_ai_confidence -v
```

## Usage Examples

### Complete Configuration with AI Integration

```json
{
  "access_token": "your_github_token",
  "filters": [
    "^\\[DEPENDENCIES\\] Update Terraform",
    "^\\[DEPENDABOT\\]"
  ],
  "github_user": "your_user",
  "owner": "your_org",
  "repos": [
    "terraform-vault",
    "terraform-aws",
    "terraform-ops",
    "terraform-k8s"
  ],
  "enable_ai_confidence_score": true,
  "enable_ai_automerge_action": true,
  "disable_pr_comments": false,
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_anthropic_api_key",
      "model": "claude-sonnet-4"
    }
  }
}
```

### When to use `disable_pr_comments: true`
- **Testing**: During development and testing of AI features
- **Debugging**: To analyze AI output without cluttering PRs
- **Development environments**: Where you don't want permanent comments on PRs
- **Batch analysis**: When analyzing many PRs and only wanting terminal results

### When to use `disable_pr_comments: false` (default)
- **Production**: When you want AI analysis to be visible to teams
- **Collaboration**: When other developers need to see AI analysis
- **Audit**: When you want to track AI decisions in PRs
- **Transparency**: When you want auto-merge decisions to be documented

## Embeddings-Based Similarity Analysis

Automerge now includes an advanced **embeddings-based similarity analysis** feature that uses Amazon Bedrock Titan Embeddings V2 to enhance AI confidence score calculations by comparing PRs against historical safe examples.

### How It Works

The embeddings service:

1. **Extracts PR Components**: For each PR, extracts:
   - File names and paths
   - File content and patches
   - Git diff
   - Terraform plan output

2. **Generates Embeddings**: Uses Amazon Bedrock Titan Embeddings V2 to generate high-dimensional vector representations of each component

3. **Caches in S3**: Stores embeddings in S3 for fast retrieval and reuse

4. **Similarity Comparison**: Compares the current PR against historical safe PRs using cosine similarity

5. **Boosts Confidence**: Applies a similarity boost to the AI confidence score when the PR is similar to previously merged safe PRs

### Configuration

Add the `embeddings` section to your config:

```json
{
  "embeddings": {
    "enabled": true,
    "s3_bucket": "automerge-embeddings-production",
    "aws_region": "eu-west-1",
    "similarity_boost_weight": 0.5,
    "max_cached_prs": 100,
    "force_recalculate": false
  }
}
```

**Configuration Options:**

- **`enabled`**: Enable/disable embeddings service (default: `false`)
- **`s3_bucket`**: S3 bucket name for storing embeddings (required when enabled)
- **`aws_region`**: AWS region for S3 and Bedrock (default: `"eu-west-1"`)
- **`similarity_boost_weight`**: Weight for similarity boost in score calculation (default: `0.5`, range: `0.0-2.0`)
- **`max_cached_prs`**: Maximum number of historical safe PRs to cache per repository (default: `100`)
- **`force_recalculate`**: Bypass cache and recalculate all embeddings - debug mode only (default: `false`)

### AWS Requirements

The embeddings service requires:

1. **AWS Credentials**: Available via environment variables, IAM role, or AWS config file
2. **S3 Permissions**:
   - `s3:PutObject` - Store embeddings
   - `s3:GetObject` - Retrieve embeddings
   - `s3:ListBucket` - List cached embeddings
   - `s3:DeleteObject` - Cleanup old embeddings

3. **Bedrock Permissions**:
   - `bedrock:InvokeModel` - Generate embeddings using Titan Embeddings V2

### Historical Safe PRs

The system identifies safe PRs using the GitHub label **`automerge-safe-example`**:

- Add this label to PRs that have been successfully merged and verified as safe
- The embeddings service will use these PRs as reference examples
- Supports up to 100 historical PRs per repository (configurable via `max_cached_prs`)
- Automatically handles pagination when fetching more than 100 PRs from GitHub

### Smart Caching and Optimization

The embeddings service includes several optimizations:

1. **S3 Cache**: Embeddings are cached in S3 to avoid recalculating for the same PR
2. **Automatic Cleanup**: Removes embeddings for PRs no longer labeled as safe examples
3. **Pagination Support**: Automatically handles GitHub API pagination for repositories with >100 safe PRs
4. **Skip When Unnecessary**: Skips embeddings calculation when no historical PRs exist
5. **Empty Component Handling**: Uses placeholder text for empty components (e.g., no terraform plan)

### Prometheus Metrics

The embeddings service automatically tracks token usage in Prometheus:

- **`automerge_embeddings_input_tokens`**: Number of input tokens used by Bedrock
  - Labels: `repo` (repository name), `model` (Bedrock model ID)
- Metrics are pushed to the configured Prometheus Pushgateway URL

### Debug Mode

Enable `force_recalculate` for debugging:

```json
{
  "embeddings": {
    "force_recalculate": true
  }
}
```

⚠️ **Warning**: This bypasses all caching and recalculates embeddings for all PRs on every run. Use only for debugging. This will significantly increase AWS costs.

### Cost Optimization

To optimize AWS costs:

1. Keep `force_recalculate` set to `false` (default)
2. Adjust `max_cached_prs` based on your needs (fewer = lower costs)
3. Use appropriate `similarity_boost_weight` to balance accuracy vs. computation
4. Label only truly representative PRs as `automerge-safe-example`

### Integration with AI Confidence Score

When both embeddings and AI confidence score are enabled:

1. AI analyzes the PR and generates a base confidence score
2. Embeddings service calculates similarity to historical safe PRs
3. Similarity boost is applied to the base score
4. Final boosted score is used for auto-merge decisions

The similarity boost is applied as:
```
boosted_score = base_score + (similarity * similarity_boost_weight * (100 - base_score))
```

### Example Configuration with Embeddings

```json
{
  "access_token": "your_github_token",
  "owner": "your_org",
  "repos": ["terraform-ops"],
  "enable_ai_confidence_score": true,
  "enable_ai_automerge_action": true,
  "ai_provider": "claude-code",
  "ai_config": {
    "claude-code": {
      "api_base": "https://api.anthropic.com",
      "api_key": "your_key",
      "model": "claude-sonnet-4"
    }
  },
  "embeddings": {
    "enabled": true,
    "s3_bucket": "automerge-embeddings-prod",
    "aws_region": "eu-west-1",
    "similarity_boost_weight": 0.5,
    "max_cached_prs": 100
  },
  "metrics_pushgateway_url": "http://localhost:9091"
}
```

### Troubleshooting

**No embeddings calculated:**
- Check that `embeddings.enabled` is `true`
- Verify AWS credentials are configured
- Ensure S3 bucket exists and has correct permissions
- Check that historical PRs have the `automerge-safe-example` label

**High AWS costs:**
- Ensure `force_recalculate` is `false`
- Reduce `max_cached_prs` if you have many historical PRs
- Verify S3 cache is working (check CloudWatch for Bedrock API calls)

**Bedrock API errors:**
- Check Bedrock permissions in IAM
- Verify the model ID `amazon.titan-embed-text-v2:0` is available in your region
- Ensure you're within Bedrock service quotas

## Configuration Options Summary

The tool now supports the following main configuration options:

- **`enable_ai_confidence_score`**: Enables AI analysis for repositories in the `repos` list when PRs have diffs
- **`enable_ai_automerge_action`**: Enables automatic merging for PRs with 100% confidence in development environments
- **`disable_pr_comments`**: When enabled, AI analysis is printed to console instead of posted as PR comments
- **`test_prs`**: Allows testing the tool on specific PRs specified as dictionaries with `{"repo": "", "pr_number": ""}`
- **`ai_provider`**: Chooses which AI provider to use (github or claude-code)
- **`ai_config`**: Contains configurations for the supported AI engines
- **`embeddings`**: Configuration for embeddings-based similarity analysis (optional)
- **`metrics_pushgateway_url`**: Prometheus Pushgateway URL for metrics (optional)

All other configuration options remain the same as before.

## Usage
### Options
```bash
options:
  -h, --help            show this help message and exit
  --config_file CONFIG_FILE
                        JSON file holding the GitHub access token, default is .config.json
  --approve_all         Approves all PRs that match the filters in the config
  --log_level {DEBUG,INFO,WARNING,ERROR}
                        Set logging level (DEBUG, INFO, WARNING, ERROR)
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

The Helm chart supports AI features via environment variables:

```yaml
job:
  env:
    - name: ENABLE_AI_CONFIDENCE_SCORE
      value: "false"
    - name: ENABLE_AI_AUTOMERGE_ACTION
      value: "false"
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

# Run AI confidence score tests
python -m unittest tests.test_ai_confidence -v

# Run test PRs tests
python -m unittest tests.test_test_prs -v
```

### Continuous Integration
The project uses GitHub Actions for CI/CD with:
- **Python Coverage Comment Action**: Automatically comments coverage reports on PRs
- **Multi-version testing**: Tests against Python 3.9, 3.10, 3.11, and 3.12
- **Code linting**: Uses Ruff for code quality checks
- **Coverage reporting**: Generates detailed coverage reports

Coverage reports are automatically generated and commented on pull requests, helping maintain code quality standards.

### Coverage Configuration

The project uses a `.coveragerc` file to configure coverage reporting:

```ini
[run]
source = src
relative_files = true
omit = tests/*, .venv/*, venv/*, */site-packages/*

[report]
show_missing = True
precision = 2

[html]
directory = htmlcov

[xml]
output = coverage.xml
```

Key settings:
- **`relative_files = true`**: Required for GitHub Actions integration
- **`source = src`**: Only measure coverage for source code
- **`omit`**: Exclude test files and virtual environments

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
├── test_conf.py            # Test utilities and mock objects
├── test_ai_confidence.py   # AI confidence score feature tests
└── test_test_prs.py        # Test PRs feature tests
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

This includes additional tools like:
- **pytest**: Alternative test runner
- **black**: Code formatter
- **mypy**: Type checking
- **pre-commit**: Git hooks
- **sphinx**: Documentation generation

### Development Workflow
1. Make your changes
2. Run tests: `python run_tests.py --full_no_web`
3. Fix any linting issues: `ruff check . --fix`
4. Commit your changes
5. Create a pull request (coverage will be automatically reported)

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
