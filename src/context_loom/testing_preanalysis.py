"""Testing-domain reader for preanalysis/v1, not a generic runtime contract.

The producer's validator remains the complete document/semantic gate. This reader
checks the selected units and their dependencies again before preparing a pilot.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote


MANIFEST = "preanalysis-manifest.json"
ARTIFACTS = {"readme", "module_requirement", "context_pack", "rsu_map", "clarifications", "context_card_index"}
ROLES = {"global_context", "module_requirement", "module_context"}
RSU = re.compile(r"RSU-\d{3,}")
REF = re.compile(r"(?:SRC-[A-Z0-9-]+|CTX|(?:RSU|Q|FC|DC)-(?:\d{3,}|INDEX))")


def split_row(line: str) -> list[str]:
    # Do not split escaped pipes or pipes inside inline code.
    cells, buffer = [], []
    escaped = in_code = False
    for char in line.strip().strip("|"):
        if escaped:
            buffer.append(char)
            escaped = False
        elif char == "\\":
            buffer.append(char)
            escaped = True
        elif char == "`":
            in_code = not in_code
            buffer.append(char)
        elif char == "|" and not in_code:
            cells.append("".join(buffer).strip())
            buffer = []
        else:
            buffer.append(char)
    return cells + ["".join(buffer).strip()]


def normalize(text: str) -> str:
    value = html.unescape(text).replace("\u00a0", " ")
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"</?[A-Za-z][^>]*>", "", value)
    value = re.sub(r"\\([\\`*_{}\[\]()#+.!|>-])", r"\1", value)
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s{0,3}>+\s?", "", value)
    value = re.sub(r"(?m)^\s*(?:[-+*]|\d+[.)])\s+", "", value)
    value = re.sub(r"(^|[：；。])\s*\d+[.)]\s+", r"\1", value, flags=re.MULTILINE)
    value = value.replace("~~", "").replace("**", "").replace("*", "").replace("`", "")
    value = re.sub(r"(?<!\w)_{1,2}(?=\S)|(?<=\S)_{1,2}(?!\w)", "", value)
    return re.sub(r"\s+", "", value).strip()


def refs(text: str) -> list[str]:
    expanded = text
    for match in re.finditer(r"(RSU|Q|FC|DC)-(\d{3,})\s*[～~]\s*(?:\1-)?(\d{3,})", text):
        first, last = int(match[2]), int(match[3])
        if last < first or last - first > 10000:
            raise ValueError(f"invalid dependency range: {match[0]}")
        expanded += " " + " ".join(f"{match[1]}-{number:03d}" for number in range(first, last + 1))
    return list(dict.fromkeys(REF.findall(expanded)))


def _relative_file(base: Path, raw: object, boundary: Path, label: str) -> Path:
    if not isinstance(raw, str) or not raw or Path(raw).is_absolute() or "\\" in raw or ":" in raw:
        raise ValueError(f"{label} must use a portable relative path")
    path = (base / raw).resolve()
    if not path.is_relative_to(boundary) or not path.is_file():
        raise ValueError(f"missing or out-of-bounds {label}: {raw}")
    return path


@dataclass
class PreanalysisInput:
    directory: Path
    project: Path
    artifacts: dict[str, Path]
    roles: dict[str, str]
    resources: dict[str, Path]
    rows: dict[str, list[str]]

    def task_inputs(self, rsu_id: str) -> tuple[list[dict[str, str]], list[list[str]]]:
        """Return direct dynamic files and exact supporting rows, never worker history."""
        dependencies: dict[str, Path] = {}
        supporting: dict[str, list[str]] = {}
        visited: set[str] = set()
        fixed_ids = set(self.roles.values())

        def visit(unit_id: str) -> None:
            if unit_id in visited:
                return
            visited.add(unit_id)
            row = self.rows.get(unit_id)
            if row is None:
                raise ValueError(f"RSU not found in the original mapping: {unit_id}")
            if row[7] != "captured":
                raise ValueError(f"RSU is not captured: {unit_id}")
            source = self.resources.get(row[3])
            if source is None or not normalize(row[2]) or normalize(row[2]) not in normalize(source.read_text(encoding="utf-8")):
                raise ValueError(f"RSU lacks a captured, literal requirement: {unit_id}")
            if row[1] != "无" and normalize(row[1]) not in normalize(source.read_text(encoding="utf-8")):
                raise ValueError(f"parent wording does not match source: {unit_id}")
            direct_refs = refs(row[5]) + refs(row[6]) + [row[3]]
            if row[6] != "无" and not any(re.fullmatch(r"Q-\d{3,}", ref) for ref in refs(row[6])):
                raise ValueError(f"unresolvable question references: {unit_id}")
            for ref in dict.fromkeys(direct_refs):
                if ref in fixed_ids:
                    continue
                if RSU.fullmatch(ref):
                    visit(ref)
                    if ref != rsu_id:
                        supporting[ref] = self.rows[ref]
                elif re.fullmatch(r"Q-\d{3,}", ref):
                    question_file = self.artifacts["clarifications"]
                    matches = [split_row(line) for line in question_file.read_text(encoding="utf-8").splitlines()
                               if line.lstrip().startswith("|") and split_row(line)[0] == ref]
                    if len(matches) != 1 or len(matches[0]) != 5 or matches[0][2] not in {"answered", "out-of-scope"}:
                        raise ValueError(f"unresolved or missing question: {ref}")
                    dependencies["CLARIFICATIONS"] = question_file
                else:
                    path = self.resources.get(ref)
                    if path is None:
                        raise ValueError(f"missing dynamic context: {ref}")
                    if re.fullmatch(r"DC-\d{3,}", ref):
                        index = self.resources.get("DC-INDEX")
                        matches = [] if index is None else [split_row(line) for line in index.read_text(encoding="utf-8").splitlines()
                            if line.lstrip().startswith("|") and split_row(line)[0] == ref]
                        if len(matches) != 1 or len(matches[0]) != 6 or matches[0][3] not in {"ready", "test-point-ready"}:
                            raise ValueError(f"blocked or missing data closure: {ref}")
                    dependencies[ref] = path

        visit(rsu_id)
        contexts = [{"context_id": ref, "path": path.relative_to(self.project).as_posix()}
                    for ref, path in dependencies.items()]
        return contexts, list(supporting.values())


def load_preanalysis(module: Path, project: Path) -> PreanalysisInput | None:
    """Discover one manifest. None means the caller may use its legacy adapter."""
    module, project = module.resolve(), project.resolve()
    if not module.is_dir() or not module.is_relative_to(project):
        raise ValueError("preanalysis module must exist inside the project")
    candidates = [module / MANIFEST, *(child / MANIFEST for child in module.iterdir() if child.is_dir())]
    manifests = [path for path in candidates if path.is_file()]
    if not manifests:
        return None
    if len(manifests) != 1:
        raise ValueError("multiple preanalysis manifests; refusing ambiguous inputs")
    manifest = manifests[0].resolve()
    if not manifest.is_relative_to(module):
        raise ValueError("preanalysis manifest escapes module")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or set(data) != {"schema_version", "module_root", "artifacts", "resource_roles", "output"} or data["schema_version"] != "preanalysis/v1":
        raise ValueError("invalid preanalysis/v1 manifest")
    raw_root = data["module_root"]
    if not isinstance(raw_root, str) or Path(raw_root).is_absolute() or "\\" in raw_root or ":" in raw_root or (manifest.parent / raw_root).resolve() != module:
        raise ValueError("manifest module_root does not match the requested module")
    if not isinstance(data["artifacts"], dict) or set(data["artifacts"]) != ARTIFACTS:
        raise ValueError("invalid preanalysis artifact roles")
    artifacts = {key: _relative_file(manifest.parent, path, manifest.parent, f"artifact {key}")
                 for key, path in data["artifacts"].items()}
    if len(set(artifacts.values())) != len(artifacts):
        raise ValueError("preanalysis artifact roles must have distinct files")
    roles = data["resource_roles"]
    if not isinstance(roles, dict) or set(roles) != ROLES or any(not isinstance(ref, str) or not re.fullmatch(r"(?:SRC-[A-Z0-9-]+|CTX)", ref) for ref in roles.values()) or len(set(roles.values())) != 3:
        raise ValueError("invalid preanalysis resource roles")
    if any(not roles[key].startswith("SRC-") for key in ("global_context", "module_requirement")):
        raise ValueError("global and requirement roles must use SRC IDs")
    output = data["output"]
    if not isinstance(output, dict) or set(output) != {"test_points_dir"}:
        raise ValueError("invalid preanalysis output contract")
    raw_output = output["test_points_dir"]
    if not isinstance(raw_output, str) or not raw_output or Path(raw_output).is_absolute() or "\\" in raw_output or ":" in raw_output:
        raise ValueError("test-point output must be a portable relative path")
    target = (manifest.parent / raw_output).resolve()
    if target == module or not target.is_relative_to(module):
        raise ValueError("test-point output escapes module")
    resources, rows = {}, {}
    for line in artifacts["rsu_map"].read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) == 8 and RSU.fullmatch(cells[0]):
            if cells[0] in rows:
                raise ValueError(f"duplicate RSU mapping: {cells[0]}")
            rows[cells[0]] = cells
        elif len(cells) == 3 and re.fullmatch(r"(?:SRC-[A-Z0-9-]+|CTX|(?:Q|RSU|FC|DC)-INDEX|(?:FC|DC)-\d{3,})", cells[0]):
            match = re.search(r"\[[^\]]*\]\((.+)\)", cells[1])
            if match is None or "#" in match[1]:
                raise ValueError(f"resource needs a local file link: {cells[0]}")
            raw = unquote(match[1].strip().strip("<>"))
            if cells[0] in resources:
                raise ValueError(f"duplicate resource: {cells[0]}")
            resources[cells[0]] = _relative_file(artifacts["rsu_map"].parent, raw, project, cells[0])
    for role, ref in roles.items():
        if ref not in resources:
            raise ValueError(f"missing fixed resource: {ref}")
        expected = {"module_requirement": "module_requirement", "module_context": "context_pack"}.get(role)
        if expected and resources[ref] != artifacts[expected]:
            raise ValueError(f"fixed resource does not match artifact: {ref}")
    return PreanalysisInput(manifest.parent, project, artifacts, dict(roles), resources, rows)
