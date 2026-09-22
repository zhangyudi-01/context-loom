# Writing a domain workflow

A domain workflow should define:

1. What its Task Unit means.
2. What sources and context are authoritative.
3. How complexity is judged.
4. The result schema and validation rules.
5. The final artifact and traceability fields.

It should not reimplement source fingerprinting, atomic state, generic packet routing, or result
assembly. Add a Skill under `skills/<domain>/`, a domain payload contract under `schemas/`, and an
adapter test that exercises the generic lifecycle.

