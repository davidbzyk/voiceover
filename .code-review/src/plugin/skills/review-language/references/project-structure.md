# Project structure and config conventions per stack
### Build Artifact Directories (always flag if tracked in git)

| Pattern | Stacks | Severity |
|---------|--------|----------|
| `dist/` | All JS/TS | HIGH |
| `build/` | All | HIGH |
| `bin/` | .NET, Go | HIGH |
| `obj/` | .NET | HIGH |
| `__pycache__/` | Python | HIGH |
| `.next/` | Next.js | HIGH |
| `.nuxt/` | Nuxt | HIGH |
| `target/` | Rust, Java | HIGH |
| `out/` | Go, Next.js | HIGH |
| `node_modules/` | All JS/TS | HIGH |
| `.venv/`, `venv/` | Python | HIGH |
| `coverage/` | All JS/TS | MEDIUM |
| `.pytest_cache/` | Python | MEDIUM |

### .gitignore Required Entries by Stack

| Stack | Required Entries |
|-------|-----------------|
| Node.js/TS | `node_modules/`, `dist/`, `.env`, `coverage/`, `*.log` |
| React | + `build/` |
| Next.js | + `.next/`, `out/` |
| Vue | + `.nuxt/` (Nuxt), `dist/` |
| Python | `__pycache__/`, `*.pyc`, `.venv/`, `.env`, `*.egg-info/`, `.pytest_cache/` |
| .NET | `bin/`, `obj/`, `*.user`, `.vs/`, `*.suo` |
| Go | `vendor/` (if unused), `*.exe`, `*.test` |
| Java | `target/`, `*.class`, `.settings/`, `.project` |
| Rust | `target/`, `Cargo.lock` (libraries only) |
## Framework Convention Rules

### React / Vite / CRA / Next.js


| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `src/components/` | Reusable UI components | Required |
| `src/pages/` OR `app/` | Route pages | Required |
| `src/hooks/` | Custom hooks | Recommended |
| `src/contexts/` OR `src/store/` | State management | Recommended |
| `src/lib/` OR `src/utils/` | Utilities | Recommended |
| `src/types/` | TypeScript types | Recommended (TS only) |
| `public/` | Static assets | Required |

**Forbidden placements:**
- React components (`*.tsx` with JSX) outside `src/`
- API route handlers in `src/components/`

**Co-location rules:**
- Feature folder pattern: `src/pages/{Feature}/` contains `index.tsx`, `types.ts`, `hooks.ts`, `components/`
- Component co-location: component + test + styles together

### .NET / ASP.NET Core / Clean Architecture


| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `{Project}.Api/Controllers/` | HTTP endpoints | Required |
| `{Project}.Api/DTOs/` | Request/Response DTOs | Required |
| `{Project}.Domain/Entities/` | Business entities | Required |
| `{Project}.Services/` | Business logic | Required |
| `{Project}.Repositories/` | Data access | Required |
| `{Project}.Shared/` | Cross-cutting concerns | Recommended |

**Forbidden placements:**
- Domain entities in Api/ project
- Direct DB access from Controllers/

### Python / FastAPI / Django / Flask

| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `src/` OR `{package}/` | Source root | Required |
| `tests/` | Test directory | Required |
| `src/api/` OR `src/routes/` | API endpoints | Recommended (FastAPI/Flask) |
| `src/models/` | Data models | Recommended |
| `src/services/` | Business logic | Recommended |
| `{app}/models.py` | Django models | Required (Django) |
| `{app}/views.py` | Django views | Required (Django) |

**Special:** `__init__.py` required in all packages (src layout)

### Go

| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `cmd/` | Entry points (main packages) | Required (multi-binary) |
| `internal/` | Private packages | Required |
| `pkg/` | Public/reusable packages | Optional |
| `api/` | API definitions (proto, swagger) | Recommended |

**Forbidden placements:**
- Source files directly in repo root (except `main.go` for single-binary)
- Test files outside their package directory

### Node.js / Express / NestJS

| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `src/routes/` OR `src/controllers/` | HTTP handlers | Required |
| `src/services/` | Business logic | Required |
| `src/models/` OR `src/entities/` | Data models | Recommended |
| `src/middleware/` | HTTP middleware | Recommended |
| `src/modules/` | NestJS modules | Required (NestJS) |

### Rust

| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `src/` | Source code | Required |
| `src/bin/` | Binary targets | Recommended (multi-binary) |
| `tests/` | Integration tests | Recommended |
| `benches/` | Benchmarks | Optional |

### Generic Fallback (unknown framework)

| Expected Directory | Purpose | Required? |
|--------------------|---------|-----------|
| `src/` | Source code | Required |
| `tests/` OR `test/` | Tests | Required |
| `docs/` | Documentation | Recommended |
| `config/` | Configuration | Recommended (if >5 config files in root) |
## Naming Convention Rules

| Stack | File Case | Dir Case | Test Pattern | Component Case |
|-------|-----------|----------|--------------|----------------|
| React/Vue | PascalCase (`.tsx`/`.vue`), camelCase (`.ts`) | lowercase / kebab-case | `*.test.tsx`, `*.spec.tsx` | PascalCase |
| Angular | kebab-case (`*.component.ts`) | kebab-case | `*.spec.ts` | PascalCase |
| .NET | PascalCase | PascalCase | `*Tests.cs` | PascalCase |
| Python | snake_case | snake_case | `test_*.py`, `*_test.py` | PascalCase (classes) |
| Go | snake_case | lowercase (no underscores) | `*_test.go` | PascalCase (exported) |
| Node.js/TS | camelCase or kebab-case | kebab-case or camelCase | `*.test.ts`, `*.spec.ts` | N/A |
| Rust | snake_case | snake_case | `#[test]` in-file, `tests/` dir | PascalCase (structs) |
| Java | PascalCase | lowercase dot-separated | `*Test.java` | PascalCase |

### Allowed Root Files (not flagged as source-in-root)

| Stack | Allowed Root Source Files |
|-------|--------------------------|
| Node.js/TS | `index.ts`, `main.ts`, `app.ts`, `server.ts` |
| Python | `manage.py`, `wsgi.py`, `asgi.py`, `main.py`, `setup.py` |
| .NET | `Program.cs` |
| Go | `main.go` |
| Rust | `main.rs`, `lib.rs` (in `src/`) |
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
## Validation Frameworks

| Stack | Framework | Detection Pattern |
|-------|-----------|-------------------|
| Python | pydantic-settings | `from pydantic_settings import\|from pydantic import BaseSettings` |
| Python | environs | `from environs import Env` |
| Node.js | envalid | `require\(['"]envalid['"]\)\|from ['"]envalid['"]` |
| Node.js | zod (env) | `z\.object.*env\|createEnv` |
| Node.js | @t3-oss/env | `from ['"]@t3-oss/env` |
| .NET | IOptions | `services\.Configure<\|IOptions<` |
| Go | envconfig | `envconfig\.Process` |
| Go | viper | `viper\.AutomaticEnv\|viper\.BindEnv` |
| Java | Spring | `@Value\("\$\{` |
| Ruby | dotenv | `Dotenv\.load\|require ['"]dotenv['"]` |

## Framework-Managed Variables (Layer 2 Exclusions)

Exclude from C2.1 (Code→Example sync) — these are auto-set by frameworks:

| Framework | Auto-Managed Vars |
|-----------|-------------------|
| Node.js | `NODE_ENV`, `PORT` |
| Next.js | `NEXT_PUBLIC_*` prefix, `NEXT_RUNTIME`, `NEXT_PHASE` |
| Vite | `VITE_*` prefix, `MODE`, `BASE_URL`, `PROD`, `DEV` |
| Python/Django | `DJANGO_SETTINGS_MODULE` |
| Python/Flask | `FLASK_APP`, `FLASK_ENV`, `FLASK_DEBUG` |
| .NET | `ASPNETCORE_ENVIRONMENT`, `ASPNETCORE_URLS`, `DOTNET_ENVIRONMENT` |
| Go | `GOPATH`, `GOROOT`, `GOPROXY` |
| Ruby/Rails | `RAILS_ENV`, `RACK_ENV` |
| Java/Spring | `SPRING_PROFILES_ACTIVE` |
| Docker | `HOSTNAME`, `HOME`, `PATH` |
