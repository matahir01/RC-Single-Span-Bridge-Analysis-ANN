# BS EN design basis for the focused bridge application

## Primary code family

The Eurocode path in this repository is treated as a **British-adopted Eurocode (BS EN)** path, not as an unidentified generic EN profile.

For the present V1 verification campaign the pinned first-generation bridge basis is:

- **BS EN 1990:2002+A1:2005** — basis of structural design, including the bridge amendment;
- **BS EN 1991-2:2003** — traffic loads on bridges;
- **BS EN 1992-2:2005** — concrete bridges, design and detailing rules;
- BS EN 1992-1-1 provisions where BS EN 1992-2 calls them up.

This is deliberate. BSI currently lists the first-generation BS EN 1990 and BS EN 1992-2 documents as current during the Eurocode transition period and states that first-generation documents remain the applicable UK basis until 30 March 2028 unless the relevant authority or project specification says otherwise. The existing JRC worked examples and the present engine equations are also first-generation Eurocode based. Mixing second-generation clauses into this verified first-generation path is therefore prohibited unless a future migration is carried out as a separate, explicit code profile.

## Nationally Determined Parameters

`BS EN` does **not** mean that UK National Annex values are silently assumed for every project. The British Standard adoption and the UK National Annex are separate pieces of the design basis.

For Nigerian work:

1. the engine identifies the base code as BS EN;
2. Nationally Determined Parameters remain explicit project inputs;
3. a UK National Annex value may be selected only when the client, approving authority or project specification adopts that basis;
4. where no project National Annex is supplied, recommended Eurocode/JRC values may be used only as an explicitly recorded design assumption, never labelled as a Nigerian National Annex.

Relevant UK companion documents include **NA+A1:2020 to BS EN 1991-2:2003** for bridge traffic actions and **NA to BS EN 1992-2:2005** for concrete bridges. They are selectable reference bases, not hidden defaults.

## Relationship to the legacy BS profile

The existing **BS 5400 / BD 37/01** implementation is retained because it is useful for legacy Nigerian/UK-style bridge work, historical calculations and independent cross-checking. It is not to be blended numerically with the BS EN profile.

The software therefore keeps two distinct routes:

- **Primary modern route:** BS EN 1990 / BS EN 1991-2 / BS EN 1992-2;
- **Legacy route:** BS 5400 / BD 37/01.

Material strengths, traffic rules, partial factors, serviceability factors and detailing rules must stay traceable to the selected route. No automatic conversion between BS cube-strength conventions and BS EN cylinder-strength conventions is permitted.

## Verification consequence

All remaining Eurocode-source verification work in V1 is to be recorded against the **BS EN** designation. The JRC bridge worked examples remain valid independent worked examples of the underlying EN provisions, while BSI publications establish the British-adopted standard identity and transition basis. Any project-specific UK National Annex choice is to be reported separately from the core BS EN rule being checked.
