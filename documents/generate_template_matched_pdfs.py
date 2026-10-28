from __future__ import annotations

import sys
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

sys.path.insert(0, str(Path(__file__).parent))
from generate_fyp1_documents import (  # noqa: E402
    DATE,
    FEATURES,
    LONG_TITLE,
    ORGANIZATION,
    PROJECT,
    SUPERVISOR,
    TEAM,
    Feature,
    add_references,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "documents"
FONT_DIR = Path("C:/Windows/Fonts")

pdfmetrics.registerFont(TTFont("TimesNewRoman", str(FONT_DIR / "times.ttf")))
pdfmetrics.registerFont(TTFont("TimesNewRoman-Bold", str(FONT_DIR / "timesbd.ttf")))
pdfmetrics.registerFont(TTFont("TimesNewRoman-Italic", str(FONT_DIR / "timesi.ttf")))
pdfmetrics.registerFont(TTFont("TimesNewRoman-BoldItalic", str(FONT_DIR / "timesbi.ttf")))


class TemplateDocTemplate(BaseDocTemplate):
    def __init__(self, filename, pagesize, short_title, **kwargs):
        super().__init__(filename, pagesize=pagesize, **kwargs)
        self.short_title = short_title
        margin = 0.85 * inch
        frame = Frame(
            margin,
            margin,
            pagesize[0] - 2 * margin,
            pagesize[1] - 2 * margin,
            leftPadding=0,
            rightPadding=0,
            topPadding=0,
            bottomPadding=0,
            id="normal",
        )
        self.addPageTemplates([PageTemplate(id="normal", frames=[frame], onPage=self._on_page)])

    def _on_page(self, canvas, doc):
        page = canvas.getPageNumber()
        if page == 1:
            return
        width, height = doc.pagesize
        canvas.saveState()
        canvas.setFont("TimesNewRoman-Italic", 9)
        canvas.drawString(0.85 * inch, height - 0.55 * inch, self.short_title)
        canvas.setFont("TimesNewRoman-Italic", 9)
        canvas.drawRightString(width - 0.85 * inch, height - 0.55 * inch, f"Page {page}")
        canvas.setFont("TimesNewRoman", 10)
        canvas.drawCentredString(width / 2, 0.45 * inch, str(page))
        canvas.restoreState()

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style = flowable.style.name
            level = {"Heading1": 0, "Heading2": 1, "Heading3": 2}.get(style)
            if level is not None:
                self.notify("TOCEntry", (level, flowable.getPlainText(), self.page))


def styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle("BodyTNR", fontName="TimesNewRoman", fontSize=12, leading=14.4, alignment=TA_JUSTIFY, spaceAfter=6))
    s.add(ParagraphStyle("BodyLeft", parent=s["BodyTNR"], alignment=TA_LEFT))
    s.add(ParagraphStyle("BodyCenter", parent=s["BodyTNR"], alignment=TA_CENTER))
    for name, size, leading, before, after in (("Heading1", 16, 19.2, 12, 6), ("Heading2", 14, 16.8, 10, 5), ("Heading3", 14, 16.8, 8, 4)):
        style = s[name]
        style.fontName = "TimesNewRoman-Bold"
        style.fontSize = size
        style.leading = leading
        style.alignment = TA_LEFT
        style.spaceBefore = before
        style.spaceAfter = after
        style.keepWithNext = True
    s.add(ParagraphStyle("CoverTitle", fontName="TimesNewRoman-Bold", fontSize=22, leading=25, alignment=TA_CENTER, spaceAfter=20))
    s.add(ParagraphStyle("CoverProject", fontName="TimesNewRoman-Bold", fontSize=18, leading=22, alignment=TA_CENTER, spaceAfter=12))
    s.add(ParagraphStyle("CoverMeta", fontName="TimesNewRoman", fontSize=12, leading=15, alignment=TA_CENTER, spaceAfter=5))
    s.add(ParagraphStyle("CoverMetaBold", fontName="TimesNewRoman-Bold", fontSize=12, leading=15, alignment=TA_CENTER, spaceAfter=5))
    s.add(ParagraphStyle("Small", fontName="TimesNewRoman", fontSize=10, leading=11.5, alignment=TA_LEFT))
    s.add(ParagraphStyle("SmallBold", fontName="TimesNewRoman-Bold", fontSize=10, leading=11.5, alignment=TA_LEFT))
    s.add(ParagraphStyle("Table", fontName="TimesNewRoman", fontSize=10.2, leading=11.7, alignment=TA_LEFT))
    s.add(ParagraphStyle("TableBold", fontName="TimesNewRoman-Bold", fontSize=10.2, leading=11.7, alignment=TA_LEFT))
    s.add(ParagraphStyle("TableCenter", fontName="TimesNewRoman", fontSize=10.2, leading=11.7, alignment=TA_CENTER))
    s.add(ParagraphStyle("Caption", fontName="TimesNewRoman-Bold", fontSize=10.5, leading=12, alignment=TA_CENTER, spaceBefore=2, spaceAfter=8))
    s.add(ParagraphStyle("TOCHeading", fontName="TimesNewRoman-Bold", fontSize=16, leading=19, alignment=TA_LEFT, spaceAfter=8))
    return s


S = styles()


def p(text, style="BodyTNR"):
    return Paragraph(text, S[style])


def clean(text: str) -> str:
    return escape(text).replace("\n", "<br/>")


def cell(text: str, bold=False, center=False):
    style = "TableCenter" if center else "TableBold" if bold else "Table"
    return Paragraph(clean(text), S[style])


def rich(text: str, style="Table"):
    return Paragraph(text, S[style])


def black_table(data, widths, header=False, repeatRows=0, padding=5):
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=repeatRows, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]
    if header:
        commands += [("FONTNAME", (0, 0), (-1, 0), "TimesNewRoman-Bold"), ("BACKGROUND", (0, 0), (-1, 0), colors.white)]
    t.setStyle(TableStyle(commands))
    return t


def caption(text):
    return p(text, "Caption")


def cover_story(document_type: str):
    return [
        Spacer(1, 1.1 * inch),
        Table([[p(document_type, "CoverTitle")]], colWidths=[6.4 * inch], style=[("LINEABOVE", (0, 0), (-1, -1), 1.5, colors.black), ("LINEBELOW", (0, 0), (-1, -1), 1.5, colors.black), ("TOPPADDING", (0, 0), (-1, -1), 18), ("BOTTOMPADDING", (0, 0), (-1, -1), 18)]),
        Spacer(1, 0.22 * inch),
        p("for", "CoverMetaBold"),
        p(PROJECT, "CoverProject"),
        p(LONG_TITLE, "CoverMetaBold"),
        Spacer(1, 0.2 * inch),
        p("Version 1.0 — Draft for Advisor Review", "CoverMetaBold"),
        Spacer(1, 0.28 * inch),
        p("Prepared by", "CoverMetaBold"),
        p(TEAM.replace("\n", "<br/>"), "CoverMeta"),
        Spacer(1, 0.08 * inch),
        p(ORGANIZATION, "CoverMeta"),
        Spacer(1, 0.08 * inch),
        p(f"Supervisor: {SUPERVISOR}", "CoverMeta"),
        Spacer(1, 0.08 * inch),
        p(f"Date created: {DATE}", "CoverMeta"),
        Spacer(1, 0.58 * inch),
        p("Copyright © 1999 by Karl E. Wiegers. Template adapted for academic project documentation.", "Small"),
        PageBreak(),
    ]


def toc_story(title="Table of Contents"):
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC0", fontName="TimesNewRoman-Bold", fontSize=12, leftIndent=0, firstLineIndent=0, leading=15),
        ParagraphStyle("TOC1", fontName="TimesNewRoman", fontSize=11.5, leftIndent=18, firstLineIndent=0, leading=14),
        ParagraphStyle("TOC2", fontName="TimesNewRoman", fontSize=11, leftIndent=36, firstLineIndent=0, leading=13),
    ]
    return [p(title, "TOCHeading"), toc, PageBreak()]


def revision_story():
    data = [
        [cell("Name", True), cell("Date", True), cell("Reason For Changes", True), cell("Version", True)],
        [cell("Abdul Wasay / Ahmed Hassan Sheikh"), cell(DATE), cell("Initial FYP-I baseline prepared for advisor review"), cell("1.0")],
    ]
    return [p("Revision History", "Heading1"), black_table(data, [1.7, 1.0, 3.55, 0.75], header=True), PageBreak()]


def add_bullets(story, items):
    for item in items:
        story.append(p(f"• {clean(item)}", "BodyTNR"))


def add_numbered(story, items):
    for i, item in enumerate(items, 1):
        story.append(p(f"{i}. {clean(item)}", "BodyTNR"))


def feature_summary_table(feature: Feature):
    rows = [
        [cell("Use Case Name", True), cell(feature.title)],
        [cell("Description", True), cell(feature.description)],
        [cell("Actors", True), cell(feature.actors)],
        [cell("Goal", True), cell(feature.goal)],
        [cell("Pre-Conditions", True), cell(feature.preconditions)],
    ]
    return black_table(rows, [1.65, 5.55])


def feature_steps_table(feature: Feature):
    rows = [[cell("Step", True, True), cell("User/Agent Action", True), cell("System Response", True)]]
    for i, (action, response) in enumerate(feature.steps, 1):
        rows.append([cell(str(i), center=True), cell(action), cell(response)])
    return black_table(rows, [0.55, 2.9, 3.75], header=True, repeatRows=1)


def feature_requirements_table(feature: Feature):
    rows = [[cell("Req.ID", True), cell("Description", True), cell("Priority", True), cell("Status", True)]]
    for req in feature.requirements:
        rows.append([cell(req.req_id), cell(req.description), cell(req.priority), cell("Pending")])
    return black_table(rows, [0.75, 4.55, 0.9, 1.0], header=True, repeatRows=1, padding=4)


def srs_feature_summary_table(feature: Feature):
    rows = [
        [cell("Feature ID", True), cell(f"FYP1-F{feature.number}")],
        [cell("Feature Name", True), cell(feature.title)],
        [cell("Description", True), cell(feature.description)],
        [cell("Priority", True), cell(feature.priority)],
        [cell("Scope", True), cell("FYP-I baseline; detailed flows are documented in the separate System Use Case Specification.")],
    ]
    return black_table(rows, [1.65, 5.55])


def use_case_outer_table(feature: Feature):
    step_parts = []
    for i, (action, response) in enumerate(feature.steps, 1):
        step_parts.append(rich(f"<b>{i}. User/Agent Action (Step {i}):</b> {clean(action)}<br/><b>System Response:</b> {clean(response)}", "Table"))
        if i != len(feature.steps):
            step_parts.append(Spacer(1, 4))
    step_block = [x for x in step_parts]
    alt_block = []
    for action, response in feature.alternate:
        alt_block.append(rich(f"<b>Action/Condition:</b> {clean(action)}<br/><b>System Response:</b> {clean(response)}", "Table"))
    ex_block = []
    for action, response in feature.exception:
        ex_block.append(rich(f"<b>Exception Condition:</b> {clean(action)}<br/><b>System Response:</b> {clean(response)}", "Table"))
    rows = [
        [rich(f"<b>Use Case Name:</b> {clean(feature.title)}", "Table")],
        [rich(f"<b>Description:</b> {clean(feature.description)}", "Table")],
        [rich(f"<b>Actors:</b> {clean(feature.actors)}", "Table")],
        [rich(f"<b>Goal:</b> {clean(feature.goal)}", "Table")],
        [rich(f"<b>Pre-Conditions:</b> {clean(feature.preconditions)}", "Table")],
        [rich("<b>Basic Course of Events / Main Flow</b>", "Table")],
        [step_block],
        [rich("<b>Alternate Flow (Invalid Inputs / Review Rejection)</b>", "Table")],
        [alt_block],
        [rich("<b>Exception Flow (System Errors)</b>", "Table")],
        [ex_block],
        [rich(f"<b>Post Conditions:</b> {clean(feature.postconditions)}", "Table")],
    ]
    table = Table(rows, colWidths=[7.2 * inch], hAlign="LEFT")
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_srs_pdf(path: Path):
    doc = TemplateDocTemplate(str(path), LETTER, f"Software Requirements Specification for {PROJECT}", leftMargin=0.85 * inch, rightMargin=0.85 * inch, topMargin=0.85 * inch, bottomMargin=0.85 * inch)
    story = cover_story("Software Requirements Specification") + toc_story() + revision_story()

    story += [p("1. Introduction", "Heading1"), p("1.1 Purpose", "Heading2")]
    story.append(p("This Software Requirements Specification defines the FYP-I requirements for SWE Autopilot, an AI-driven autonomous software engineering platform with a controlled multi-agent workflow. It covers the requirement analyzer, traceability, predictive risk analysis, Agent Runtime foundations, Architect/Critic review, code generation, Docker sandbox execution, initial verification, workspace management, and supporting authentication. FYP-II functions are explicitly outside this baseline."))
    story += [p("1.2 Document Conventions", "Heading2")]
    story.append(p("The document uses Times New Roman, 12-point body text, 1.2 line spacing, normal margins, and justified paragraphs. Main headings use 16-point bold text and subsection headings use 14-point bold text. Functional requirements use unique identifiers. Priority values are High, Medium, or Low. Status values are Pending until the advisor reviews and approves the baseline. The words shall and must identify mandatory requirements."))
    story += [p("1.3 Intended Audience and Reading Suggestions", "Heading2")]
    story.append(p("This SRS is intended for the project advisor, project team, developers, testers, and reviewers. Advisors should review Sections 1, 2, 4, and 5 for scope and acceptance criteria. Developers should use Sections 3 and 4 for interfaces and behavior. Testers should derive tests from the functional and nonfunctional requirements."))
    story += [p("1.4 Product Scope", "Heading2")]
    story.append(p("SWE Autopilot provides a web-based control plane that transforms natural-language software requirements into structured, traceable, and verifiable engineering work. A deterministic Agent Runtime controls LLM-based reasoning, tool permissions, artifact versions, execution evidence, and approval decisions. The FYP-I release demonstrates the foundation of this workflow for controlled full-stack web application development."))
    add_bullets(story, [
        "Analyze natural-language requirements and detect ambiguity, incompleteness, conflicts, and missing acceptance criteria.",
        "Create requirement IDs, user stories, acceptance criteria, and artifact relationships.",
        "Predict architectural, technical, performance, security, dependency, and implementation risks.",
        "Generate and critique architecture alternatives before implementation.",
        "Generate frontend, backend, API, database, configuration, test, and documentation artifacts through controlled agents.",
        "Execute generated software inside Docker and collect build/runtime evidence.",
        "Run the initial verification workflow and associate results with artifacts.",
    ])
    story += [p("1.5 References", "Heading2")]
    add_numbered(story, [
        "SWE Autopilot FYP Proposal, Complete Unified Document, October 7, 2026.",
        "Software Requirements Specification Template (2025), supplied by the project advisor.",
        "Sign Up Use Case Example, supplied by the project advisor.",
        "SWE Autopilot repository: https://github.com/sheikh4467/SWE-Autopilot",
    ])

    story += [p("2. Overall Description", "Heading1"), p("2.1 Product Perspective", "Heading2")]
    story.append(p("SWE Autopilot is a new self-contained web platform composed of a Next.js frontend, FastAPI backend, Agent Runtime, specialized SDLC agents, data storage, and controlled Docker execution. The frontend provides the landing/authentication experience, project workspace, requirements input, traceability view, risk review, architecture review, code-generation controls, and verification status. The target architecture uses PostgreSQL, Redis, LangGraph/LangChain, LLM providers, and Docker."))
    story += [p("2.2 Product Functions", "Heading2")]
    add_bullets(story, [
        "Register and authenticate project members using email/password and configured Google/GitHub OAuth.",
        "Create a project workspace and submit natural-language requirements.",
        "Compile requirements into structured artifacts and detect ambiguity.",
        "Maintain requirement-to-artifact traceability.",
        "Analyze and prioritize predictive risks.",
        "Coordinate Architect/Critic proposals and approval.",
        "Generate code with specialized agents under explicit permissions.",
        "Build and run code in a Docker sandbox.",
        "Collect initial verification evidence and preserve execution history.",
    ])
    story += [p("2.3 User Classes and Characteristics", "Heading2")]
    story.append(black_table([
        [cell("User Class", True), cell("Characteristics and Responsibilities", True)],
        [cell("Project Member / Developer"), cell("Creates workspaces, submits requirements, reviews artifacts, approves architecture, and inspects evidence.")],
        [cell("Advisor / Reviewer"), cell("Reviews scope, requirements, architecture decisions, evidence, and unresolved issues.")],
        [cell("System Administrator"), cell("Configures providers, repository access, execution limits, and environment settings.")],
        [cell("Agent / Runtime"), cell("Internal actors that analyze, propose, critique, generate, and coordinate under runtime controls.")],
    ], [2.0, 5.2], header=True, repeatRows=1))
    story += [p("2.4 Operating Environment", "Heading2"), p("The system shall operate as a browser-accessible web application. Development may use Windows, Linux, or macOS with a multi-core processor and at least 16 GB RAM recommended. The target stack includes Python 3.11+, Node.js, Docker Desktop, PostgreSQL, Redis, Git, a modern browser, and an LLM API or local Ollama model."), p("2.5 Design and Implementation Constraints", "Heading2")]
    add_bullets(story, [
        "The Agent Runtime shall control workflow state, tools, permissions, artifact versions, and approvals.",
        "Generated code shall execute through a restricted Docker sandbox rather than unrestricted host execution.",
        "OAuth client secrets, session secrets, and model keys shall be loaded from protected environment variables.",
        "FYP-I targets full-stack web applications; native desktop, embedded, hardware, and native mobile compilers are excluded.",
        "The architecture shall remain model-provider independent.",
    ])
    story += [p("2.6 User Documentation", "Heading2")]
    add_bullets(story, ["Quick-start guide", "Workspace and requirements guide", "Advisor review checklist", "Developer setup guide for OAuth, Docker, and model providers"])
    story += [p("2.7 Assumptions and Dependencies", "Heading2")]
    add_bullets(story, ["A modern browser and reachable deployment are available.", "Docker is available for sandbox execution.", "At least one LLM provider or local model is configured.", "The target project is stored in a Git repository.", "PostgreSQL and Redis are available for the target deployment."])

    story += [p("3. External Interface Requirements", "Heading1"), p("3.1 User Interfaces", "Heading2"), p("The frontend shall provide a responsive landing/authentication page with 3D visuals, scroll transitions, and clear Sign In and Create Account actions. The authenticated workspace shall provide views for requirements, traceability, risks, architecture, code generation, sandbox execution, and verification evidence. Forms shall show validation and actionable errors. Tables shall show IDs, priorities, versions, relationships, approval states, execution results, and verification evidence."), p("3.2 Hardware Interfaces", "Heading2"), p("No dedicated hardware interface is required. Docker may use CPU, memory, storage, and network resources subject to configured limits. Hardware-based development is outside FYP-I scope."), p("3.3 Software Interfaces", "Heading2")]
    story.append(black_table([
        [cell("Interface", True), cell("Purpose and Data Exchanged", True)],
        [cell("Next.js ↔ FastAPI"), cell("REST/JSON authentication, projects, requirements, artifacts, agent runs, and evidence." )],
        [cell("FastAPI ↔ PostgreSQL"), cell("Project, requirement, artifact, relationship, risk, architecture, execution, and evidence records.")],
        [cell("Agent Runtime ↔ LangGraph/LangChain"), cell("State transitions, messages, tool requests, permissions, and outcomes.")],
        [cell("Runtime ↔ LLM provider"), cell("Structured prompts and responses for analysis, architecture, critique, and generation.")],
        [cell("Runtime ↔ Docker"), cell("Build/run commands, restricted mounts, logs, exit status, and runtime results.")],
        [cell("Authentication ↔ Google/GitHub"), cell("Server-side OAuth authorization code, provider identity, email, and profile data.")],
    ], [2.0, 5.2], header=True, repeatRows=1))
    story += [p("3.4 Communications Interfaces", "Heading2"), p("Browser-to-backend communication shall use HTTP during local development and HTTPS in deployment. REST requests shall use JSON except for OAuth redirects. OAuth state shall be validated server-side. Authenticated sessions shall use HTTP-only cookies. Provider, LLM, and deployment communications shall use TLS-protected endpoints."), p("4. System Features", "Heading1"), p("This section defines the FYP-I system features and their functional requirements at SRS level. Detailed actors, preconditions, stimulus/response sequences, alternate flows, exception flows, and postconditions are maintained in the separate SWE Autopilot FYP-I System Use Case Specification. All statuses are Pending until the advisor reviews the document.")]
    for feature in FEATURES:
        story += [p(f"4.{feature.number} {feature.title}", "Heading2"), p(f"4.{feature.number}.1 Feature Summary", "Heading3")]
        story.append(srs_feature_summary_table(feature))
        story.append(caption(f"Table 4.{feature.number}.1. {feature.title} Feature Summary"))
        story += [p(f"4.{feature.number}.2 Functional Requirements", "Heading3")]
        story.append(feature_requirements_table(feature))
        story.append(caption(f"Table 4.{feature.number}.2. {feature.title} Functional Requirements"))

    story += [p("5. Other Nonfunctional Requirements", "Heading1"), p("5.1 Performance Requirements", "Heading2")]
    add_bullets(story, ["The landing page shall become interactive within 3 seconds in the target local environment.", "The backend shall return validation errors within 2 seconds under normal local load.", "A requirement analysis request shall show a running state within 3 seconds.", "Workspace views shall load the latest saved state within 3 seconds for the FYP-I target dataset.", "Docker execution shall stream or persist logs for inspection."])
    story += [p("5.2 Safety Requirements", "Heading2")]
    add_bullets(story, ["Generated code shall not run directly on the host when sandbox execution is required.", "The sandbox shall apply time, memory, storage, and process limits where supported.", "The runtime shall stop an execution that exceeds policy limits.", "Architecture and generated artifacts shall require explicit review before promotion."])
    story += [p("5.3 Security Requirements", "Heading2")]
    add_bullets(story, ["Passwords shall be stored only as strong one-way hashes.", "OAuth state shall be generated, validated, and consumed server-side.", "Sessions shall use HTTP-only cookies and shall not expose provider secrets in URLs.", "OAuth and LLM secrets shall be supplied through protected environment variables.", "Agent tools and artifacts shall be permission controlled and audited.", "Project data shall be isolated by user and workspace authorization."])
    story += [p("5.4 Software Quality Attributes", "Heading2")]
    story.append(black_table([[cell("Attribute", True), cell("Requirement", True)], [cell("Usability"), cell("A first-time project member should be able to create a workspace, submit a requirement, and find the first analysis result without external assistance.")], [cell("Correctness"), cell("An artifact shall not be marked verified without recorded execution or validation evidence.")], [cell("Reliability"), cell("Failed runs shall produce visible failure states and diagnostics.")], [cell("Maintainability"), cell("Frontend, backend, runtime, agents, and storage adapters shall be separable modules.")], [cell("Portability"), cell("The platform shall run in local Windows/Linux/macOS and container-capable deployment environments.")], [cell("Testability"), cell("Requirements shall have identifiable inputs, outputs, error paths, and evidence.")], [cell("Traceability"), cell("Requirements and artifacts shall carry stable IDs and relationships.")]], [1.5, 5.7], header=True, repeatRows=1))
    story += [p("5.5 Business Rules", "Heading2")]
    add_bullets(story, ["A project member may initiate analysis only for an authorized workspace.", "An LLM response alone shall not mark an artifact verified.", "Architecture decisions require a rationale and approval before controlled generation.", "Generated code must remain linked to the requirements and architecture that motivated it.", "FYP-II capabilities shall not be represented as completed FYP-I functionality."])
    story += [p("6. Other Requirements", "Heading1")]
    add_bullets(story, ["The system shall preserve timestamps and version identifiers for requirements, artifacts, runs, approvals, and evidence.", "The system shall support export of a project summary.", "The system shall support UTF-8 natural-language requirements and generated documentation.", "The system shall keep FYP-I and FYP-II scope labels visible in planning and review views."])
    story += [p("Appendix A: Glossary", "Heading1")]
    story.append(black_table([[cell("Term", True), cell("Definition", True)], [cell("Agent Runtime"), cell("Deterministic control layer for workflow state, permissions, artifacts, evidence, approvals, and audit history.")], [cell("Traceability"), cell("Relationships connecting requirements to downstream engineering artifacts and evidence.")], [cell("Docker Sandbox"), cell("Restricted environment for building and running generated software.")], [cell("Verification Evidence"), cell("Observable build, runtime, test, static-analysis, schema, or execution output.")], [cell("FYP-I"), cell("First semester scope covering requirements, runtime foundations, architecture, generation, sandboxing, and initial verification.")], [cell("LLM"), cell("Large Language Model used for reasoning or generation inside the controlled workflow.")]], [2.0, 5.2], header=True, repeatRows=1))
    story += [p("Appendix B: Analysis Models", "Heading1"), p("Top-level FYP-I data flow: Project Member → Requirement Input → Requirement Compiler → Structured Requirements / User Stories / Acceptance Criteria → Traceability Store → Risk Analyzer → Architect/Critic → Approved Architecture → Code Agents → Docker Sandbox → Verification Evidence → Project Workspace."), p("Primary traceability path: REQ-### → US-### → ARCH-### → API/COMPONENT → CODE ARTIFACT → TEST ARTIFACT → EXECUTION RUN → VERIFICATION EVIDENCE."), p("FYP-I state flow: Draft Requirement → Analyzed → Reviewed → Architecture Proposed → Architecture Approved → Code Generated → Sandbox Executed → Verification Passed / Failed / Escalated."), p("The complete logical ERD is intentionally maintained as a separate stand-alone document: SWE_Autopilot_Whole_Project_ERD_CrowFoot.pdf. It is not embedded in this SRS.")]
    story += [p("Appendix C: To Be Determined List", "Heading1")]
    story.append(black_table([[cell("TBD ID", True), cell("Open Item", True), cell("Owner / Resolution Point", True)], [cell("TBD-01"), cell("Final PostgreSQL schema and migration strategy."), cell("Team; platform-core design.")], [cell("TBD-02"), cell("Final LLM model/provider for the advisor demonstration."), cell("Team and advisor; before evaluation.")], [cell("TBD-03"), cell("Docker resource limits and network policy."), cell("Team; before sandbox verification.")], [cell("TBD-04"), cell("Advisor approval workflow and roles."), cell("Advisor and team; review-gate design.")], [cell("TBD-05"), cell("Benchmark dataset and acceptance thresholds."), cell("Team; before FYP-I evaluation.")]], [1.0, 4.2, 2.0], header=True, repeatRows=1))
    doc.multiBuild(story)


def build_use_case_pdf(path: Path):
    doc = TemplateDocTemplate(str(path), A4, f"FYP-I System Use Cases for {PROJECT}", leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    story = cover_story("FYP-I System Use Case Specification") + toc_story() + revision_story()
    story += [p("Purpose of This Document", "Heading1"), p("This document expands Section 4 of the SWE Autopilot SRS into system use cases using the exact organization of the supplied Sign Up Use Case Example. Every use case contains a description, actors, goal, preconditions, main flow, alternate flow, exception flow, postconditions, and functional requirements table. All statuses are Pending until advisor review.")]
    for feature in FEATURES:
        story += [PageBreak(), p(f"4.{feature.number}. {feature.title}", "Heading2"), p(f"4.{feature.number}.1. Description:", "Heading3"), p(feature.description), p(f"4.{feature.number}.2. Stimulus/Response Sequences:", "Heading3"), use_case_outer_table(feature), caption(f"Table {feature.number}. {feature.title} Stimulus/Response Sequences"), p(f"4.{feature.number}.3. Functional Requirements:", "Heading3"), feature_requirements_table(feature), caption(f"Table {feature.number}. {feature.title} Functional Requirements")]
    story += [PageBreak(), p("FYP-I Scope Boundary", "Heading1"), p("The following proposal features remain FYP-II scope and are intentionally excluded from these FYP-I use cases: What-If Development Simulator, Change-Impact and Consistency Engine, Testing Agent and selective test replay, Closed-Loop Debugging and Recovery, Defensive Red-Team Agent, Attack Memory, Controlled Rollback, Release Gate, Deployment, final SDLC reporting, benchmarking, and final defense preparation."), p("Advisor Review Checklist", "Heading1")]
    add_bullets(story, ["Confirm every use case has a clear actor, goal, precondition, main flow, alternate flow, exception flow, and postcondition.", "Confirm requirements are testable, necessary, unambiguous, and correctly prioritized.", "Confirm authentication and workspace functions remain supporting platform functions rather than replacing the core FYP-I contribution.", "Update every Status column after advisor review and record the revision in the Revision History table."])
    story += [p("References", "Heading1")]
    add_numbered(story, ["SWE Autopilot FYP Proposal, October 7, 2026.", "Software Requirements Specification Template (2025), supplied by the advisor.", "Sign Up Use Case Example, supplied by the advisor.", "SWE Autopilot repository: https://github.com/sheikh4467/SWE-Autopilot"])
    doc.multiBuild(story)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    srs = OUT / "SWE_Autopilot_FYP1_SRS_Template_Matched.pdf"
    use_cases = OUT / "SWE_Autopilot_FYP1_System_Use_Cases_Template_Matched.pdf"
    build_srs_pdf(srs)
    build_use_case_pdf(use_cases)
    print(srs)
    print(use_cases)
