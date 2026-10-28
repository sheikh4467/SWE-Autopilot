from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "documents"
WIDTH, HEIGHT = 2400, 1660
FONT_DIR = Path("C:/Windows/Fonts")


@dataclass(frozen=True)
class TableDef:
    key: str
    name: str
    x: int
    y: int
    fields: tuple[str, ...]


@dataclass(frozen=True)
class Rel:
    source: str
    target: str
    source_card: Literal["one", "many"] = "one"
    target_card: Literal["one", "many"] = "many"
    source_optional: bool = False
    target_optional: bool = False


FONT_TITLE = ImageFont.truetype(str(FONT_DIR / "timesbd.ttf"), 32)
FONT_SUBTITLE = ImageFont.truetype(str(FONT_DIR / "times.ttf"), 16)
FONT_TABLE = ImageFont.truetype(str(FONT_DIR / "timesbd.ttf"), 15)
FONT_FIELD = ImageFont.truetype(str(FONT_DIR / "times.ttf"), 13)
FONT_KEY = ImageFont.truetype(str(FONT_DIR / "timesbd.ttf"), 13)
FONT_LEGEND = ImageFont.truetype(str(FONT_DIR / "times.ttf"), 14)

TABLE_W = 300
HEADER_H = 29
ROW_H = 19
TABLE_H = HEADER_H + ROW_H * 5


TABLES: tuple[TableDef, ...] = (
    # Identity and workspace
    TableDef("users", "tbUSERS", 40, 130, ("PK user_id", "email", "name", "password_hash", "created_at")),
    TableDef("oauth_accounts", "tbOAUTH_ACCOUNTS", 40, 310, ("PK oauth_account_id", "FK user_id", "provider", "provider_account_id", "created_at")),
    TableDef("projects", "tbPROJECTS", 40, 490, ("PK project_id", "FK owner_id", "project_name", "repository_url", "status")),
    TableDef("project_members", "tbPROJECT_MEMBERS", 40, 670, ("PK membership_id", "FK project_id", "FK user_id", "role", "joined_at")),
    TableDef("audit_events", "tbAUDIT_EVENTS", 40, 850, ("PK event_id", "FK project_id", "FK actor_user_id", "action", "created_at")),
    # Requirements and traceability
    TableDef("requirements", "tbREQUIREMENTS", 400, 130, ("PK requirement_id", "FK project_id", "external_key", "type", "status")),
    TableDef("requirement_versions", "tbREQ_VERSIONS", 400, 310, ("PK version_id", "FK requirement_id", "version_no", "raw_text", "analysis_status")),
    TableDef("user_stories", "tbUSER_STORIES", 400, 490, ("PK story_id", "FK version_id", "story_key", "title", "status")),
    TableDef("acceptance_criteria", "tbACCEPTANCE_CRITERIA", 400, 670, ("PK criteria_id", "FK story_id", "criterion_text", "status", "sort_order")),
    TableDef("artifacts", "tbARTIFACTS", 400, 850, ("PK artifact_id", "FK project_id", "artifact_type", "name", "current_version")),
    TableDef("artifact_links", "tbARTIFACT_LINKS", 400, 1030, ("PK link_id", "FK source_artifact_id", "FK target_artifact_id", "relation_type", "created_at")),
    # Architecture and runtime
    TableDef("architecture_proposals", "tbARCH_PROPOSALS", 760, 130, ("PK architecture_id", "FK project_id", "version", "status", "rationale")),
    TableDef("architecture_reviews", "tbARCH_REVIEWS", 760, 310, ("PK review_id", "FK architecture_id", "FK reviewer_id", "critic_summary", "decision")),
    TableDef("risks", "tbRISKS", 760, 490, ("PK risk_id", "FK project_id", "FK artifact_id", "category", "severity")),
    TableDef("agent_definitions", "tbAGENT_DEFINITIONS", 760, 670, ("PK agent_id", "agent_name", "purpose", "model_provider", "active")),
    TableDef("agent_runs", "tbAGENT_RUNS", 760, 850, ("PK run_id", "FK project_id", "FK agent_id", "state", "started_at")),
    TableDef("agent_messages", "tbAGENT_MESSAGES", 760, 1030, ("PK message_id", "FK run_id", "role", "content", "created_at")),
    # Code and verification
    TableDef("tool_permissions", "tbTOOL_PERMISSIONS", 1120, 130, ("PK permission_id", "FK run_id", "tool_name", "scope", "decision")),
    TableDef("generated_artifacts", "tbGENERATED_ARTIFACTS", 1120, 310, ("PK generated_id", "FK run_id", "FK artifact_id", "commit_ref", "diff_summary")),
    TableDef("execution_runs", "tbEXECUTION_RUNS", 1120, 490, ("PK execution_id", "FK project_id", "FK generated_id", "image", "status")),
    TableDef("verification_checks", "tbVERIFICATION_CHECKS", 1120, 670, ("PK check_id", "FK project_id", "check_name", "check_type", "command")),
    TableDef("verification_results", "tbVERIFICATION_RESULTS", 1120, 850, ("PK result_id", "FK execution_id", "FK check_id", "status", "evidence_uri")),
    TableDef("approvals", "tbAPPROVALS", 1120, 1030, ("PK approval_id", "FK project_id", "FK reviewer_id", "gate_type", "decision")),
    # FYP-II change, security, release
    TableDef("change_requests", "tbCHANGE_REQUESTS", 1480, 130, ("PK change_id", "FK project_id", "FK requested_by", "description", "status")),
    TableDef("impact_analyses", "tbIMPACT_ANALYSES", 1480, 310, ("PK impact_id", "FK change_id", "FK artifact_id", "impact_type", "confidence")),
    TableDef("recovery_attempts", "tbRECOVERY_ATTEMPTS", 1480, 490, ("PK recovery_id", "FK execution_id", "FK run_id", "attempt_no", "outcome")),
    TableDef("security_findings", "tbSECURITY_FINDINGS", 1480, 670, ("PK finding_id", "FK project_id", "FK execution_id", "severity", "status")),
    TableDef("attack_memory", "tbATTACK_MEMORY", 1480, 850, ("PK attack_id", "FK finding_id", "signature", "trigger_scope", "active")),
    TableDef("regression_tests", "tbREGRESSION_TESTS", 1480, 1030, ("PK regression_id", "FK attack_id", "FK check_id", "test_case", "replay_policy")),
    TableDef("deployments", "tbDEPLOYMENTS", 1840, 130, ("PK deployment_id", "FK project_id", "FK execution_id", "environment", "status")),
    TableDef("reports", "tbREPORTS", 1840, 310, ("PK report_id", "FK project_id", "FK generated_by", "report_type", "file_uri")),
    TableDef("oauth_states", "tbOAUTH_STATES", 1840, 490, ("PK state", "provider", "redirect_uri", "created_at", "expires_at")),
)


RELATIONS: tuple[Rel, ...] = (
    Rel("users", "oauth_accounts", target_card="many"),
    Rel("users", "projects", target_card="many"),
    Rel("users", "project_members", target_card="many"),
    Rel("projects", "project_members", target_card="many"),
    Rel("projects", "audit_events", target_card="many"),
    Rel("users", "audit_events", target_card="many"),
    Rel("projects", "requirements", target_card="many"),
    Rel("requirements", "requirement_versions", target_card="many"),
    Rel("requirement_versions", "user_stories", target_card="many"),
    Rel("user_stories", "acceptance_criteria", target_card="many"),
    Rel("projects", "artifacts", target_card="many"),
    Rel("artifacts", "artifact_links", target_card="many"),
    Rel("projects", "architecture_proposals", target_card="many"),
    Rel("architecture_proposals", "architecture_reviews", target_card="many"),
    Rel("users", "architecture_reviews", target_card="many"),
    Rel("projects", "risks", target_card="many", target_optional=True),
    Rel("artifacts", "risks", target_card="many", target_optional=True),
    Rel("agent_definitions", "agent_runs", target_card="many"),
    Rel("projects", "agent_runs", target_card="many"),
    Rel("agent_runs", "agent_messages", target_card="many"),
    Rel("agent_runs", "tool_permissions", target_card="many"),
    Rel("agent_runs", "generated_artifacts", target_card="many"),
    Rel("artifacts", "generated_artifacts", target_card="many"),
    Rel("projects", "execution_runs", target_card="many"),
    Rel("generated_artifacts", "execution_runs", target_card="many"),
    Rel("projects", "verification_checks", target_card="many"),
    Rel("execution_runs", "verification_results", target_card="many"),
    Rel("verification_checks", "verification_results", target_card="many"),
    Rel("projects", "approvals", target_card="many"),
    Rel("users", "approvals", target_card="many"),
    Rel("projects", "change_requests", target_card="many"),
    Rel("change_requests", "impact_analyses", target_card="many"),
    Rel("artifacts", "impact_analyses", target_card="many", target_optional=True),
    Rel("execution_runs", "recovery_attempts", target_card="many"),
    Rel("agent_runs", "recovery_attempts", target_card="many", target_optional=True),
    Rel("projects", "security_findings", target_card="many"),
    Rel("execution_runs", "security_findings", target_card="many"),
    Rel("security_findings", "attack_memory", target_card="many"),
    Rel("attack_memory", "regression_tests", target_card="many"),
    Rel("verification_checks", "regression_tests", target_card="many", target_optional=True),
    Rel("projects", "deployments", target_card="many"),
    Rel("execution_runs", "deployments", target_card="many"),
    Rel("projects", "reports", target_card="many"),
    Rel("users", "reports", target_card="many"),
)


def table_map():
    return {table.key: table for table in TABLES}


def fonts():
    return {
        "title": ImageFont.truetype(str(FONT_DIR / "timesbd.ttf"), 32),
        "subtitle": ImageFont.truetype(str(FONT_DIR / "times.ttf"), 16),
        "table": ImageFont.truetype(str(FONT_DIR / "timesbd.ttf"), 14),
        "field": ImageFont.truetype(str(FONT_DIR / "times.ttf"), 13),
        "key": ImageFont.truetype(str(FONT_DIR / "timesbd.ttf"), 13),
        "legend": ImageFont.truetype(str(FONT_DIR / "times.ttf"), 14),
    }


def center(table: TableDef):
    return table.x + TABLE_W // 2, table.y + TABLE_H // 2


def edge_points(source: TableDef, target: TableDef):
    sx, sy = center(source)
    tx, ty = center(target)
    if source.x < target.x:
        return (source.x + TABLE_W, sy), (target.x, ty)
    if source.x > target.x:
        return (source.x, sy), (target.x + TABLE_W, ty)
    if source.y < target.y:
        return (sx, source.y + TABLE_H), (tx, target.y)
    return (sx, source.y), (tx, target.y + TABLE_H)


def dashed_line(draw, start, end, width=2, dash=10, gap=6):
    dx, dy = end[0] - start[0], end[1] - start[1]
    distance = max(1.0, (dx * dx + dy * dy) ** 0.5)
    ux, uy = dx / distance, dy / distance
    pos = 0.0
    while pos < distance:
        a = (start[0] + ux * pos, start[1] + uy * pos)
        b = (start[0] + ux * min(pos + dash, distance), start[1] + uy * min(pos + dash, distance))
        draw.line([a, b], fill="#333333", width=width)
        pos += dash + gap


def point_with_offset(point, direction, amount):
    return point[0] + direction[0] * amount, point[1] + direction[1] * amount


def draw_cardinality(draw, point, direction, card, optional=False):
    # direction points toward the related table; draw the symbol just inside the line endpoint.
    ux, uy = direction
    px, py = -uy, ux
    base = point_with_offset(point, (-ux, -uy), 2)
    if optional:
        circle_center = point_with_offset(base, (-ux, -uy), 7)
        draw.ellipse((circle_center[0] - 5, circle_center[1] - 5, circle_center[0] + 5, circle_center[1] + 5), outline="#333333", width=2)
        base = point_with_offset(base, (-ux, -uy), 13)
    if card == "one":
        a = point_with_offset(base, (px, py), 9)
        b = point_with_offset(base, (-px, -py), 9)
        draw.line([a, b], fill="#333333", width=2)
    else:
        # Crow's foot: three short lines opening away from the endpoint.
        tip = base
        root = point_with_offset(base, (-ux, -uy), 15)
        draw.line([tip, point_with_offset(root, (px, py), 10)], fill="#333333", width=2)
        draw.line([tip, root], fill="#333333", width=2)
        draw.line([tip, point_with_offset(root, (-px, -py), 10)], fill="#333333", width=2)


def draw_table(draw, table: TableDef, f):
    x, y = table.x, table.y
    draw.rectangle((x, y, x + TABLE_W, y + TABLE_H), outline="#222222", width=2, fill="#FFFFFF")
    draw.rectangle((x, y, x + TABLE_W, y + HEADER_H), fill="#D3D3D3", outline="#222222", width=2)
    draw.text((x + 9, y + 6), table.name, font=f["table"], fill="#111111")
    for i, field in enumerate(table.fields):
        fy = y + HEADER_H + 4 + i * ROW_H
        if field.startswith("PK"):
            draw.text((x + 8, fy), "PK", font=f["key"], fill="#111111")
            value = field[3:]
        elif field.startswith("FK"):
            draw.text((x + 8, fy), "FK", font=f["key"], fill="#111111")
            value = field[3:]
        else:
            value = field
        draw.text((x + 46, fy), value, font=f["key"] if field.startswith(("PK", "FK")) else f["field"], fill="#111111")


def draw_png(path: Path):
    image = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(image)
    f = fonts()
    draw.text((40, 28), "SWE Autopilot — Whole Project Entity Relationship Diagram", font=f["title"], fill="#111111")
    draw.text((40, 68), "Logical database design; PK = primary key, FK = foreign key; crow's-foot notation shows cardinality", font=f["subtitle"], fill="#333333")
    draw.line((40, 99, WIDTH - 40, 99), fill="#111111", width=2)
    draw.text((40, 109), "FYP-I and FYP-II entities are shown together for the complete platform model.", font=f["subtitle"], fill="#333333")

    tables = table_map()
    for rel in RELATIONS:
        source, target = tables[rel.source], tables[rel.target]
        start, end = edge_points(source, target)
        dashed_line(draw, start, end)
        dx, dy = end[0] - start[0], end[1] - start[1]
        dist = max(1.0, (dx * dx + dy * dy) ** 0.5)
        direction = (dx / dist, dy / dist)
        draw_cardinality(draw, start, direction, rel.source_card, rel.source_optional)
        draw_cardinality(draw, end, (-direction[0], -direction[1]), rel.target_card, rel.target_optional)

    for table in TABLES:
        draw_table(draw, table, f)

    # Legend styled like a small table header/field sample.
    lx, ly = 1840, 660
    draw.rectangle((lx, ly, lx + 430, ly + 112), outline="#222222", width=2, fill="#FFFFFF")
    draw.rectangle((lx, ly, lx + 430, ly + 29), fill="#D3D3D3", outline="#222222", width=2)
    draw.text((lx + 10, ly + 6), "Notation", font=f["table"], fill="#111111")
    draw.text((lx + 12, ly + 38), "PK", font=f["key"], fill="#111111")
    draw.text((lx + 48, ly + 38), "Primary key", font=f["field"], fill="#111111")
    draw.text((lx + 12, ly + 61), "FK", font=f["key"], fill="#111111")
    draw.text((lx + 48, ly + 61), "Foreign key", font=f["field"], fill="#111111")
    draw.text((lx + 12, ly + 84), "○<", font=f["key"], fill="#111111")
    draw.text((lx + 48, ly + 84), "Optional many relationship", font=f["field"], fill="#111111")
    image.save(path, "PNG", optimize=True)


def draw_pdf(path: Path, png_path: Path):
    page_width, page_height = landscape((11 * 72, 8.5 * 72))
    pdf = canvas.Canvas(str(path), pagesize=(page_width, page_height))
    image = Image.open(png_path)
    scale = min((page_width - 18) / image.width, (page_height - 18) / image.height)
    width, height = image.width * scale, image.height * scale
    pdf.drawImage(ImageReader(image), (page_width - width) / 2, (page_height - height) / 2, width=width, height=height, preserveAspectRatio=True, mask="auto")
    pdf.setTitle("SWE Autopilot Whole Project ERD - Crow's Foot")
    pdf.save()


def write_notes(path: Path):
    path.write_text(
        "# SWE Autopilot Whole Project ERD — Crow's-Foot Version\n\n"
        "This ERD uses the same table-and-relationship style as the supplied reference image. It is a proposed logical schema for the complete SWE Autopilot platform, including FYP-I and FYP-II entities.\n\n"
        "The current authentication prototype implements `tbUSERS`, `tbOAUTH_ACCOUNTS`, and `tbOAUTH_STATES` in SQLite. The remaining tables represent the planned full project database and require advisor review before implementation.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "SWE_Autopilot_Whole_Project_ERD_CrowFoot.png"
    pdf = OUT / "SWE_Autopilot_Whole_Project_ERD_CrowFoot.pdf"
    notes = OUT / "SWE_Autopilot_Whole_Project_ERD_CrowFoot.md"
    draw_png(png)
    draw_pdf(pdf, png)
    write_notes(notes)
    print(png)
    print(pdf)
    print(notes)
