# Dashboard Affordances

Use this before answering "I cannot see this in the dashboard" or "how do I
inspect X-Ray?" Dashboard behavior depends on file type and state. Offer the
no-code path before SDK or REST fallback when the UI already exposes one.

| File or state | Dashboard affordance | API fallback |
| --- | --- | --- |
| PDF or image-backed document with visual output | X-Ray viewer or source-view surface when available. | `document_getxray` or `xrayUrl` for the full X-Ray payload. |
| `.xlsx` | Viewer may not render a page-style X-Ray. Use **Download** when available to retrieve raw X-Ray JSON. | `document_getxray` or `xrayUrl`. |
| `.docx` | Viewer may not render a page-style X-Ray. Use **Download** when available to retrieve raw X-Ray JSON. | `document_getxray` or `xrayUrl`. |
| Non-visual or converted formats | Prefer **Download** for raw X-Ray JSON if the dashboard exposes it. | `document_getxray` or `xrayUrl`. |
| Ingest not complete | Dashboard controls may be absent or stale until processing reaches `complete`. | Poll `document_getprocessingstatusbyid`. |

## Answer Pattern

For dashboard availability questions:

1. Name the likely file type or state assumption.
2. Offer the no-code dashboard affordance first: viewer, source card, or
   **Download** for raw X-Ray JSON.
3. Then give the API fallback with `document_getxray` or `xrayUrl`.

Keep the answer short. A dashboard question usually needs a path, not a full SDK
tutorial.
