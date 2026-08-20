# VoxFlow Agent Guide

This repository builds narrated editorial paper-collage videos from a Chinese script.

## Required workflow

1. Read `~/.codex/skills/vox-director/SKILL.md`, especially the prompt and beat references.
2. For MiniMax H3 prompts, read `~/.codex/skills/h3-prompt-writing/SKILL.md` and use I2VA for a single first-frame reference.
3. For collage motion and physical constraints, consult `~/.codex/skills/paper-collage-explainer-generator/SKILL.md`.
4. Run `scripts/voxflow.ps1 doctor` before billable work.
5. Create or review `projects/<name>/beats.json` before image or video generation.
6. Reuse the whiteboard project's configured image2 and TTS adapters. Never copy or print its secrets.
7. RunningHub member video generation is capped at 3 concurrent jobs. Enterprise shared mode is capped at 100. Preserve cached images and clips unless the prompt fingerprint changes.
8. Generate an editable ChatCut handoff. Use local FFmpeg assembly for unattended previews and fallback delivery.

## Safety

- Never print API keys or put them in repository files.
- Generated media belongs under `projects/` and stays untracked.
- A full 60-second run can trigger many paid image/video jobs. Confirm `beats.json` and shot count before a production run.
- Do not regenerate a successful stage without `--force`.

## Commands

```powershell
scripts/voxflow.ps1 doctor
scripts/voxflow.ps1 plan --project demo --script examples/demo-script.txt
scripts/voxflow.ps1 run --project demo --script examples/demo-script.txt
scripts/voxflow.ps1 chatcut --project demo --launch
```
