from __future__ import annotations

import html
import json
import traceback
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from threading import Event

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtGui import QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from rc_single_span.core.models import BridgeProject
from rc_single_span.core.progress import AnalysisCancelled, AnalysisControl
from rc_single_span.research.study import _reference_config, run_research_study


class _ResearchSignals(QObject):
    finished = Signal(object, object)
    error = Signal(str)
    progress = Signal(str, int, int)
    cancelled = Signal()


class _ResearchWorker(QRunnable):
    def __init__(
        self,
        project: BridgeProject,
        config: dict[str, object],
        output_directory: Path,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self.project = project
        self.config = config
        self.output_directory = output_directory
        self.cancel_event = cancel_event
        self.signals = _ResearchSignals()

    @Slot()
    def run(self) -> None:
        try:
            def progress(phase: str, completed: int, total: int) -> None:
                self.signals.progress.emit(phase, completed, total)

            reference = _reference_config(self.config)
            summary = run_research_study(
                self.project,
                self.config,
                self.output_directory,
                reference_config=reference,
                control=AnalysisControl(progress, self.cancel_event.is_set),
                exploratory=self.config.get("assumptions_confirmed") is not True,
            )
        except AnalysisCancelled:
            self.signals.cancelled.emit()
            return
        except Exception:  # noqa: BLE001 - worker must return study errors to the UI.
            self.signals.error.emit(traceback.format_exc())
            return
        self.signals.finished.emit(summary, self.output_directory)


def _cell(value: object) -> str:
    return html.escape(str(value))


def _number(value: object, digits: int = 4) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}g}"
    except (TypeError, ValueError):
        return _cell(value)


def _table(headers: tuple[str, ...], rows: list[tuple[object, ...]]) -> str:
    header = "".join(f"<th>{_cell(item)}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_cell(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def render_research_report(summary: dict[str, object]) -> str:
    """Render a traceable study sheet from the frozen run summary."""

    baseline = summary.get("baseline", {})
    if not isinstance(baseline, dict):
        baseline = {}
    metrics = summary.get("held_out_test_metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    names = metrics.get("target_names", [])
    rmse = metrics.get("rmse", [])
    mae = metrics.get("mae", [])
    r2 = metrics.get("r2", [])
    metric_rows = [
        (name, _number(rmse[index]), _number(mae[index]), _number(r2[index]))
        for index, name in enumerate(names)
        if index < len(rmse) and index < len(mae) and index < len(r2)
    ]

    distributions = summary.get("random_variables", [])
    distribution_rows = []
    if isinstance(distributions, list):
        for variable in distributions:
            if isinstance(variable, dict):
                distribution_rows.append((
                    variable.get("name"), variable.get("family"), variable.get("mean"),
                    variable.get("cov"), variable.get("std"), variable.get("lower"),
                    variable.get("upper"),
                ))

    boundary_rows: list[tuple[object, ...]] = []
    boundary = summary.get("direct_boundary_challenges", [])
    if isinstance(boundary, list):
        for item in boundary:
            if isinstance(item, dict):
                boundary_rows.append((
                    item.get("target_name"),
                    "Bracket found" if item.get("bracket_found") else "No bracket found",
                    _number(item.get("direct_margin")),
                    _number(item.get("surrogate_margin")),
                    _number(item.get("absolute_error")),
                ))

    reliability_rows: list[tuple[object, ...]] = []
    for method_key, label in (
        ("form", "FORM (ANN)"),
        ("surrogate_monte_carlo", "Monte Carlo (ANN)"),
        ("direct_monte_carlo", "Monte Carlo (direct evaluator)"),
    ):
        method = summary.get(method_key, {})
        if isinstance(method, dict):
            for target_name, item in method.items():
                if not isinstance(item, dict):
                    continue
                ci = (
                    f"{_number(item.get('confidence_low'))}–{_number(item.get('confidence_high'))}"
                    if item.get("confidence_low") is not None else "—"
                )
                reliability_rows.append((
                    target_name,
                    label,
                    _number(item.get("probability_of_failure")),
                    _number(item.get("beta" if label.startswith("FORM") else "reliability_index")),
                    ci,
                    "Converged" if item.get("converged", True) else "Not converged",
                ))

    convergence_rows: list[tuple[object, ...]] = []
    convergence = summary.get("sample_size_convergence")
    if isinstance(convergence, dict):
        for point in convergence.get("points", []):
            if isinstance(point, dict):
                convergence_rows.append((
                    point.get("sample_count"),
                    point.get("seed"),
                    _number(point.get("maximum_standardized_change"), 3),
                    point.get("converged_from_previous"),
                ))

    gates = summary.get("evidence_gate", {})
    gate_rows = []
    if isinstance(gates, dict):
        for item in gates.get("items", []):
            if isinstance(item, dict):
                gate_rows.append((
                    item.get("title"),
                    str(item.get("state", "")).replace("_", " ").title(),
                    item.get("evidence"),
                    item.get("remaining"),
                ))

    rbdo = summary.get("rbdo")
    rbdo_summary = "RBDO was not run."
    if isinstance(rbdo, dict):
        rbdo_summary = (
            f"Status: {'PASS' if rbdo.get('success') else 'NO FEASIBLE / NOT CONVERGED'}; "
            f"objective {_number(rbdo.get('objective'))}; iterations {rbdo.get('iterations')}; "
            f"message: {_cell(rbdo.get('message', ''))}."
        )

    project_name = baseline.get("project_name", "Bridge project")
    status = summary.get("status", "Research status unavailable")
    split = summary.get("split_rows", {})
    if not isinstance(split, dict):
        split = {}
    limit_states = summary.get("nominal_limit_states", {})
    if not isinstance(limit_states, dict):
        limit_states = {}
    limit_values = limit_states.get("values", {})
    if not isinstance(limit_values, dict):
        limit_values = {}
    variables_by_name = {
        item.get("name"): item for item in distributions if isinstance(item, dict)
    }

    def variable_mean(name: str) -> float:
        item = variables_by_name.get(name)
        if not isinstance(item, dict):
            return 1.0
        if item.get("family") == "uniform":
            lower, upper = item.get("lower"), item.get("upper")
            if lower is not None and upper is not None:
                return 0.5 * (float(lower) + float(upper))
        return float(item["mean"]) if item.get("mean") is not None else 1.0

    dead_factor = variable_mean("dead_load_factor")
    live_factor = variable_mean("live_load_factor")
    moment_effect_factor = variable_mean("moment_load_model_factor")
    shear_effect_factor = variable_mean("shear_load_model_factor")
    moment_resistance_factor = variable_mean("flexure_resistance_model_factor")
    shear_resistance_factor = variable_mean("shear_resistance_model_factor")
    moment_substitution = (
        "S_M = θ_EM × (γD × M_G,k + γL × M_Q,k) = "
        f"{moment_effect_factor:.4g} × ({dead_factor:.4g} × "
        f"{_number(baseline.get('permanent_moment_knm'))} + {live_factor:.4g} × "
        f"{_number(baseline.get('traffic_moment_knm'))}) = "
        f"{_number(limit_values.get('moment_effect_knm'))} kNm (M_Ed); "
        f"M_R = θ_RM × M_R,EC2 = {moment_resistance_factor:.4g} × "
        f"{_number(limit_values.get('nominal_moment_resistance_knm'))} = "
        f"{_number(limit_values.get('moment_resistance_knm'))} kNm; "
        f"gM = {_number(limit_values.get('g_flexure_knm'))} kNm"
    )
    shear_substitution = (
        "S_V = θ_EV × (γD × V_G,k + γL × V_Q,k) = "
        f"{shear_effect_factor:.4g} × ({dead_factor:.4g} × "
        f"{_number(baseline.get('permanent_shear_kn'))} + {live_factor:.4g} × "
        f"{_number(baseline.get('traffic_shear_kn'))}) = "
        f"{_number(limit_values.get('shear_effect_kn'))} kN (V_Ed); "
        f"V_R = θ_RV × V_R,EC2 = {shear_resistance_factor:.4g} × "
        f"{_number(limit_values.get('nominal_shear_resistance_kn'))} = "
        f"{_number(limit_values.get('shear_resistance_kn'))} kN; "
        f"gV = {_number(limit_values.get('g_shear_kn'))} kN"
    )
    deflection_limit = _number(
        summary.get("limit_state_model", {}).get("deflection_limit_mm")
        if isinstance(summary.get("limit_state_model"), dict) else None
    )
    deflection_substitution = (
        "δ = s_I × (γD × δ_G + γL × δ_Q) = "
        f"{_number(limit_values.get('deflection_stiffness_scale'))} × "
        f"({dead_factor:.4g} × {_number(baseline.get('permanent_deflection_mm'))} + "
        f"{live_factor:.4g} × {_number(baseline.get('traffic_deflection_mm'))}) = "
        f"{_number(limit_values.get('deflection_mm'))} mm; "
        f"δ_lim = {deflection_limit} mm; "
        f"gδ = {_number(limit_values.get('g_deflection_mm'))} mm"
    )

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body {{ font-family: Arial, sans-serif; color: #24344a; font-size: 9pt; }}
h1 {{ color: #193653; font-size: 19pt; }} h2 {{ color: #245b85; font-size: 12pt; margin-top: 18pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0; }}
th, td {{ border: 1px solid #bfccd6; padding: 4pt; text-align: left; vertical-align: top; }}
th {{ background: #e9f1f6; }} .notice {{ border: 1px solid #b79b58; background: #fff9e7; padding: 8pt; }}
.sheet {{ page-break-before: always; }}
</style></head><body>
<h1>ANN, Reliability and RBDO Research Study Sheets</h1>
<p>Study bridge: {_cell(project_name)}<br>Analysis route: BS EN 1990 / 1991-2 / 1992-2<br>
LM1 step: {_number(baseline.get('lm1_step_m'))} m</p>
<p class="notice"><b>{_cell(status)}</b><br>All probability, traffic and dependence inputs must be
source-justified for the thesis. Exploratory outputs do not approve a bridge or establish
the required reliability target.</p>

<h2>Reference response and limit states</h2>
<p>Physical response baseline: {_cell(baseline.get('provenance', ''))}<br>
Deflection basis: {_cell(baseline.get('deflection_basis', ''))}</p>
<p><b>Limit states:</b> gM = MR − MEd; gV = VR − VEd; gδ = δlim − δ.<br>
{_cell(moment_substitution)}<br>{_cell(shear_substitution)}<br>
{_cell(deflection_substitution)}<br>
Mean-vector margins: gM = {_number(limit_values.get('g_flexure_knm'))} kNm;
gV = {_number(limit_values.get('g_shear_kn'))} kN;
gδ = {_number(limit_values.get('g_deflection_mm'))} mm.</p>
<p>Governing girder indices: moment {baseline.get('moment_girder_index')}, shear
{baseline.get('shear_girder_index')}, deflection {baseline.get('deflection_girder_index')}.</p>

<h2>Random variables and distributions</h2>
{_table(('Variable', 'Distribution', 'Mean', 'COV', 'SD', 'Lower', 'Upper'), distribution_rows)}

<h2>Dataset and ANN validation</h2>
<p>LHS samples: {summary.get('dataset_rows')} (invalid {summary.get('invalid_dataset_rows')});
split: train {split.get('train')}, validation {split.get('validation')}, test {split.get('test')}.</p>
{_table(('Limit state', 'Test RMSE', 'Test MAE', 'Test R²'), metric_rows)}
{_table(('Target', 'Direct boundary result', 'Direct margin', 'ANN margin', 'Absolute error'), boundary_rows)}

<h2>Reliability cross-checks</h2>
{_table(('Limit state', 'Method', 'Pf', 'β', '95% CI', 'Convergence'), reliability_rows)}

<h2>Sample-size convergence</h2>
{_table(('N', 'Seed', 'Maximum standardized change', 'Within tolerance'), convergence_rows)}

<h2>RBDO</h2><p>{rbdo_summary}</p>
<p>Candidate direct check: {_cell(summary.get('rbdo_candidate_direct', 'Not available'))}</p>

<h2>Evidence gates</h2>
{_table(('Gate', 'State', 'Evidence', 'Remaining work'), gate_rows)}

<h2>Reproducibility register</h2>
<p>Config SHA-256: {_cell(summary.get('config_sha256'))}<br>
Bridge-project SHA-256: {_cell(summary.get('project_sha256'))}<br>
Artifact hashes and numerical records are in summary.json.</p>
</body></html>"""


class ResearchWorkspace(QWidget):
    """Interactive research tab; runs the stochastic workflow off the GUI thread."""

    def __init__(self, project_provider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_provider = project_provider
        self._pool = QThreadPool.globalInstance()
        self._cancel_event: Event | None = None
        self._worker: _ResearchWorker | None = None
        self._summary: dict[str, object] | None = None
        self._report_html: str | None = None
        self._config_path: Path | None = None
        self._output_path: Path | None = None
        self._config = self._load_packaged_config()
        self._build_ui()
        self._populate_controls()
        self._render_idle_state()

    @staticmethod
    def _load_packaged_config() -> dict[str, object]:
        resource = files("rc_single_span.research").joinpath(
            "data/provisional_exploratory_config.json"
        )
        return json.loads(resource.read_text(encoding="utf-8"))

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        header = QLabel(
            "Research workbench — ANN / reliability / RBDO\n"
            "The study uses the bridge geometry currently shown in this project. "
            "Inputs and outputs are frozen into the study record."
        )
        header.setWordWrap(True)
        header.setStyleSheet(
            "font-size: 13pt; font-weight: 700; color: #173d59; padding: 6px;"
        )
        root.addWidget(header)

        columns = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)

        self.assumption_notice = QLabel()
        self.assumption_notice.setWordWrap(True)
        self.assumption_notice.setStyleSheet(
            "background: #fff6df; border: 1px solid #d1b46e; padding: 8px; color: #593f08;"
        )
        left_layout.addWidget(self.assumption_notice)

        controls_group = QGroupBox("Study controls")
        controls_form = QFormLayout(controls_group)
        self.sample_count = QSpinBox()
        self.sample_count.setRange(100, 1_000_000)
        self.direct_mc_count = QSpinBox()
        self.direct_mc_count.setRange(0, 10_000_000)
        self.validation_count = QSpinBox()
        self.validation_count.setRange(10, 1_000_000)
        self.lm1_step = QDoubleSpinBox()
        self.lm1_step.setRange(0.1, 20.0)
        self.lm1_step.setDecimals(2)
        self.lm1_step.setSingleStep(0.1)
        controls_form.addRow("LHS training samples", self.sample_count)
        controls_form.addRow("Fresh direct validation", self.validation_count)
        controls_form.addRow("Direct Monte Carlo samples", self.direct_mc_count)
        controls_form.addRow("Research LM1 step (m)", self.lm1_step)
        left_layout.addWidget(controls_group)

        variables_group = QGroupBox("Random-variable model (edit cells before running)")
        variables_layout = QVBoxLayout(variables_group)
        self.variables_table = QTableWidget(0, 7)
        self.variables_table.setHorizontalHeaderLabels(
            ("Variable", "Family", "Mean", "COV", "SD", "Lower", "Upper")
        )
        self.variables_table.horizontalHeader().setStretchLastSection(True)
        self.variables_table.setAlternatingRowColors(True)
        variables_layout.addWidget(self.variables_table)
        left_layout.addWidget(variables_group, 1)

        self.config_path_label = QLabel("Using packaged provisional study configuration")
        self.config_path_label.setWordWrap(True)
        left_layout.addWidget(self.config_path_label)
        config_buttons = QHBoxLayout()
        self.load_button = QPushButton("Load JSON")
        self.load_button.clicked.connect(self._load_config_dialog)
        self.save_button = QPushButton("Save JSON")
        self.save_button.clicked.connect(self._save_config_dialog)
        config_buttons.addWidget(self.load_button)
        config_buttons.addWidget(self.save_button)
        left_layout.addLayout(config_buttons)

        output_row = QHBoxLayout()
        self.output_folder = QLineEdit(str(Path.home() / "Documents" / "RCBridgeStudies"))
        self.output_folder.setPlaceholderText("Study output folder")
        self.browse_output_button = QPushButton("Browse…")
        self.browse_output_button.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_folder, 1)
        output_row.addWidget(self.browse_output_button)
        left_layout.addLayout(output_row)

        run_row = QHBoxLayout()
        self.run_button = QPushButton("Run research study")
        self.run_button.clicked.connect(self._run_study)
        self.cancel_button = QPushButton("Cancel run")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_study)
        self.pdf_button = QPushButton("Export study PDF")
        self.pdf_button.setEnabled(False)
        self.pdf_button.clicked.connect(self._export_pdf)
        run_row.addWidget(self.run_button)
        run_row.addWidget(self.cancel_button)
        run_row.addWidget(self.pdf_button)
        left_layout.addLayout(run_row)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        self.evidence_gate = QTableWidget(0, 3)
        self.evidence_gate.setHorizontalHeaderLabels(("Research gate", "State", "Open evidence")
        )
        self.evidence_gate.horizontalHeader().setStretchLastSection(True)
        self.evidence_gate.setMaximumHeight(190)
        right_layout.addWidget(self.evidence_gate)
        progress_row = QHBoxLayout()
        self.progress_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_row.addWidget(self.progress_label, 1)
        progress_row.addWidget(self.progress_bar, 2)
        right_layout.addLayout(progress_row)
        self.result_view = QTextBrowser()
        self.result_view.setOpenExternalLinks(True)
        right_layout.addWidget(self.result_view, 1)

        columns.addWidget(left)
        columns.addWidget(right)
        columns.setSizes([470, 690])
        root.addWidget(columns, 1)

    def _populate_controls(self) -> None:
        pipeline = self._config.get("pipeline", {})
        validation = self._config.get("validation", {})
        reference = self._config.get("reference_run", {})
        if not isinstance(pipeline, dict) or not isinstance(validation, dict):
            raise TypeError("Packaged study configuration has invalid pipeline/validation sections.")
        if not isinstance(reference, dict):
            raise TypeError("Packaged study configuration has invalid reference_run section.")
        self.sample_count.setValue(int(pipeline.get("sample_count", 1500)))
        self.validation_count.setValue(int(validation.get("fresh_direct_samples", 250)))
        self.direct_mc_count.setValue(int(validation.get("direct_monte_carlo_samples", 0)))
        self.lm1_step.setValue(float(reference.get("lm1_longitudinal_step_m", 3.0)))
        self._populate_variables()
        confirmed = self._config.get("assumptions_confirmed") is True
        self.assumption_notice.setText(
            "CONFIRMED INPUT BASIS: run will be reported for review; research acceptance gates still apply."
            if confirmed else
            "EXPLORATORY ONLY — the packaged priors, action multipliers, dependence choice, "
            "traffic representation and serviceability criterion are not confirmed study inputs."
        )
        self._populate_gate(self._config.get("evidence_gate"))

    def _populate_variables(self) -> None:
        variables = self._config.get("random_variables", [])
        if not isinstance(variables, list):
            raise TypeError("random_variables must be a list.")
        self.variables_table.setRowCount(len(variables))
        for row, variable in enumerate(variables):
            if not isinstance(variable, dict):
                raise TypeError("Every random variable must be an object.")
            values = (
                variable.get("name"), variable.get("family"), variable.get("mean"),
                variable.get("cov"), variable.get("std"), variable.get("lower"),
                variable.get("upper"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if column == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.variables_table.setItem(row, column, item)

    def _populate_gate(self, gate: object = None) -> None:
        rows: list[tuple[str, str, str]] = []
        if isinstance(gate, dict) and isinstance(gate.get("items"), list):
            for item in gate["items"]:
                if isinstance(item, dict):
                    state = str(item.get("state", "open")).replace("_", " ").upper()
                    rows.append((str(item.get("title", item.get("key", "Gate"))),
                                 state, str(item.get("remaining", ""))))
        if not rows:
            rows = [
                ("Probabilistic assumptions", "OPEN", "Source/action/dependence basis not confirmed"),
                ("Sample-size convergence", "OPEN", "Must pass on the adopted study inputs"),
                ("ANN near-boundary validation", "OPEN", "Direct checks at g = 0 are required"),
                ("Reliability cross-check", "OPEN", "FORM and direct Monte Carlo need review"),
                ("Target reliability", "REVIEW", "CC2 / 50-year is a thesis scenario"),
                ("RBDO candidate", "OPEN", "Directly verify feasible buildable design"),
            ]
        if self._summary:
            convergence = self._summary.get("sample_size_convergence")
            if isinstance(convergence, dict):
                points = convergence.get("points", [])
                tolerance = float(convergence.get("tolerance", 0.05))
                changes = [
                    float(point["maximum_standardized_change"])
                    for point in points
                    if isinstance(point, dict)
                    and point.get("maximum_standardized_change") is not None
                ]
                stable = bool(changes) and all(value <= tolerance for value in changes)
                rows.append(("This run: response-statistic stability",
                             "PASS" if stable else "FAIL / OPEN",
                             f"Largest adjacent change {_number(max(changes), 3)}; limit {tolerance:.1%}"))
            boundary = self._summary.get("direct_boundary_challenges", [])
            if isinstance(boundary, list) and boundary:
                no_bracket = [
                    str(item.get("target_name")) for item in boundary
                    if isinstance(item, dict) and not item.get("bracket_found")
                ]
                rows.append(("This run: direct boundary search",
                             "REVIEW REQUIRED" if no_bracket else "MEASURED; REVIEW",
                             "No bracket: " + ", ".join(no_bracket) if no_bracket
                             else "Boundary predictions are diagnostics, not acceptance"))
            rbdo = self._summary.get("rbdo")
            if isinstance(rbdo, dict):
                rows.append(("This run: RBDO candidate",
                             "FEASIBLE" if rbdo.get("success") else "NO FEASIBLE RESULT",
                             str(rbdo.get("message", ""))))
            elif rbdo is None:
                rows.append(("This run: RBDO candidate", "NOT RUN", ""))
        self.evidence_gate.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.evidence_gate.setItem(row, column, item)

    def _read_config(self) -> dict[str, object]:
        config = json.loads(json.dumps(self._config))
        pipeline = config.setdefault("pipeline", {})
        validation = config.setdefault("validation", {})
        reference = config.setdefault("reference_run", {})
        if not all(isinstance(item, dict) for item in (pipeline, validation, reference)):
            raise ValueError("Study configuration sections must be JSON objects.")
        pipeline["sample_count"] = self.sample_count.value()
        validation["fresh_direct_samples"] = self.validation_count.value()
        validation["direct_monte_carlo_samples"] = self.direct_mc_count.value()
        reference["lm1_longitudinal_step_m"] = self.lm1_step.value()
        raw_variables = []
        for row in range(self.variables_table.rowCount()):
            values = [
                self.variables_table.item(row, column).text().strip()
                if self.variables_table.item(row, column) is not None else ""
                for column in range(self.variables_table.columnCount())
            ]
            if not values[0]:
                raise ValueError(f"Random-variable row {row + 1} has no name.")
            converted: dict[str, object] = {"name": values[0], "family": values[1]}
            for key, value in zip(("mean", "cov", "std", "lower", "upper"), values[2:], strict=True):
                converted[key] = None if not value else float(value)
            raw_variables.append(converted)
        config["random_variables"] = raw_variables
        return config

    def _load_config_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load research study configuration", "", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise TypeError("Configuration root must be an object.")
            self._config = data
            self._config_path = Path(path)
            self._populate_controls()
            self.config_path_label.setText(str(self._config_path))
            self._render_idle_state()
        except Exception as exc:  # noqa: BLE001 - report malformed user input in the GUI.
            QMessageBox.warning(self, "Cannot load study configuration", str(exc))

    def _save_config_dialog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save research study configuration", "research_study.json", "JSON files (*.json)"
        )
        if not path:
            return
        try:
            data = self._read_config()
            Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            self._config = data
            self._config_path = Path(path)
            self.config_path_label.setText(str(self._config_path))
            QMessageBox.information(self, "Study configuration saved", f"Saved {path}")
        except Exception as exc:  # noqa: BLE001 - report malformed user input in the GUI.
            QMessageBox.warning(self, "Cannot save study configuration", str(exc))

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose study output folder", self.output_folder.text())
        if path:
            self.output_folder.setText(path)

    def _new_output_path(self) -> Path:
        parent = Path(self.output_folder.text()).expanduser()
        stamp = datetime.now(UTC).strftime("study_%Y%m%d_%H%M%S")
        candidate = parent / stamp
        suffix = 1
        while candidate.exists():
            candidate = parent / f"{stamp}_{suffix}"
            suffix += 1
        return candidate

    def _run_study(self) -> None:
        if self._worker is not None:
            return
        try:
            project = self._project_provider()
            config = self._read_config()
            output = self._new_output_path()
            if not output.parent.exists():
                output.parent.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Research study input error", str(exc))
            return
        self._cancel_event = Event()
        worker = _ResearchWorker(project, config, output, self._cancel_event)
        worker.signals.finished.connect(self._study_finished)
        worker.signals.error.connect(self._study_failed)
        worker.signals.progress.connect(self._progress_changed)
        worker.signals.cancelled.connect(self._study_cancelled)
        self._worker = worker
        self._summary = None
        self._report_html = None
        self.pdf_button.setEnabled(False)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Preparing study…")
        self.result_view.setHtml(
            "<h2>Research study running</h2><p>The deterministic BS EN baseline, LHS dataset, "
            "ANN, direct validation, reliability checks and configured RBDO will run in the "
            "background. Use Cancel to stop at the current cooperative-check point.</p>"
        )
        self._pool.start(worker)

    def _cancel_study(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.progress_label.setText("Cancellation requested…")
            self.cancel_button.setEnabled(False)

    def _progress_changed(self, phase: str, completed: int, total: int) -> None:
        percent = min(100, max(0, round(100 * completed / max(1, total))))
        self.progress_bar.setValue(percent)
        self.progress_label.setText(f"{phase} — {completed:,}/{total:,}")

    def _study_finished(self, summary: object, output: object) -> None:
        self._worker = None
        self._cancel_event = None
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if not isinstance(summary, dict):
            self._study_failed("Study worker returned an invalid summary.")
            return
        self._summary = summary
        self._output_path = Path(output)
        self._report_html = render_research_report(summary)
        self.result_view.setHtml(self._report_html)
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"Completed — {self._output_path}")
        self.pdf_button.setEnabled(True)
        self._populate_gate(summary.get("evidence_gate"))

    def _study_failed(self, message: str) -> None:
        self._worker = None
        self._cancel_event = None
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("Study failed; no accepted result was published")
        QMessageBox.critical(self, "Research study failed", message)

    def _study_cancelled(self) -> None:
        self._worker = None
        self._cancel_event = None
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.progress_label.setText("Study cancelled; partial files are not a completed study")

    def _export_pdf(self) -> None:
        if not self._report_html:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export research study sheets", "research_study_sheets.pdf", "PDF files (*.pdf)"
        )
        if not path:
            return
        try:
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            document = QTextDocument()
            document.setHtml(self._report_html)
            document.print_(printer)
            QMessageBox.information(self, "Study sheets exported", f"Saved {path}")
        except Exception as exc:  # noqa: BLE001 - report PDF creation errors to the UI.
            QMessageBox.warning(self, "Study PDF export failed", str(exc))

    def _render_idle_state(self) -> None:
        self.result_view.setHtml(
            "<h2>Study basis and release gates</h2>"
            "<p>The table on the left contains the provisional random-variable model. "
            "Edit or replace it, then save the configuration so the run can be reproduced.</p>"
            "<p>Run uses the current bridge geometry and the explicit BS EN search step shown above. "
            "The study record stores the project, configuration, sample splits, model and hashes.</p>"
            "<p>Research outputs remain pending until data sources, traffic actions, dependence, "
            "sample convergence, ANN boundary performance, reliability cross-checks and a "
            "directly verified feasible RBDO design pass review.</p>"
        )


__all__ = ["ResearchWorkspace", "render_research_report"]
