# Language-specific notes

## Tech Stack Specific Notes

### Node.js/TypeScript
- **ORM Security:** Prisma auto-sanitizes, but check raw queries
- **Template Engines:** EJS `<%=` escapes, `<%-` does not
- **Validation:** Prefer Zod for type-safe validation

### Python
- **Django:** Uses parameterized queries by default, but check `.raw()` and `.extra()`
- **Flask:** No built-in ORM, always validate input manually
- **FastAPI:** Pydantic validation built-in, but check custom validators

### Go
- **SQL:** Use `database/sql` with placeholders `?` or `$1`
- **Templates:** `html/template` auto-escapes, `text/template` does not
- **Validation:** Use `go-playground/validator`

### Java/Spring
- **Hibernate:** Parameterized by default, check native queries
- **Templates:** Thymeleaf escapes by default, check `th:utext`
- **Validation:** Use Bean Validation (`@Valid`, `@NotNull`, etc.)
