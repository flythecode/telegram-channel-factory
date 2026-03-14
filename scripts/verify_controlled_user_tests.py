#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET_DIR = ROOT / "controlled-user-tests" / "2026-03-14"
TEMPLATE = ROOT / "CONTROLLED_USER_TEST_RESULTS_TEMPLATE.md"
MANIFEST = PACKET_DIR / "STATUS_MANIFEST.json"
REPORT = ROOT / "CONTROLLED_USER_TEST_REPORT_2026-03-14.md"
PARTICIPANTS = [PACKET_DIR / f"PARTICIPANT_0{i}.md" for i in range(1, 4)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_filled(path: Path, template_hash: str) -> bool:
    if not path.exists():
        return False
    if sha256(path) == template_hash:
        return False
    text = path.read_text(encoding="utf-8")
    required_markers = ["- Date:", "- Participant:", "## Summary"]
    return all(marker in text for marker in required_markers) and text.count(":\n") < text.count(":")


def main() -> int:
    template_hash = sha256(TEMPLATE)
    participant_hashes = {p.name: sha256(p) if p.exists() else None for p in PARTICIPANTS}
    filled = [{"path": f"./{p.name}", "filled": is_filled(p, template_hash)} for p in PARTICIPANTS]
    filled_count = sum(1 for item in filled if item["filled"])
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["participantFiles"] = filled
    manifest["currentStatus"] = "ready_for_close" if filled_count >= 2 else "blocked_on_real_participants"
    manifest["lastVerifiedAt"] = now
    manifest["latestEvidence"] = [
        f"template_sha256={template_hash}",
        *[f"{name}_sha256={digest}" for name, digest in participant_hashes.items() if digest],
        f"filled_participant_files={filled_count}"
    ]
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = [
        "# Controlled user test verification",
        "",
        f"- Verified at: {now}",
        f"- Filled participant files: {filled_count}/{len(PARTICIPANTS)}",
        f"- Status: {manifest['currentStatus']}",
        "- Participant files:",
    ]
    summary.extend([f"  - {item['path']}: {'filled' if item['filled'] else 'template/empty'}" for item in filled])
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
