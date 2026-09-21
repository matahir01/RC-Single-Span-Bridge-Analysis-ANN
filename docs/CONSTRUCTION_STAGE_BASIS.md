# Construction-Stage Analysis Basis

For the V1 single-span composite RC girder bridge, construction-stage analysis is part of the core deterministic model.

## Required V1 sequence

### Stage 1 — precast girder
Active longitudinal section: precast girder only.

Typical actions applied in this state:
- precast girder self-weight;
- erection-stage items that are physically present before deck casting;
- precast false-slab weight when it is placed on the girder and is not structurally composite.

The wet in-situ slab must not contribute stiffness in this state.

### Stage 2 — deck construction
Active longitudinal section: precast girder plus only any explicitly verified construction-stage composite elements.

Typical new actions:
- wet in-situ deck concrete;
- construction-stage deck loads that are actually present.

By default the 75 mm false slab is weight-only and the 175 mm wet in-situ slab does not contribute composite stiffness until hardened.

### Stage 3 — final hardened composite bridge
Active longitudinal section: final composite girder/deck section.

Typical new actions:
- surfacing;
- barriers/parapets;
- services and other superimposed permanent actions;
- traffic and code-specific service/ultimate combinations.

The hardened participating slab may contribute to the final composite section.

## Superposition rule

Each load increment is analysed using the stiffness and section state that exists when that load is introduced. Earlier permanent actions are not re-applied to the final composite stiffness.

The final permanent response is the signed sum of the stage increments. This is important for construction safety, stress history and service deflection.

## What V1 does not attempt

The first verified implementation is intentionally limited to unpropped construction with unchanged supports and unchanged simple-span continuity.

The following require a separate future model and must not be silently approximated:
- temporary props and prop removal;
- changing supports or bearings during construction;
- continuity established after erection;
- creep/shrinkage redistribution;
- age-dependent modulus and detailed time stepping;
- nonlinear cracking history;
- staged prestressing;
- local formwork or falsework design.

Unsupported assumptions must be reported explicitly rather than hidden behind a generic construction-stage switch.
