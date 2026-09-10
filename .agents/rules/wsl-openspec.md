---
trigger: always_on
---
# WSL Execution, Package Manager & OpenSpec Environment Rules

## 1. Environment & Execution
- Windows is the HOST ONLY. Do not create or write code/files into Windows paths.
- All projects, files, and tools live inside WSL (Ubuntu distro).
- Primary projects root: `/home/asus/Projects/` (e.g. `/home/asus/Projects/GeoFoundation`).
- Python / Conda environment: `/home/asus/miniforge3/envs/geospatial` (Miniforge base at `/home/asus/miniforge3`).
- Commands must be executed inside WSL using: `wsl -d Ubuntu bash -c "source /home/asus/miniforge3/bin/activate geospatial && cd <project_dir> && <command>"`.

## 2. Package Manager Hierarchy (Strict Precedence)
- **Always prefer `bun`** as the primary JavaScript / TypeScript package manager and runtime.
  - Path: `/home/asus/.bun/bin/bun`
  - For installing agent skills: `bunx skills add <skill-name>` or `bun add`
- **Second choice**: `pnpm` (if `bun` cannot be used or repository specifically requires pnpm lockfile).
- **Last choice**: `npm` only when neither `bun` nor `pnpm` is supported.

## 3. Specification-Driven Workflow
- Always adhere to the OpenSpec specification-driven workflow (`openspec/`) for planning, proposal creation, task tracking, and implementation.
