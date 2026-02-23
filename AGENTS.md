# AGENTS

## Repository scope

This is a monorepo with:

- Backend API at repository root.
- Frontend Admin Console at `frontend/`.

## Backend working rules

- Run backend quality checks with `./scripts/quality.sh check`.
- Keep API response contracts stable unless an explicit versioned change is requested.
- Do not remove legacy `/api/secrets/kv` endpoints.

## Frontend working rules

- Run frontend checks with:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run build`
- Frontend talks to backend using `VITE_API_BASE_URL` (defaults to `/api`).

## Docker workflows

- Full stack: `docker compose up -d --build`
- Frontend: `http://localhost:8080`
- Backend API via proxy: `http://localhost:8080/api`
- Backend API direct: `http://localhost:5000/api`

## Knowledge

- When you have access to MCP tools like DeepWiki, use them to investigate the `bearlike/Simple-Secrets-Manager` repository directly. 
  - Ask targeted questions about the codebase to understand how it works. You can use DeepWiki for any open source repository.  
  - Focus specifically on the open-source, publicly available GitHub repository. This lets you dig into the implementation details without guessing.
- Always test and lint the codebase after changes.
- Playwright MCP tool, when accessible, can be used for testing front-end components and changes. 
- Always scan related components to ensure consistency. Keep things stupid simple (KISS) and don't repeat yourself (DRY). This prevents code bloat. We need to avoid overengineering.


## Conventional Commit Guidelines 

Only use when asked to commit.

Commit Message Format
```
<gitmoji> <type>(<scope/project/lib>): <description>
empty line as separator
<optional body>
empty line as separator
<optional footer>
```

Type Reference
--------------
| Type | Title | Emoji | Description | Example Scopes (non-exaustive) |
| --- | --- | --- | --- | --- |
| build | Builds | 🏗️ | Changes that affect the build system or external dependencies | gulp, broccoli, npm |
| chore | Chores | 🔧 | Other changes that don't modify src or test files | scripts, config |
| ci | Continuous Integrations | 👷 | Changes to our CI configuration files and scripts | Travis, Circle, BrowserStack, SauceLabs,github actions, husky |
| docs | Documentation | 📝 | Documentation only changes | README, API |
| feat | Features | ✨ | A new feature | user, payment, gallery |
| fix | Bug Fixes | 🐛 | A bug fix | auth, data |
| perf | Performance Improvements | ⚡️ | A code change that improves performance | query, cache |
| refactor | Code Refactoring | ♻️ | A code change that neither fixes a bug nor adds a feature | utils, helpers |
| revert | Reverts | ⏪️ | Reverts a previous commit | query, utils, |
| style | Styles | 💄 | Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc) | formatting |
| test | Tests | ✅ | Adding missing tests or correcting existing tests | unit, e2e |
| i18n |  | 🌐 | Internationalization | locale, translation |

### Workflow

**Follow these steps:**

1. Run `git status` to review changed files.
2. Run `git diff` or `git diff --cached` to inspect changes.
3. Stage your changes with `git add <file>`.
4. Construct your commit message using the following XML structure.
5. After generating your commit message, Copilot will automatically run the following command in your integrated terminal (no confirmation needed):

```bash
git commit -m "type(scope): description"
```

6. Just execute this prompt and Copilot will handle the commit for you in the terminal.

### Commit Message Structure

```xml
<commit-message>
	<type>feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert</type>
	<scope>(api|frontend|cli|...)</scope> What core project/lib is being worked on
	<description>A short, imperative summary of the change.</description>
	<body>(optional: more detailed explanation)</body>
	<footer>(optional: e.g. BREAKING CHANGE: details, or issue references)</footer>
</commit-message>
```

### Examples

```xml
<examples>
	<example>✨ feat(api): add ability to parse arrays</example>
	<example>🐛 fix(frontend): correct button alignment</example>
	<example>📝  chore(docs): update README with usage instructions</example>
	<example>♻️ refactor(database): improve performance of data processing</example>
	<example>🔧 chore(api): update dependencies</example>
</examples>
```

### Validation

```xml
<validation>
        <gitmoji>✨| 🐛 | ⚡️|🚨 |etc</gitmoji>
	<type>Must be one of the allowed types. See <reference>https://www.conventionalcommits.org/en/v1.0.0/#specification</reference></type>
	<scope>Optional, but recommended for clarity.</scope>
	<description>Required. Use the imperative mood (e.g., "add", not "added").</description>
	<body>Optional. Use for additional context.</body>
	<footer>Use for breaking changes or issue references.</footer>
</validation>
```

### Final Step

```xml
<final-step>
	<cmd>git commit -m "type(scope): description"</cmd>
	<note>Replace with your constructed message. Include body and footer if needed.</note>
</final-step>
```

