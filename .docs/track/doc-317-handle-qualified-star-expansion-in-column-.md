# Track: DOC-317 qualified star expansion in column lineage

Track: technical

Scope boundary: Broad — rework star handling in column lineage end to end. In scope: qualified
single-source stars (`renamed.*`), multi-star joins (`a.*, b.*`), the phantom `'*'` output column
name, qualified-star `EXCLUDE`, and reshaping `build_schema_mapping` to the nested form
`qualify()` requires. Retaining the `known_columns` catalog fallback is in scope and required.
Out of scope: any change to the lineage cache format, the frontend, or the analyzer's
parallelism.

Bug fix restoring intended parser behavior; no new user-facing capability and no product
requirements worth a PRD, so acceptance criteria live directly in stories.
