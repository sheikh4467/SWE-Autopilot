from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "documents"
WIDTH, HEIGHT = 2200, 1500
FONT_DIR = Path("C:/Windows/Fonts")


@dataclass(frozen=True)
class Entity:
    key: str
    title: str
    scope: str
    x: int
    y: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    label: str
    dashed: bool = False


SCOPE_STYLES = {
    "FYP-I": {"fill": "#E5F8FB", "stroke": "#087E8B", "accent": "#087E8B"},
    "FYP-II": {"fill": "#F0E9FF", "stroke": "#6A4C93", "accent": "#6A4C93"},
    "Shared": {"fill": "#FFF5D9", "stroke": "#A47700", "accent": "#A47700"},
}


def font(name: str, size: int):
    return ImageFont.truetype(str(FONT_DIR / name), size)


FONT_TITLE = font("timesbd.ttf", 30)
FONT_SUBTITLE = font("times.ttf", 16)
FONT_ENTITY = font("timesbd.ttf", 17)
FONT_FIELD = font("times.ttf", 14)
FONT_FIELD_BOLD = font("timesbd.ttf", 14)
FONT_LABEL = font("timesbd.ttf", 14)
FONT_LEGEND = font("times.ttf", 15)


BOX_W = 340
BOX_H = 132


ENTITIES: tuple[Entity, ...] = (
    Entity("users", "Users", "Shared", 40, 125, ("PK user_id", "email", "name", "password_hash", "created_at")),
    Entity("oauth_accounts", "OAuthAccounts", "Shared", 40, 280, ("PK oauth_account_id", "FK user_id", "provider", "provider_account_id", "created_at")),
    Entity("oauth_states", "OAuthStates", "Shared", 40, 435, ("PK state", "provider", "redirect_uri", "created_at", "expires_at")),
    Entity("projects", "Projects", "Shared", 40, 590, ("PK project_id", "FK owner_id", "name", "repository_url", "status")),
    Entity("project_members", "ProjectMembers", "Shared", 40, 745, ("PK membership_id", "FK project_id", "FK user_id", "role", "joined_at")),
    Entity("audit_events", "AuditEvents", "Shared", 40, 900, ("PK event_id", "FK project_id", "FK actor_user_id", "action", "created_at")),

    Entity("requirements", "Requirements", "FYP-I", 420, 125, ("PK requirement_id", "FK project_id", "external_key", "type", "status")),
    Entity("requirement_versions", "RequirementVersions", "FYP-I", 420, 280, ("PK version_id", "FK requirement_id", "version_no", "raw_text", "analysis_status")),
    Entity("user_stories", "UserStories", "FYP-I", 420, 435, ("PK story_id", "FK version_id", "story_key", "title", "status")),
    Entity("acceptance_criteria", "AcceptanceCriteria", "FYP-I", 420, 590, ("PK criteria_id", "FK story_id", "criterion_text", "status", "sort_order")),
    Entity("artifacts", "Artifacts", "Shared", 420, 745, ("PK artifact_id", "FK project_id", "artifact_type", "name", "current_version")),
    Entity("artifact_links", "ArtifactLinks", "Shared", 420, 900, ("PK link_id", "FK source_artifact_id", "FK target_artifact_id", "relation_type", "created_at")),

    Entity("architecture_proposals", "ArchitectureProposals", "FYP-I", 800, 125, ("PK architecture_id", "FK project_id", "version", "proposal_data", "status")),
    Entity("architecture_reviews", "ArchitectureReviews", "FYP-I", 800, 280, ("PK review_id", "FK architecture_id", "FK reviewer_id", "critic_summary", "decision")),
    Entity("risks", "Risks", "FYP-I", 800, 435, ("PK risk_id", "FK project_id", "FK artifact_id", "category", "severity")),
    Entity("agent_definitions", "AgentDefinitions", "Shared", 800, 590, ("PK agent_id", "name", "purpose", "model_provider", "active")),
    Entity("agent_runs", "AgentRuns", "Shared", 800, 745, ("PK run_id", "FK project_id", "FK agent_id", "FK parent_run_id", "state")),
    Entity("agent_messages", "AgentMessages", "Shared", 800, 900, ("PK message_id", "FK run_id", "role", "content", "created_at")),

    Entity("tool_permissions", "ToolPermissions", "Shared", 1180, 125, ("PK permission_id", "FK run_id", "tool_name", "scope", "decision")),
    Entity("generated_artifacts", "GeneratedArtifacts", "FYP-I", 1180, 280, ("PK generated_id", "FK run_id", "FK artifact_id", "commit_ref", "diff_summary")),
    Entity("execution_runs", "ExecutionRuns", "FYP-I", 1180, 435, ("PK execution_id", "FK project_id", "FK generated_id", "image", "status")),
    Entity("verification_checks", "VerificationChecks", "FYP-I", 1180, 590, ("PK check_id", "FK project_id", "name", "check_type", "command")),
    Entity("verification_results", "VerificationResults", "FYP-I", 1180, 745, ("PK result_id", "FK execution_id", "FK check_id", "status", "evidence_uri")),
    Entity("approvals", "Approvals", "Shared", 1180, 900, ("PK approval_id", "FK project_id", "FK reviewer_id", "gate_type", "decision")),

    Entity("change_requests", "ChangeRequests", "FYP-II", 1560, 125, ("PK change_id", "FK project_id", "FK requested_by", "description", "status")),
    Entity("impact_analyses", "ImpactAnalyses", "FYP-II", 1560, 280, ("PK impact_id", "FK change_id", "FK artifact_id", "impact_type", "confidence")),
    Entity("recovery_attempts", "RecoveryAttempts", "FYP-II", 1560, 435, ("PK recovery_id", "FK execution_id", "FK run_id", "attempt_no", "outcome")),
    Entity("security_findings", "SecurityFindings", "FYP-II", 1560, 590, ("PK finding_id", "FK project_id", "FK execution_id", "severity", "status")),
    Entity("attack_memory", "AttackMemory", "FYP-II", 1560, 745, ("PK attack_id", "FK finding_id", "signature", "trigger_scope", "active")),
    Entity("regression_tests", "RegressionTests", "FYP-II", 1560, 900, ("PK regression_id", "FK attack_id", "FK check_id", "test_case", "replay_policy")),
    Entity("deployments", "Deployments", "FYP-II", 1560, 1055, ("PK deployment_id", "FK project_id", "FK execution_id", "environment", "status")),
    Entity("reports", "Reports", "FYP-II", 1560, 1210, ("PK report_id", "FK project_id", "FK generated_by", "report_type", "file_uri")),
)


RELATIONS: tuple[Relation, ...] = (
    Relation("users", "oauth_accounts", "1 : N"),
    Relation("users", "projects", "owner"),
    Relation("users", "project_members", "member"),
    Relation("projects", "project_members", "1 : N"),
    Relation("projects", "audit_events", "1 : N"),
    Relation("users", "audit_events", "actor"),
    Relation("projects", "requirements", "1 : N"),
    Relation("requirements", "requirement_versions", "1 : N"),
    Relation("requirement_versions", "user_stories", "1 : N"),
    Relation("user_stories", "acceptance_criteria", "1 : N"),
    Relation("projects", "artifacts", "1 : N"),
    Relation("artifacts", "artifact_links", "source/target"),
    Relation("projects", "architecture_proposals", "1 : N"),
    Relation("architecture_proposals", "architecture_reviews", "1 : N"),
    Relation("users", "architecture_reviews", "reviewer"),
    Relation("projects", "risks", "1 : N"),
    Relation("artifacts", "risks", "affected"),
    Relation("agent_definitions", "agent_runs", "1 : N"),
    Relation("projects", "agent_runs", "1 : N"),
    Relation("agent_runs", "agent_messages", "1 : N"),
    Relation("agent_runs", "tool_permissions", "1 : N"),
    Relation("agent_runs", "generated_artifacts", "1 : N"),
    Relation("artifacts", "generated_artifacts", "versioned"),
    Relation("projects", "execution_runs", "1 : N"),
    Relation("generated_artifacts", "execution_runs", "executes"),
    Relation("projects", "verification_checks", "1 : N"),
    Relation("execution_runs", "verification_results", "1 : N"),
    Relation("verification_checks", "verification_results", "1 : N"),
    Relation("projects", "approvals", "1 : N"),
    Relation("users", "approvals", "reviewer"),
    Relation("projects", "change_requests", "1 : N", dashed=True),
    Relation("change_requests", "impact_analyses", "1 : N", dashed=True),
    Relation("artifacts", "impact_analyses", "affected", dashed=True),
    Relation("execution_runs", "recovery_attempts", "1 : N", dashed=True),
    Relation("agent_runs", "recovery_attempts", "repair run", dashed=True),
    Relation("projects", "security_findings", "1 : N", dashed=True),
    Relation("execution_runs", "security_findings", "detected by", dashed=True),
    Relation("security_findings", "attack_memory", "1 : N", dashed=True),
    Relation("attack_memory", "regression_tests", "1 : N", dashed=True),
    Relation("verification_checks", "regression_tests", "replays", dashed=True),
    Relation("projects", "deployments", "1 : N", dashed=True),
    Relation("execution_runs", "deployments", "released", dashed=True),
    Relation("projects", "reports", "1 : N", dashed=True),
    Relation("users", "reports", "generated by", dashed=True),
)


def entity_map():
    return {entity.key: entity for entity in ENTITIES}


def center(entity: Entity):
    return entity.x + BOX_W // 2, entity.y + BOX_H // 2


def draw_wrapped(draw, text, xy, max_width, fnt, fill="#111827", line_gap=2):
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def arrow(draw, start, end, color, dashed=False):
    if dashed:
        dx, dy = end[0] - start[0], end[1] - start[1]
        dist = max(1, (dx * dx + dy * dy) ** 0.5)
        ux, uy = dx / dist, dy / dist
        segment = 12
        gap = 8
        pos = 0
        while pos < dist:
            p1 = (start[0] + ux * pos, start[1] + uy * pos)
            p2 = (start[0] + ux * min(pos + segment, dist), start[1] + uy * min(pos + segment, dist))
            draw.line([p1, p2], fill=color, width=2)
            pos += segment + gap
    else:
        draw.line([start, end], fill=color, width=2)
    dx, dy = end[0] - start[0], end[1] - start[1]
    dist = max(1, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux
    size = 10
    tip = end
    left = (end[0] - ux * size + px * size * 0.6, end[1] - uy * size + py * size * 0.6)
    right = (end[0] - ux * size - px * size * 0.6, end[1] - uy * size - py * size * 0.6)
    draw.polygon([tip, left, right], fill=color)


def relation_points(source: Entity, target: Entity):
    sx, sy = center(source)
    tx, ty = center(target)
    if source.x < target.x:
        return (source.x + BOX_W, sy), (target.x, ty)
    if source.x > target.x:
        return (source.x, sy), (target.x + BOX_W, ty)
    if source.y < target.y:
        return (sx, source.y + BOX_H), (tx, target.y)
    return (sx, source.y), (tx, target.y + BOX_H)


def draw_png(path: Path):
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 24), "SWE Autopilot — Whole Project Logical ERD", font=FONT_TITLE, fill="#111827")
    draw.text((40, 64), "FYP-I core entities and FYP-II extension entities; PK = primary key, FK = foreign key", font=FONT_SUBTITLE, fill="#4B5563")
    draw.line((40, 92, WIDTH - 40, 92), fill="#111827", width=2)

    # Scope legend.
    legend_x = WIDTH - 590
    legend_y = 30
    for index, scope in enumerate(("FYP-I", "FYP-II", "Shared")):
        style = SCOPE_STYLES[scope]
        x = legend_x + index * 175
        draw.rounded_rectangle((x, legend_y, x + 22, legend_y + 22), radius=4, fill=style["fill"], outline=style["stroke"], width=2)
        draw.text((x + 30, legend_y + 1), scope, font=FONT_LEGEND, fill="#374151")

    entities = entity_map()
    # Draw relationship lines behind entities.
    for relation in RELATIONS:
        source = entities[relation.source]
        target = entities[relation.target]
        start, end = relation_points(source, target)
        source_style = SCOPE_STYLES[source.scope]
        color = source_style["stroke"] if relation.dashed else "#9CA3AF"
        arrow(draw, start, end, color, relation.dashed)
        mx = (start[0] + end[0]) // 2
        my = (start[1] + end[1]) // 2
        # Avoid placing most labels on top of boxes; only show selected relation labels.
        if relation.label in {"owner", "member", "reviewer", "affected", "executes", "detected by", "released", "generated by"}:
            draw.rounded_rectangle((mx - 35, my - 10, mx + 35, my + 10), radius=4, fill="white")
            draw.text((mx - 30, my - 8), relation.label, font=font("times.ttf", 11), fill="#4B5563")

    for entity in ENTITIES:
        style = SCOPE_STYLES[entity.scope]
        x, y = entity.x, entity.y
        draw.rounded_rectangle((x, y, x + BOX_W, y + BOX_H), radius=7, fill=style["fill"], outline=style["stroke"], width=3)
        draw.rectangle((x, y, x + BOX_W, y + 30), fill=style["stroke"])
        draw.text((x + 10, y + 5), entity.title, font=FONT_ENTITY, fill="white")
        field_y = y + 39
        for field in entity.fields:
            is_key = field.startswith("PK") or field.startswith("FK")
            fnt = FONT_FIELD_BOLD if is_key else FONT_FIELD
            color = style["accent"] if is_key else "#374151"
            draw.text((x + 12, field_y), field, font=fnt, fill=color)
            field_y += 18

    # Cluster labels.
    clusters = [
        (40, 1080, 335, "Identity & Workspace"),
        (420, 1080, 715, "Requirements & Traceability"),
        (800, 1080, 1095, "Architecture & Agent Runtime"),
        (1180, 1080, 1475, "Generation & Verification"),
        (1560, 1390, 1900, "Change, Security & Release"),
    ]
    for x, y, right, label in clusters:
        draw.text((x, y), label, font=FONT_LABEL, fill="#6B7280")

    image.save(path, "PNG", optimize=True)


def draw_svg(path: Path):
    def esc(text):
        return escape(text)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:"Times New Roman",serif;fill:#111827}.title{font-size:30px;font-weight:700}.subtitle{font-size:16px;fill:#4b5563}.entity-title{font-size:17px;font-weight:700;fill:white}.field{font-size:14px}.key{font-weight:700}.cluster{font-size:14px;font-weight:700;fill:#6b7280}.relation{font-size:11px;fill:#4b5563}</style>',
        '<text x="40" y="50" class="title">SWE Autopilot — Whole Project Logical ERD</text>',
        '<text x="40" y="78" class="subtitle">FYP-I core entities and FYP-II extension entities; PK = primary key, FK = foreign key</text>',
        f'<line x1="40" y1="92" x2="{WIDTH - 40}" y2="92" stroke="#111827" stroke-width="2"/>',
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#9CA3AF"/></marker><marker id="arrowDashed" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#6A4C93"/></marker></defs>',
    ]
    for index, scope in enumerate(("FYP-I", "FYP-II", "Shared")):
        style = SCOPE_STYLES[scope]
        x = WIDTH - 590 + index * 175
        lines.append(f'<rect x="{x}" y="30" width="22" height="22" rx="4" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="2"/>')
        lines.append(f'<text x="{x + 30}" y="47" class="subtitle">{scope}</text>')
    entities = entity_map()
    for relation in RELATIONS:
        source, target = entities[relation.source], entities[relation.target]
        start, end = relation_points(source, target)
        color = SCOPE_STYLES[source.scope]["stroke"] if relation.dashed else "#9CA3AF"
        dash = ' stroke-dasharray="8,6"' if relation.dashed else ""
        marker = "arrowDashed" if relation.dashed else "arrow"
        lines.append(f'<line x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" stroke="{color}" stroke-width="2"{dash} marker-end="url(#{marker})"/>')
    for entity in ENTITIES:
        style = SCOPE_STYLES[entity.scope]
        x, y = entity.x, entity.y
        lines.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="7" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="3"/>')
        lines.append(f'<rect x="{x}" y="{y}" width="{BOX_W}" height="30" rx="7" fill="{style["stroke"]}"/>')
        lines.append(f'<rect x="{x}" y="{y + 22}" width="{BOX_W}" height="8" fill="{style["stroke"]}"/>')
        lines.append(f'<text x="{x + 10}" y="{y + 21}" class="entity-title">{esc(entity.title)}</text>')
        field_y = y + 49
        for field in entity.fields:
            cls = "field key" if field.startswith(("PK", "FK")) else "field"
            color = style["accent"] if field.startswith(("PK", "FK")) else "#374151"
            lines.append(f'<text x="{x + 12}" y="{field_y}" class="{cls}" fill="{color}">{esc(field)}</text>')
            field_y += 18
    for x, y, _, label in [(40, 1080, 335, "Identity & Workspace"), (420, 1080, 715, "Requirements & Traceability"), (800, 1080, 1095, "Architecture & Agent Runtime"), (1180, 1080, 1475, "Generation & Verification"), (1560, 1390, 1900, "Change, Security & Release")]:
        lines.append(f'<text x="{x}" y="{y}" class="cluster">{esc(label)}</text>')
    lines.append('</svg>')
    path.write_text("\n".join(lines), encoding="utf-8")


def draw_pdf(path: Path, png_path: Path):
    page_width, page_height = landscape((11 * 72, 8.5 * 72))
    pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height))
    image = Image.open(png_path)
    scale = min((page_width - 24) / image.width, (page_height - 24) / image.height)
    w, h = image.width * scale, image.height * scale
    pdf.drawImage(ImageReader(image), (page_width - w) / 2, (page_height - h) / 2, width=w, height=h, preserveAspectRatio=True, mask="auto")
    pdf.setTitle("SWE Autopilot Whole Project Logical ERD")
    pdf.save()


def write_markdown(path: Path):
    lines = [
        "# SWE Autopilot — Whole Project Logical ERD",
        "",
        "This ERD is a proposed logical data model for the complete SWE Autopilot platform. It includes the FYP-I core and the FYP-II extensions from the project proposal.",
        "",
        "## Scope legend",
        "",
        "- **FYP-I:** requirements, traceability, risk analysis, architecture review, agent runtime, code generation, Docker execution, initial verification, workspace, and authentication.",
        "- **FYP-II:** change-impact analysis, recovery, defensive security testing, Attack Memory, regression replay, deployment, and final reporting.",
        "- **Shared:** identity, project membership, artifacts, agent definitions, audit events, and approval infrastructure.",
        "",
        "## Core relationship summary",
        "",
        "- Users own projects and join projects through ProjectMembers.",
        "- Projects contain requirements, artifacts, architecture proposals, risks, agent runs, executions, verification checks, approvals, and audit events.",
        "- Requirements are versioned and decomposed into user stories and acceptance criteria.",
        "- Artifacts are connected through ArtifactLinks to maintain requirement-to-evidence traceability.",
        "- AgentRuns produce generated artifacts and messages while ToolPermissions record runtime control decisions.",
        "- ExecutionRuns produce VerificationResults and may later produce RecoveryAttempts and SecurityFindings.",
        "- SecurityFindings become AttackMemory records, which create reusable RegressionTests.",
        "- Verified executions can be promoted to Deployments and summarized in Reports.",
        "",
        "## Implementation note",
        "",
        "The current authentication prototype already implements Users, OAuthAccounts, and OAuthStates in SQLite. The remaining entities are the proposed platform schema for the full SWE Autopilot implementation and should be reviewed by the advisor before database migration work.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "SWE_Autopilot_Whole_Project_ERD.png"
    svg = OUT / "SWE_Autopilot_Whole_Project_ERD.svg"
    pdf = OUT / "SWE_Autopilot_Whole_Project_ERD.pdf"
    md = OUT / "SWE_Autopilot_Whole_Project_ERD.md"
    draw_png(png)
    draw_svg(svg)
    draw_pdf(pdf, png)
    write_markdown(md)
    print(png)
    print(svg)
    print(pdf)
    print(md)
