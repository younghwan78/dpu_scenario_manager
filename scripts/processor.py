"""
DPU Scenario Processor — YAML → Static HTML Generator.

Supports multi-project structure:
  scenarios/
    projectA/
      01_lcd_idle.yaml
      ...
    projectB/
      ...

Generates:
  docs/
    index.html              (project selector dashboard)
    projectA/
      index.html             (scenario list for projectA)
      views/
        lcd_idle.html
        ...
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from schema import DpuScenario, load_all_scenarios

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
SCENARIO_DIR = PROJECT_DIR / "scenarios"
TEMPLATE_DIR = SCRIPT_DIR / "templates"
DOCS_DIR = PROJECT_DIR / "docs"


# ---------------------------------------------------------------------------
# Jinja2 setup
# ---------------------------------------------------------------------------
def _create_jinja_env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=False,
        keep_trailing_newline=True,
    )
    return env


# ---------------------------------------------------------------------------
# Scenario → template context
# ---------------------------------------------------------------------------
def _scenario_to_json(scenario: DpuScenario) -> str:
    """Serialize scenario to JSON for embedding in HTML."""
    data = scenario.model_dump()
    return json.dumps(data, ensure_ascii=False, indent=None)


def _build_viewer_context(scenario: DpuScenario, project_name: str) -> dict:
    """Build Jinja2 template context for a single scenario view."""
    sources = sorted(set(l.source for l in scenario.layers))
    total_bw_orig = sum(l.bw.original_gbps for l in scenario.layers)
    total_bw_eff = sum(
        l.bw.compressed_gbps if l.bw.compressed_gbps is not None else l.bw.original_gbps
        for l in scenario.layers
    )
    return {
        "scenario": scenario,
        "scenario_json": _scenario_to_json(scenario),
        "sources": sources,
        "total_bw_orig": total_bw_orig,
        "total_bw_eff": total_bw_eff,
        "project_name": project_name,
    }


def _build_project_index_context(
    project_name: str, scenarios: list[DpuScenario]
) -> dict:
    """Build Jinja2 template context for a project's scenario list."""
    cards = []
    for s in scenarios:
        sources = sorted(set(l.source for l in s.layers))
        total_bw = sum(
            l.bw.compressed_gbps if l.bw.compressed_gbps is not None else l.bw.original_gbps
            for l in s.layers
        )
        safe_name = s.name.lower().replace(" ", "_").replace("-", "_")
        cards.append({
            "name": s.name,
            "description": s.description,
            "filename": f"{safe_name}.html",
            "layer_count": len(s.layers),
            "display_resolution": (
                s.display.get("resolution", "N/A")
                if isinstance(s.display, dict)
                else s.display.resolution
            ),
            "total_bw": total_bw,
            "sources": sources,
        })
    return {
        "project_name": project_name,
        "scenarios": cards,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _build_root_index_context(
    projects: list[dict],
) -> dict:
    """Build context for the root project-selector dashboard."""
    return {
        "projects": projects,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# ---------------------------------------------------------------------------
# Discover projects
# ---------------------------------------------------------------------------
def _discover_projects(scenario_dir: Path) -> list[str]:
    """Return sorted list of project directory names."""
    return sorted(
        d.name
        for d in scenario_dir.iterdir()
        if d.is_dir() and any(d.glob("*.yaml"))
    )


# ---------------------------------------------------------------------------
# Generate
# ---------------------------------------------------------------------------
def generate(
    scenario_dir: Path | None = None,
    output_dir: Path | None = None,
) -> list[Path]:
    """
    Main entry point: discover projects, load scenarios, generate HTML.

    Directory structure:
      scenarios/{project}/*.yaml  →  docs/{project}/views/*.html
                                     docs/{project}/index.html
                                     docs/index.html  (project selector)
    """
    scenario_dir = scenario_dir or SCENARIO_DIR
    output_dir = output_dir or DOCS_DIR

    # Discover project subdirectories
    project_names = _discover_projects(scenario_dir)
    if not project_names:
        print("⚠  No project directories found in:", scenario_dir)
        return []

    env = _create_jinja_env()
    generated: list[Path] = []
    project_summaries: list[dict] = []

    for project_name in project_names:
        proj_scenario_dir = scenario_dir / project_name
        proj_output_dir = output_dir / project_name
        proj_views_dir = proj_output_dir / "views"

        # Clean and recreate
        if proj_views_dir.exists():
            shutil.rmtree(proj_views_dir)
        proj_views_dir.mkdir(parents=True, exist_ok=True)

        # Load scenarios
        scenarios = load_all_scenarios(proj_scenario_dir)
        if not scenarios:
            print(f"  ⚠  No YAML files in: {proj_scenario_dir}")
            continue

        print(f"\n📁 Project: {project_name} ({len(scenarios)} scenarios)")

        # --- Render viewer pages ---
        viewer_tpl = env.get_template("viewer.html.j2")
        for scenario in scenarios:
            ctx = _build_viewer_context(scenario, project_name)
            html = viewer_tpl.render(**ctx)

            safe_name = scenario.name.lower().replace(" ", "_").replace("-", "_")
            out_path = proj_views_dir / f"{safe_name}.html"
            out_path.write_text(html, encoding="utf-8")
            generated.append(out_path)
            print(f"  ✅ {out_path.relative_to(output_dir.parent)}")

        # --- Render project index ---
        proj_index_tpl = env.get_template("project_index.html.j2")
        proj_ctx = _build_project_index_context(project_name, scenarios)
        proj_html = proj_index_tpl.render(**proj_ctx)
        proj_index_path = proj_output_dir / "index.html"
        proj_index_path.write_text(proj_html, encoding="utf-8")
        generated.append(proj_index_path)
        print(f"  ✅ {proj_index_path.relative_to(output_dir.parent)}")

        # Collect summary for root dashboard
        all_sources = set()
        total_layers = 0
        for s in scenarios:
            total_layers += len(s.layers)
            for l in s.layers:
                all_sources.add(l.source)

        project_summaries.append({
            "name": project_name,
            "scenario_count": len(scenarios),
            "total_layers": total_layers,
            "sources": sorted(all_sources),
        })

    # --- Render root index (project selector) ---
    root_tpl = env.get_template("index.html.j2")
    root_ctx = _build_root_index_context(project_summaries)
    root_html = root_tpl.render(**root_ctx)
    root_path = output_dir / "index.html"
    root_path.write_text(root_html, encoding="utf-8")
    generated.append(root_path)
    print(f"\n  ✅ {root_path.relative_to(output_dir.parent)}")

    return generated


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DPU Scenario → HTML Generator")
    parser.add_argument("--scenarios", type=Path, default=SCENARIO_DIR,
                        help="Path to scenarios directory")
    parser.add_argument("--output", type=Path, default=DOCS_DIR,
                        help="Path to output docs directory")
    args = parser.parse_args()

    print(f"\n🔄 Processing scenarios from: {args.scenarios}")
    files = generate(args.scenarios, args.output)
    print(f"\n✨ Generated {len(files)} files → {args.output}\n")
