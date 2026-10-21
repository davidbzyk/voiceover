# Environment configuration detection

## Env Var Usage Patterns by Language

| Language | Pattern | Capture Group | Notes |
|----------|---------|---------------|-------|
| JavaScript/TypeScript | `process\.env\.(\w+)` | $1 | Direct access |
| JavaScript/TypeScript | `process\.env\[['"](\w+)['"]\]` | $1 | Bracket access |
| Python | `os\.getenv\(['"](\w+)['"]` | $1 | With optional default |
| Python | `os\.environ\[['"](\w+)['"]\]` | $1 | KeyError if missing |
| Python | `os\.environ\.get\(['"](\w+)['"]` | $1 | Safe access |
| Go | `os\.Getenv\(['"](\w+)['"]` | $1 | Returns empty string if missing |
| .NET | `Environment\.GetEnvironmentVariable\(['"](\w+)['"]` | $1 | |
| .NET | `Configuration\[['"](\w+)['"]\]` | $1 | IConfiguration access |
| Java | `System\.getenv\(['"](\w+)['"]` | $1 | |
| Ruby | `ENV\[['"](\w+)['"]\]` | $1 | Direct access |
| Ruby | `ENV\.fetch\(['"](\w+)['"]` | $1 | Raises if missing |
| Rust | `env::var\(['"](\w+)['"]` | $1 | std::env |

### Pydantic Settings (Layer 2)

Pydantic `BaseSettings` maps field names to env vars automatically:

```python
class Settings(BaseSettings):
    database_url: str       # → DATABASE_URL
    api_key: str            # → API_KEY
    model_config = SettingsConfigDict(env_prefix="APP_")  # → APP_DATABASE_URL
```

Detection: Grep `class\s+\w+\(.*BaseSettings\)` → read class body → extract field names → convert to SCREAMING_SNAKE_CASE → add `env_prefix` if present.

## Docker/CI Env Patterns

| Source | Section/Directive | Detection Pattern |
|--------|-------------------|-------------------|
| `docker-compose.yml` | `environment:` | `^\s+environment:` then `\s+\w+=` or `\s+- \w+=` |
| `docker-compose.*.yml` | Override files | Same as above |
| `Dockerfile` | `ENV` directive | `^ENV\s+(\w+)` |
| `Dockerfile` | `ARG` directive | `^ARG\s+(\w+)` |
| `.github/workflows/*.yml` | `env:` section | `^\s+env:` then `\s+\w+:` |
| `.gitlab-ci.yml` | `variables:` | `^variables:` then `\s+\w+:` |
