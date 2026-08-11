# Pi Agent provenance

ArcVellum Pi Worker is an ArcVellum-specific bounded worker built against the
public Pi packages listed below. The implementation was developed in the
ArcVellum Pi research fork and then moved into the Studio repository so its
runtime, tests, release lifecycle, and security boundary can be maintained with
the product that executes it.

- Upstream project: `https://github.com/earendil-works/pi`
- ArcVellum research fork: `ssh://git@ssh.github.com:443/o-1717986918/arcvellum-pi-agent.git`
- Source transfer commit: `c13e393bce74770d16cf1306bd9358d8e7f95e79`
- `@earendil-works/pi-agent-core`: `0.84.1`
- `@earendil-works/pi-ai`: `0.84.1`
- License: MIT; see `PI-AGENT-LICENSE.txt`

Release builds must use the exact dependency versions and integrity hashes in
`workers/pi-worker/package-lock.json`. Updating Pi dependencies requires Worker
tests, the continuous user-path E2E, provenance regeneration, and a new release.
