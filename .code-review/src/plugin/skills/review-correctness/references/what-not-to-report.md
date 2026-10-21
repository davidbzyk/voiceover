**Auto-generated files:** If the diff contains generated files (protobuf stubs, OpenAPI clients,
ORM migrations, lock files, minified bundles), skip those files entirely. Generated code reflects
tool choices, not developer decisions. Note in the report which files were skipped and why.

   - Do not widen a repository contract with an assumed deployment topology or process lifetime. Retain such a risk only when repository evidence establishes the operating condition and a material consequence; an imagined configuration is not an unresolved project risk.

6. **Findings don't duplicate linter output.** Don't flag things the project's linter/formatter would catch (missing semicolons, wrong indentation). Focus on semantic issues.

- **Internal refactors that don't change public interface** -- renaming private methods, restructuring internal data flow, changing implementation details behind a stable API. If the contract is unchanged, it's not your concern.

- **Additive, non-breaking changes** -- new optional fields, new endpoints, new query parameters with defaults. These extend the contract without breaking it.

- Nullable column additions, new tables with defaults, indexes on new/small tables
- Test-only fixtures, seeds, or test DB setup
- Purely additive schema with no existing-row interaction
- Schema drift concerns when neither `db/schema.rb` nor `db/structure.sql` is in the diff

- **Micro-optimizations in cold paths** -- startup code, migration scripts, admin tools, one-time initialization. If it runs once or rarely, the performance doesn't matter.
- **Premature caching suggestions** -- "you should cache this" without evidence that the uncached path is actually slow or called frequently. Caching adds complexity; only suggest it when the cost is clear.
- **Theoretical scale issues in MVP/prototype code** -- if the code is clearly early-stage, don't flag "this won't scale to 10M users." Flag only what will break at the *expected* near-term scale.
- **Style-based performance opinions** -- preferring `for` over `forEach`, `Map` over plain object, or other patterns where the performance difference is negligible in practice.

- **Internal pure functions that can't fail** -- string formatting, math operations, in-memory data transforms. If there's no I/O, there's no reliability concern.

- **Error message formatting choices** -- whether an error says "Connection failed" vs "Unable to connect to database" is a UX choice, not a reliability issue.
- **Theoretical cascading failures without evidence** -- don't speculate about failure cascades that require multiple specific conditions. Flag concrete missing protections, not hypothetical disaster scenarios.

- Pre-existing issues
- Something that looks like a bug but is not actually a bug
- Pedantic nitpicks that a senior engineer wouldn't call out
- Issues that a linter, typechecker, or compiler would catch (eg. missing or incorrect imports, type errors, broken tests, formatting issues, pedantic style issues like newlines). No need to run these build steps yourself -- it is safe to assume that they will be run separately as part of CI.
- General code quality issues (eg. lack of test coverage, general security issues, poor documentation), unless explicitly required in CLAUDE.md

- Changes in functionality that are likely intentional or are directly related to the broader change
- Real issues, but on lines that the user did not modify in their pull request

    **DON'T:**
    - Say "looks good" without checking
    - Mark nitpicks as Critical
    - Give feedback on code you didn't actually read
    - Be vague ("improve error handling")

If you identify a high risk finding, but the intent of the branch is to introduce that finding – e.g. break some functionality, remove a feature flag, remove a safeguard – AND the scope of the change is well constrained, you SHOULD NOT waste the author's time by reporting the issue to them. However, if you believe it is likely that they are not aware of the full implications of their change, or you are worried that they are under-weighting the negative impacts (extreme example: a developer pushes a PR titled "Delete the database"), or you are worried that the change is actually malicious, you should still report the finding.
