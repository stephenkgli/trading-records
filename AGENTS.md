## Workflow

IMPORTANT: Every code change MUST go through all steps below：

1. **Write code** - implement the change
2. **Run tests** - ensure all tests pass
3. **Verify locally** - validate the change actually works in the running dev environment:
   - Frontend: use the `agent-browser` skill to open pages, click through UI, take screenshots, and visually confirm behavior
   - Backend: call API endpoints directly (via `curl`) to verify response data
   - Database: execute SQL queries against PostgreSQL to verify data integrity
4. **If issues found** - fix and repeat from step 2 until no remaining issues
5. **Optimize** - use the `code-simplifier:code-simplifier` agent to review and optimize all changed code for clarity, consistency, and maintainability

YOU MUST NOT consider a task complete until step 5 is done.

## Skill Compliance

IMPORTANT: The following skills MUST be consulted for their respective domains:

- **Database changes** (schema, queries, migrations): Follow `supabase-postgres-best-practices` skill strictly. This includes query performance, indexing, RLS, connection management, and schema design.
- **Frontend code** (React components, hooks, data fetching, performance): Follow `vercel-react-best-practices` and `vercel-composition-patterns` skills. This covers re-render optimization, bundle size, component architecture, and state management.
- **UI/UX design** (layout, styling, accessibility, interactions): Follow `web-design-guidelines` and `frontend-design` skills. This covers accessibility, visual consistency, and production-grade design quality.
