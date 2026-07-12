---
name: ptx-isa
description: "The complete NVIDIA PTX ISA 9.3 specification, split into greppable markdown. Use when writing, reading, or generating PTX: instruction syntax and semantics, operand types, state spaces, special registers, TensorCore operations (WMMA, WGMMA, tcgen05), async copy and TMA, the memory consistency model, and directives. Triggers on PTX, inline PTX, asm volatile, ptxas, cuobjdump -ptx, mma/wgmma/tcgen05, cp.async, mbarrier, .reg/.shared/.global state spaces, sreg, and questions about what a PTX instruction means or which targets support it."
---

# PTX ISA 9.3

The full specification is in `ptx/`, one file per section, 485 files.
Search it; do not read it whole. Every fact about PTX semantics you need is in
there, and guessing at PTX semantics produces code that assembles and then
misbehaves.

## How to find things

Sections are numbered exactly as in the spec, and filenames carry the number, so
a citation like "9.7.4.3" maps directly to a path:

```bash
find ptx -name '9.7.4.3-*'
```

Grep the whole spec when you know the mnemonic or keyword:

```bash
grep -rl 'cp.async.bulk.tensor' ptx/
grep -rn 'swizzle' ptx/9-instruction-set/ | head
```

`INDEX.md` lists every section in document order — read it when you need to
orient yourself in a chapter you don't know.

## The chapters

| Chapter | What lives there |
|---|---|
| `4-syntax` | Statement grammar, operand syntax, comments |
| `5-state-spaces-types-and-variables` | `.reg`, `.shared`, `.global`, `.const`, `.param`, `.local`, `.tmem`; types; arrays; alignment |
| `6-instruction-operands` | Operand forms, addressing, type-checking rules |
| `8-memory-consistency-model` | Scopes, ordering, `fence`, `.acquire`/`.release`, async proxies |
| `9-instruction-set` | Every instruction. The bulk of the spec. |
| `10-special-registers` | `%tid`, `%ctaid`, `%laneid`, `%clock`, ... |
| `11-directives` | `.version`, `.target`, `.entry`, `.func`, `.maxntid`, `.pragma` |
| `13-release-notes` | Which ISA version introduced or changed an instruction |

Instruction semantics live under `9-instruction-set/9.7-*`, grouped by class:
integer, floating point, comparison and selection, logic, movement and
conversion, texture, surface, control flow, parallel synchronization, warp-level
matrix multiply (WMMA/WGMMA), and tensor-core Gen5 (`tcgen05`).

## Figures

The spec's diagrams are in `ptx/_images/`, referenced from the sections that use
them, and they are part of the content rather than decoration: the register
fragment layouts for `mma`/`wgmma`, the TMA swizzling modes, and the tensor
memory maps exist *only* as figures. When a section points at one, open it —
the surrounding prose does not restate what the diagram shows.

## Reading an instruction section

Each instruction section states, in order: syntax (all operand forms), a
description, semantics (pseudocode), notes, the PTX ISA version that introduced
it and any that changed it, target architecture support, and examples. Two of
those are load-bearing and easy to skip:

- **PTX ISA version** — an instruction documented here may not exist in the ISA
  version you are targeting with `.version`.
- **Target ISA notes** — an instruction may require `sm_90a`/`sm_100a` and be
  unavailable, or silently different, elsewhere.

Check both before using an instruction you have not used before. `.target
sm_90a` is architecture-*specific*: code built for it does not run on `sm_100`.

## Release notes as a lookup

To find when something appeared, grep the release notes rather than reading the
instruction section's history line:

```bash
grep -rn 'tcgen05' ptx/13-release-notes/
```

## Version

This tree is PTX ISA 9.3; `VERSION.json` records the exact source.
The spec is versioned independently of CUDA — check `.version` in generated PTX
against the ISA version documented here before trusting a semantics question.
