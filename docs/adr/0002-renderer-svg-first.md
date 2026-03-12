# ADR 0002: SVG-first Render Tree

- Status: accepted
- Context: the product needs predictable typography, editable layout trees and parity between preview and export.
- Decision: adopt an SVG-friendly layout tree as the canonical representation for creative pages.
- Consequences: preview and export engines will share the same tree; raster output becomes a derived artifact, never the source of truth.
