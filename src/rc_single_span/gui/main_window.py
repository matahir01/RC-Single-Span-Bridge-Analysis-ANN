from __future__ import annotations

import json
import traceback
from pathlib import Path
from threading import Event
from time import monotonic

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtGui import QAction, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rc_single_span.gui.design_adapter import GuiDesignInputs
from rc_single_span.core.progress import AnalysisCancelled, AnalysisControl
from rc_single_span.gui.dialogs import InputDialog
from rc_single_span.gui.engine_adapter import (
    GuiAccuracyMode,
    GuiAnalysisSettings,
    GuiAnalysisSummary,
    GuiCodeProfile,
    run_gui_analysis,
)
from rc_single_span.gui.project_state import GuiProjectState
from rc_single_span.gui.reporting import render_calculation_report
from rc_single_span.gui.widgets import double_spin, form_page, int_spin
from rc_single_span.verification.reference_runner import ReferenceRunResult


class _WorkerSignals(QObject):
    finished = Signal(object, object)
    error = Signal(str)
    progress = Signal(str, int, int, float)
    cancelled = Signal()


class _AnalysisWorker(QRunnable):
    def __init__(
        self,
        state: GuiProjectState,
        settings: GuiAnalysisSettings,
        design_inputs: GuiDesignInputs,
        cancel_event: Event,
    ) -> None:
        super().__init__()
        self.state = state
        self.settings = settings
        self.design_inputs = design_inputs
        self.cancel_event = cancel_event
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        started = monotonic()
        last_update: tuple[str, int] | None = None

        def progress(phase: str, completed: int, total: int) -> None:
            nonlocal last_update
            percent = min(100, round(100 * completed / max(1, total)))
            update = phase, percent
            if update != last_update:
                self.signals.progress.emit(phase, completed, total, monotonic() - started)
                last_update = update

        try:
            project = self.state.build_project()
            result, summary = run_gui_analysis(
                project,
                self.settings,
                self.design_inputs,
                control=AnalysisControl(progress, self.cancel_event.is_set),
            )
            if self.cancel_event.is_set():
                raise AnalysisCancelled("Analysis cancelled by user.")
        except AnalysisCancelled:
            self.signals.cancelled.emit()
            return
        except Exception:  # noqa: BLE001 - GUI worker must return engine errors to the UI.
            self.signals.error.emit(traceback.format_exc())
            return
        self.signals.finished.emit(result, summary)


def _status_text(value: bool | None) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "CHECK"
    return "N/A"


def _number_or_dash(value: float | None, decimals: int = 3) -> str:
    return "—" if value is None else f"{value:.{decimals}f}"


class BridgeMainWindow(QMainWindow):
    """Desktop presentation layer over the verified deterministic engine."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RC Single-Span Bridge Analysis")
        self.resize(1360, 880)
        self._thread_pool = QThreadPool.globalInstance()
        self._current_path: Path | None = None
        self._last_result = None
        self._last_summary: GuiAnalysisSummary | None = None
        self._report_html: str | None = None
        self._run_fingerprint: str | None = None
        self._run_state: GuiProjectState | None = None
        self._run_settings: GuiAnalysisSettings | None = None
        self._run_design: GuiDesignInputs | None = None
        self._loading_inputs = False
        self._cancel_event: Event | None = None
        self._state = GuiProjectState()

        self._workspace = QSplitter(Qt.Orientation.Horizontal)
        self.project_tree = QTreeWidget()
        self.project_tree.setHeaderLabel("BRIDGE PROJECT")
        self.project_tree.setMinimumWidth(185)
        self.project_tree.setMaximumWidth(300)
        self._tabs = QTabWidget()
        self._workspace.addWidget(self.project_tree)
        self._workspace.addWidget(self._tabs)
        self._workspace.setSizes([220, 1100])
        self.setCentralWidget(self._workspace)
        self.setStatusBar(QStatusBar())
        self.setStyleSheet(
            "QMainWindow { background: #f2f5f8; }"
            "QToolBar { background: #e4edf4; border-bottom: 1px solid #aabfce;"
            " spacing: 5px; padding: 7px; }"
            "QToolBar QToolButton { padding: 7px 6px; color: #173d59; font-weight: 600; }"
            "QToolBar QToolButton:hover { background: #c8deec; }"
            "QTreeWidget { background: #f7fafc; border-right: 1px solid #bdcbd5; }"
            "QTreeWidget::item { padding: 6px; }"
            "QTreeWidget::item:selected { background: #d6e9f5; color: #173d59; }"
            "QTabWidget::pane { border: 1px solid #c8d5dd; background: white; }"
            "QGroupBox { font-weight: 600; margin-top: 12px; }"
            "QPushButton { padding: 7px 11px; }"
        )

        self._build_toolbar()
        self._build_project_tab()
        self._build_geometry_tab()
        self._build_materials_tab()
        self._build_loads_tab()
        self._build_analysis_tab()
        self._build_design_tab()
        self._build_results_tab()
        self._build_report_tab()
        self._build_verification_tab()
        self._build_research_tab()
        self._apply_state(self._state)
        self._sync_code_panels()
        self._refresh_navigation()
        self.project_tree.itemClicked.connect(self._navigate_from_tree)
        self._tabs.currentChanged.connect(self._select_tree_item)
        self._wire_input_changes()
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Bridge ribbon")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for label, handler in (
            ("New", self._new_project),
            ("Open", self._open_project),
            ("Save", self._save_project),
        ):
            action = QAction(label, self)
            action.triggered.connect(handler)
            toolbar.addAction(action)
        toolbar.addSeparator()
        for label, group in (
            ("Project", "project"), ("Layout", "layout"),
            ("Girder section", "section"), ("Deck", "deck"),
            ("Materials", "materials"), ("Loads", "loads"),
            ("Traffic", "traffic"), ("Design criteria", "design"),
        ):
            action = QAction(label, self)
            action.triggered.connect(lambda _checked=False, key=group: self._edit_group(key))
            toolbar.addAction(action)
        toolbar.addSeparator()
        self._run_action = QAction("Run analysis", self)
        self._run_action.triggered.connect(self._run_analysis)
        toolbar.addAction(self._run_action)
        result_action = QAction("Results", self)
        result_action.triggered.connect(lambda: self._tabs.setCurrentWidget(self.results_page))
        toolbar.addAction(result_action)
        self._export_action = QAction("Export PDF", self)
        self._export_action.setEnabled(False)
        self._export_action.triggered.connect(self._export_pdf)
        toolbar.addAction(self._export_action)

    def _refresh_navigation(self) -> None:
        self.project_tree.blockSignals(True)
        self.project_tree.clear()
        self._tree_items: dict[int, QTreeWidgetItem] = {}
        groups = (
            ("Model", ("Bridge view", "Project", "Geometry", "Materials")),
            ("Actions", ("Loads", "Analysis", "Design checks")),
            ("Review", ("Results", "Report", "Verification", "ANN / Reliability")),
        )
        for group_name, labels in groups:
            parent = QTreeWidgetItem(self.project_tree, [group_name])
            for label in labels:
                index = next(
                    (i for i in range(self._tabs.count()) if self._tabs.tabText(i) == label),
                    -1,
                )
                if index >= 0:
                    item = QTreeWidgetItem(parent, [label])
                    item.setData(0, Qt.ItemDataRole.UserRole, index)
                    self._tree_items[index] = item
        self.project_tree.expandAll()
        self.project_tree.blockSignals(False)
        self._select_tree_item(self._tabs.currentIndex())

    def _navigate_from_tree(self, item: QTreeWidgetItem, _column: int) -> None:
        index = item.data(0, Qt.ItemDataRole.UserRole)
        if isinstance(index, int):
            self._tabs.setCurrentIndex(index)

    def _select_tree_item(self, index: int) -> None:
        item = self._tree_items.get(index)
        if item is not None:
            self.project_tree.setCurrentItem(item)

    def _edit_group(self, group: str) -> None:
        names = {
            "project": "project_name",
            "layout": "span_m physical_length_m deck_width_m carriageway_width_m "
            "carriageway_offset_m girder_count girder_spacing_m",
            "section": "section_type rect_width rect_depth t_flange_width "
            "t_flange_thickness t_web_width t_total_depth i_top_flange_width "
            "i_top_flange_thickness i_top_haunch i_web_width i_web_depth "
            "i_bottom_haunch i_bottom_flange_width i_bottom_flange_thickness",
            "deck": "false_slab_depth false_slab_composite in_situ_depth in_situ_composite",
            "materials": "fck_mpa fcu_mpa fyk_mpa density elastic_modulus "
            "rebar_layers bars_per_layer bar_diameter",
            "loads": "surfacing_thickness surfacing_density barrier_load services_load",
            "traffic": "code_profile analysis_mode psi1_tandem psi1_udl psi2_traffic lm1_step "
            "hb_units retain_cases",
            "design": "design_enabled effective_depth design_bar_diameter design_bar_spacing "
            "ec_cover ec_fct_eff ec_crack_limit ec_na_ratio ec_sls_basis ec_alpha_cc "
            "bs_cover bs_crack_point_depth bs_crack_limit bs_ec_modified bs_fyv "
            "deflection_enabled deflection_limit deflection_basis",
        }[group].split()
        fields = [(name.replace("_", " ").title(), getattr(self, name)) for name in names]
        dialog = InputDialog(
            group.title(), fields,
            validate=lambda: (self._read_state().build_project(), self._read_design_inputs()),
            changed=self._inputs_changed,
            parent=self,
        )
        dialog.exec()

    def _build_project_tab(self) -> None:
        page, form = form_page("Project")
        self.project_name = QLineEdit()
        form.addRow("Project name", self.project_name)
        note = QLabel(
            "Inputs and criteria in this application belong to the selected project. "
            "Software results are not approval of a real bridge."
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._tabs.addTab(page, "Project")

    def _build_geometry_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        bridge_box = QGroupBox("Bridge geometry")
        bridge_form = QFormLayout(bridge_box)
        self.span_m = double_spin(15.0, suffix=" m")
        self.physical_length_m = double_spin(14.95, suffix=" m")
        self.deck_width_m = double_spin(11.0, suffix=" m")
        self.carriageway_width_m = double_spin(7.0, suffix=" m")
        self.carriageway_offset_m = double_spin(
            0.0,
            minimum=-100.0,
            maximum=100.0,
            suffix=" m",
        )
        self.girder_count = int_spin(7, minimum=2, maximum=100)
        self.girder_spacing_m = double_spin(1.70, suffix=" m")
        bridge_form.addRow("Analysis span", self.span_m)
        bridge_form.addRow("Physical girder length", self.physical_length_m)
        bridge_form.addRow("Deck width", self.deck_width_m)
        bridge_form.addRow("Carriageway width", self.carriageway_width_m)
        bridge_form.addRow("Carriageway offset", self.carriageway_offset_m)
        bridge_form.addRow("Girder count", self.girder_count)
        bridge_form.addRow("Girder spacing", self.girder_spacing_m)
        layout.addWidget(bridge_box)

        section_box = QGroupBox("Precast girder section")
        section_layout = QVBoxLayout(section_box)
        self.section_type = QComboBox()
        self.section_type.addItems(["Rectangular", "T", "I"])
        self.section_type.currentIndexChanged.connect(self._section_changed)
        section_layout.addWidget(self.section_type)
        self.section_stack = QStackedWidget()

        rectangular, form = form_page("Rectangular section")
        self.rect_width = double_spin(0.40, suffix=" m")
        self.rect_depth = double_spin(0.95, suffix=" m")
        form.addRow("Width", self.rect_width)
        form.addRow("Depth", self.rect_depth)
        self.section_stack.addWidget(rectangular)

        t_section, form = form_page("T-section")
        self.t_flange_width = double_spin(1.70, suffix=" m")
        self.t_flange_thickness = double_spin(0.175, suffix=" m")
        self.t_web_width = double_spin(0.40, suffix=" m")
        self.t_total_depth = double_spin(1.125, suffix=" m")
        form.addRow("Flange width", self.t_flange_width)
        form.addRow("Flange thickness", self.t_flange_thickness)
        form.addRow("Web width", self.t_web_width)
        form.addRow("Total depth", self.t_total_depth)
        self.section_stack.addWidget(t_section)

        i_section, form = form_page("I-section")
        self.i_top_flange_width = double_spin(0.40, suffix=" m")
        self.i_top_flange_thickness = double_spin(0.15, suffix=" m")
        self.i_top_haunch = double_spin(0.0, suffix=" m")
        self.i_web_width = double_spin(0.20, suffix=" m")
        self.i_web_depth = double_spin(0.65, suffix=" m")
        self.i_bottom_haunch = double_spin(0.0, suffix=" m")
        self.i_bottom_flange_width = double_spin(0.40, suffix=" m")
        self.i_bottom_flange_thickness = double_spin(0.15, suffix=" m")
        form.addRow("Top flange width", self.i_top_flange_width)
        form.addRow("Top flange thickness", self.i_top_flange_thickness)
        form.addRow("Top haunch depth", self.i_top_haunch)
        form.addRow("Web width", self.i_web_width)
        form.addRow("Clear web depth", self.i_web_depth)
        form.addRow("Bottom haunch depth", self.i_bottom_haunch)
        form.addRow("Bottom flange width", self.i_bottom_flange_width)
        form.addRow("Bottom flange thickness", self.i_bottom_flange_thickness)
        self.section_stack.addWidget(i_section)
        section_layout.addWidget(self.section_stack)
        layout.addWidget(section_box)

        deck_box = QGroupBox("Deck construction")
        deck_form = QFormLayout(deck_box)
        self.false_slab_depth = double_spin(0.075, suffix=" m")
        self.in_situ_depth = double_spin(0.175, suffix=" m")
        self.false_slab_composite = QCheckBox("Participates in final composite section")
        self.in_situ_composite = QCheckBox("Participates in final composite section")
        self.in_situ_composite.setChecked(True)
        deck_form.addRow("Precast false slab", self.false_slab_depth)
        deck_form.addRow("", self.false_slab_composite)
        deck_form.addRow("Cast in-situ slab", self.in_situ_depth)
        deck_form.addRow("", self.in_situ_composite)
        layout.addWidget(deck_box)
        layout.addStretch(1)
        self._tabs.addTab(page, "Geometry")

    def _build_materials_tab(self) -> None:
        page, form = form_page("Materials and longitudinal reinforcement")
        self.fck_mpa = double_spin(35.0, suffix=" MPa")
        self.fcu_mpa = double_spin(45.0, suffix=" MPa")
        self.fyk_mpa = double_spin(500.0, suffix=" MPa")
        self.density = double_spin(25.0, suffix=" kN/m³")
        self.elastic_modulus = double_spin(
            34000.0,
            suffix=" MPa",
            decimals=0,
            step=100.0,
        )
        self.rebar_layers = int_spin(4, minimum=1, maximum=20)
        self.bars_per_layer = int_spin(4, minimum=1, maximum=30)
        self.bar_diameter = double_spin(32.0, suffix=" mm", decimals=1, step=1.0)
        form.addRow("Concrete fck", self.fck_mpa)
        form.addRow("Concrete fcu", self.fcu_mpa)
        form.addRow("Reinforcement fyk", self.fyk_mpa)
        form.addRow("Concrete density", self.density)
        form.addRow("Elastic modulus", self.elastic_modulus)
        form.addRow("Reinforcement layers", self.rebar_layers)
        form.addRow("Bars per layer", self.bars_per_layer)
        form.addRow("Bar diameter", self.bar_diameter)
        self._tabs.addTab(page, "Materials")

    def _build_loads_tab(self) -> None:
        page, form = form_page("Permanent actions")
        self.surfacing_thickness = double_spin(0.080, suffix=" m")
        self.surfacing_density = double_spin(22.0, suffix=" kN/m³")
        self.barrier_load = double_spin(10.0, suffix=" kN/m")
        self.services_load = double_spin(2.0, suffix=" kN/m")
        form.addRow("Surfacing thickness", self.surfacing_thickness)
        form.addRow("Surfacing density", self.surfacing_density)
        form.addRow("Barrier line load (each side)", self.barrier_load)
        form.addRow("Services line load (each side)", self.services_load)
        note = QLabel(
            "These remain explicit project inputs; the application does not relabel them as "
            "surveyed or as-built values."
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._tabs.addTab(page, "Loads")

    def _build_analysis_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Traffic and analysis settings")
        form = QFormLayout(box)
        self.code_profile = QComboBox()
        self.code_profile.addItems([GuiCodeProfile.BS_EN.value, GuiCodeProfile.BS_5400.value])
        self.code_profile.currentIndexChanged.connect(self._sync_code_panels)
        self.analysis_mode = QComboBox()
        self.analysis_mode.addItems([mode.value for mode in GuiAccuracyMode])
        self.analysis_mode.setCurrentText(GuiAccuracyMode.FINAL.value)
        self.analysis_mode.currentIndexChanged.connect(self._mode_changed)
        self.psi1_tandem = double_spin(0.75, maximum=1.0, decimals=2, step=0.05)
        self.psi1_udl = double_spin(0.40, maximum=1.0, decimals=2, step=0.05)
        self.psi2_traffic = double_spin(0.0, maximum=1.0, decimals=2, step=0.05)
        self.lm1_step = double_spin(0.6, minimum=0.05, maximum=5.0, suffix=" m")
        self.lm1_step.valueChanged.connect(self._customize_grid)
        self.hb_units = double_spin(45.0, minimum=1.0, maximum=100.0, decimals=1)
        self.retain_cases = QCheckBox("Retain all traffic cases for detailed review")
        form.addRow("Code profile", self.code_profile)
        form.addRow("Accuracy mode", self.analysis_mode)
        form.addRow("BS EN frequent TS factor ψ1", self.psi1_tandem)
        form.addRow("BS EN frequent UDL factor ψ1", self.psi1_udl)
        form.addRow("BS EN quasi-permanent ψ2", self.psi2_traffic)
        form.addRow("LM1 longitudinal step", self.lm1_step)
        mode_note = QLabel(
            "BS EN LM1 accuracy modes only. The BS 5400 / BD 37 route uses fixed "
            "traffic search steps and requires a separate project-specific convergence audit. "
            "Quick: 3 m exploratory grid. Standard: 2.4 → 1.2 m, refining to "
            "0.6 m if the 5% girder-envelope test fails. Final Verification: "
            "audits 1.2 → 0.6 m. Editing the grid selects Custom, without "
            "a convergence claim."
        )
        mode_note.setWordWrap(True)
        form.addRow(mode_note)
        form.addRow("HB units", self.hb_units)
        form.addRow("", self.retain_cases)
        layout.addWidget(box)
        self.run_button = QPushButton("Run deterministic analysis")
        self.run_button.clicked.connect(self._run_analysis)
        layout.addWidget(self.run_button)
        self.cancel_button = QPushButton("Cancel analysis")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_analysis)
        layout.addWidget(self.cancel_button)
        self.analysis_progress = QProgressBar()
        self.analysis_progress.setRange(0, 100)
        self.analysis_progress.setValue(0)
        layout.addWidget(self.analysis_progress)
        self.analysis_phase = QLabel("Ready")
        layout.addWidget(self.analysis_phase)
        self.analysis_note = QLabel(
            "The same verified deterministic engine is used by the GUI. Code-specific design "
            "checks are optional and require the explicit Design tab inputs."
        )
        self.analysis_note.setWordWrap(True)
        layout.addWidget(self.analysis_note)
        layout.addStretch(1)
        self._tabs.addTab(page, "Analysis")

    def _build_design_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        self.design_enabled = QCheckBox("Run code-specific resistance and SLS checks")
        layout.addWidget(self.design_enabled)

        common_box = QGroupBox("Common design inputs")
        common = QFormLayout(common_box)
        self.effective_depth = double_spin(1.10, suffix=" m")
        self.design_bar_diameter = double_spin(32.0, suffix=" mm", decimals=1)
        self.design_bar_spacing = double_spin(90.0, suffix=" mm", decimals=1)
        common.addRow("Effective depth d", self.effective_depth)
        common.addRow("Bar diameter", self.design_bar_diameter)
        common.addRow("Bar spacing", self.design_bar_spacing)
        layout.addWidget(common_box)

        self.design_code_stack = QStackedWidget()
        ec_page, ec = form_page("BS EN / EC2 project inputs")
        self.ec_cover = double_spin(50.0, suffix=" mm", decimals=1)
        self.ec_fct_eff = double_spin(3.2, suffix=" MPa", decimals=2)
        self.ec_crack_limit = double_spin(0.30, suffix=" mm", decimals=3)
        self.ec_na_ratio = double_spin(0.45, minimum=0.01, maximum=1.0, decimals=3)
        self.ec_sls_basis = QComboBox()
        self.ec_sls_basis.addItems(["characteristic", "frequent", "quasi_permanent"])
        self.ec_alpha_cc = double_spin(1.0, minimum=0.01, maximum=1.0, decimals=3)
        ec.addRow("Nominal cover", self.ec_cover)
        ec.addRow("Effective concrete tensile strength", self.ec_fct_eff)
        ec.addRow("Crack-width limit", self.ec_crack_limit)
        ec.addRow("Maximum neutral-axis ratio", self.ec_na_ratio)
        ec.addRow("SLS basis", self.ec_sls_basis)
        ec.addRow("αcc", self.ec_alpha_cc)
        self.design_code_stack.addWidget(ec_page)

        bs_page, bs = form_page("BS 5400 project inputs")
        self.bs_cover = double_spin(50.0, suffix=" mm", decimals=1)
        self.bs_crack_point_depth = double_spin(1200.0, suffix=" mm", decimals=1)
        self.bs_crack_limit = double_spin(0.25, suffix=" mm", decimals=3)
        self.bs_ec_modified = double_spin(34000.0, suffix=" MPa", decimals=0)
        self.bs_fyv = double_spin(460.0, suffix=" MPa", decimals=1)
        bs.addRow("Nominal cover", self.bs_cover)
        bs.addRow("Crack-point depth", self.bs_crack_point_depth)
        bs.addRow("Allowable crack width", self.bs_crack_limit)
        bs.addRow("Modified concrete modulus", self.bs_ec_modified)
        bs.addRow("Shear reinforcement fyv", self.bs_fyv)
        self.design_code_stack.addWidget(bs_page)
        layout.addWidget(self.design_code_stack)

        deflection_box = QGroupBox("Project deflection acceptance criterion")
        deflection = QFormLayout(deflection_box)
        self.deflection_enabled = QCheckBox("Apply an explicit project limit")
        self.deflection_limit = double_spin(50.0, suffix=" mm")
        self.deflection_basis = QLineEdit()
        self.deflection_basis.setPlaceholderText(
            "Required when enabled, e.g. project specification clause / authority criterion"
        )
        deflection.addRow("", self.deflection_enabled)
        deflection.addRow("Limit", self.deflection_limit)
        deflection.addRow("Basis / provenance", self.deflection_basis)
        layout.addWidget(deflection_box)

        warning = QLabel(
            "The displayed starter values are editable working inputs, not universal code or "
            "Nigerian National Annex defaults. Confirm the adopted project basis before using "
            "design-check conclusions."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        layout.addStretch(1)
        self._tabs.addTab(page, "Design checks")

    def _build_results_tab(self) -> None:
        page = QWidget()
        self.results_page = page
        layout = QVBoxLayout(page)
        self.result_basis = QLabel("No analysis run yet.")
        self.result_basis.setWordWrap(True)
        layout.addWidget(self.result_basis)

        governing_box = QGroupBox("Governing ULS effects")
        governing = QFormLayout(governing_box)
        self.governing_moment = QLabel("—")
        self.governing_shear = QLabel("—")
        self.governing_torsion = QLabel("—")
        governing.addRow("Moment", self.governing_moment)
        governing.addRow("Shear", self.governing_shear)
        governing.addRow("Torsion", self.governing_torsion)
        layout.addWidget(governing_box)

        self.results_table = QTableWidget(0, 5)
        self.results_table.setHorizontalHeaderLabels(
            ["Girder", "Moment (kNm)", "Shear (kN)", "Torsion (kNm)", "Source"]
        )
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results_table)

        design_box = QGroupBox("Resistance and serviceability checks")
        design_layout = QVBoxLayout(design_box)
        self.design_results_table = QTableWidget(0, 13)
        self.design_results_table.setHorizontalHeaderLabels(
            [
                "Girder",
                "Flex util.",
                "Flexure",
                "VEd kN",
                "Vmax kN",
                "Web limit",
                "Asw/s mm²/m",
                "wk mm",
                "wlim mm",
                "Crack",
                "δ mm",
                "δlim mm",
                "Deflection",
            ]
        )
        self.design_results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.design_results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        design_layout.addWidget(self.design_results_table)
        layout.addWidget(design_box)

        self.result_notes = QTextEdit()
        self.result_notes.setReadOnly(True)
        self.result_notes.setMaximumHeight(120)
        layout.addWidget(self.result_notes)
        self._tabs.addTab(page, "Results")

    def _build_report_tab(self) -> None:
        page = QWidget()
        self.report_page = page
        layout = QVBoxLayout(page)
        self.report_preview = QTextBrowser()
        self.report_preview.setHtml(
            "<h2>Calculation report</h2><p>Run the analysis to generate a report "
            "from the current project inputs.</p>"
        )
        layout.addWidget(self.report_preview)
        button = QPushButton("Export current calculation report to PDF")
        button.clicked.connect(self._export_pdf)
        layout.addWidget(button)
        self._tabs.addTab(page, "Report")

    def _wire_input_changes(self) -> None:
        for widget in self.findChildren(QDoubleSpinBox):
            widget.valueChanged.connect(self._inputs_changed)
        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self._inputs_changed)
        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self._inputs_changed)
        for widget in self.findChildren(QComboBox):
            widget.currentIndexChanged.connect(self._inputs_changed)
        for widget in self.findChildren(QLineEdit):
            if not isinstance(widget.parent(), (QDoubleSpinBox, QSpinBox)):
                widget.textChanged.connect(self._inputs_changed)

    def _invalidate_results(self, message: str) -> None:
        self._last_result = None
        self._last_summary = None
        self._report_html = None
        self._export_action.setEnabled(False)
        self.results_table.setRowCount(0)
        self.design_results_table.setRowCount(0)
        self.result_basis.setText(message)
        self.governing_moment.setText("—")
        self.governing_shear.setText("—")
        self.governing_torsion.setText("—")
        self.result_notes.clear()
        self.report_preview.setHtml(f"<h2>Calculation report</h2><p>{message}</p>")

    def _inputs_changed(self, *_args: object) -> None:
        if self._loading_inputs:
            return
        self._section_changed(self.section_type.currentIndex())
        self._sync_code_panels()
        self._invalidate_results("Inputs changed. Run the analysis again for current results.")
        if hasattr(self, "bridge_schematic"):
            self.bridge_schematic.set_state(self._read_state())
        self.statusBar().showMessage("Project inputs changed")

    def _fingerprint(self) -> str:
        return repr((self._read_state(), self._read_settings(), self._read_design_inputs()))

    def _build_verification_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "Deterministic verification status\n\n"
            "• BS EN deterministic V1: GO within the documented software scope.\n"
            "• BS 5400 / BD 37 deterministic source tests pass within the documented "
            "software scope. The default reference HA+HB grid fails the provisional "
            "5% refinement criterion for torsion (7.412%); no traffic grid "
            "convergence claim is made.\n"
            "• External STAAD evidence verifies the documented structural-response campaign; "
            "it is not approval of an individual bridge.\n\n"
            "Next GUI increments include STAAD comparison views, calculation-report browsing, "
            "traffic/construction-stage visualisation and full BS combination-4/5 effect input."
        )
        layout.addWidget(text)
        self._tabs.addTab(page, "Verification")

    def _build_research_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "ANN / Reliability / RBDO workspace\n\n"
            "The research package already contains LHS sampling, ANN training, FORM, Monte "
            "Carlo validation, dependence support and RBDO infrastructure. Controls will be "
            "exposed here after the final probabilistic study basis is frozen.\n\n"
            "Research outputs remain validation-pending until the probabilistic model, sample-size "
            "convergence, surrogate performance near g=0, reliability cross-checks and final "
            "optimum verification are documented."
        )
        layout.addWidget(text)
        self._tabs.addTab(page, "ANN / Reliability")

    def _section_changed(self, index: int) -> None:
        self.section_stack.setCurrentIndex(index)

    def _mode_changed(self, _index: int) -> None:
        steps = {
            GuiAccuracyMode.QUICK.value: 3.0,
            GuiAccuracyMode.STANDARD.value: 1.2,
            GuiAccuracyMode.FINAL.value: 0.6,
        }
        selected = steps.get(self.analysis_mode.currentText())
        if selected is not None:
            self.lm1_step.blockSignals(True)
            try:
                self.lm1_step.setValue(selected)
            finally:
                self.lm1_step.blockSignals(False)

    def _customize_grid(self, _value: float) -> None:
        if not self._loading_inputs:
            self.analysis_mode.setCurrentText(GuiAccuracyMode.CUSTOM.value)

    def _sync_code_panels(self) -> None:
        is_bs_en = self.code_profile.currentIndex() == 0
        self.design_code_stack.setCurrentIndex(0 if is_bs_en else 1)
        self.psi1_tandem.setEnabled(is_bs_en)
        self.psi1_udl.setEnabled(is_bs_en)
        self.psi2_traffic.setEnabled(is_bs_en)
        self.analysis_mode.setEnabled(is_bs_en)
        self.lm1_step.setEnabled(is_bs_en)
        self.hb_units.setEnabled(not is_bs_en)

    def _read_state(self) -> GuiProjectState:
        section_value = ("rectangular", "t", "i")[self.section_type.currentIndex()]
        return GuiProjectState(
            name=self.project_name.text().strip() or "Untitled bridge project",
            span_m=self.span_m.value(),
            physical_girder_length_m=self.physical_length_m.value(),
            deck_width_m=self.deck_width_m.value(),
            carriageway_width_m=self.carriageway_width_m.value(),
            carriageway_offset_m=self.carriageway_offset_m.value(),
            girder_count=self.girder_count.value(),
            girder_spacing_m=self.girder_spacing_m.value(),
            section_type=section_value,
            rectangular_width_m=self.rect_width.value(),
            rectangular_depth_m=self.rect_depth.value(),
            t_flange_width_m=self.t_flange_width.value(),
            t_flange_thickness_m=self.t_flange_thickness.value(),
            t_web_width_m=self.t_web_width.value(),
            t_total_depth_m=self.t_total_depth.value(),
            i_top_flange_width_m=self.i_top_flange_width.value(),
            i_top_flange_thickness_m=self.i_top_flange_thickness.value(),
            i_top_haunch_depth_m=self.i_top_haunch.value(),
            i_web_width_m=self.i_web_width.value(),
            i_web_depth_m=self.i_web_depth.value(),
            i_bottom_haunch_depth_m=self.i_bottom_haunch.value(),
            i_bottom_flange_width_m=self.i_bottom_flange_width.value(),
            i_bottom_flange_thickness_m=self.i_bottom_flange_thickness.value(),
            false_slab_depth_m=self.false_slab_depth.value(),
            in_situ_slab_depth_m=self.in_situ_depth.value(),
            false_slab_composite=self.false_slab_composite.isChecked(),
            in_situ_slab_composite=self.in_situ_composite.isChecked(),
            fck_mpa=self.fck_mpa.value(),
            fcu_mpa=self.fcu_mpa.value(),
            fyk_mpa=self.fyk_mpa.value(),
            concrete_density_kn_m3=self.density.value(),
            elastic_modulus_mpa=self.elastic_modulus.value(),
            reinforcement_layers=self.rebar_layers.value(),
            bars_per_layer=self.bars_per_layer.value(),
            bar_diameter_mm=self.bar_diameter.value(),
            surfacing_thickness_m=self.surfacing_thickness.value(),
            surfacing_density_kn_m3=self.surfacing_density.value(),
            barrier_kn_m=self.barrier_load.value(),
            services_kn_m=self.services_load.value(),
        )

    def _read_settings(self) -> GuiAnalysisSettings:
        return GuiAnalysisSettings(
            code_profile=GuiCodeProfile(self.code_profile.currentText()),
            elastic_modulus_mpa=self.elastic_modulus.value(),
            psi1_tandem=self.psi1_tandem.value(),
            psi1_udl=self.psi1_udl.value(),
            psi2_traffic=self.psi2_traffic.value(),
            lm1_step_m=self.lm1_step.value(),
            accuracy_mode=GuiAccuracyMode(self.analysis_mode.currentText()),
            retain_all_cases=self.retain_cases.isChecked(),
            hb_units=self.hb_units.value(),
        )

    def _read_design_inputs(self) -> GuiDesignInputs:
        deflection_limit = self.deflection_limit.value() if self.deflection_enabled.isChecked() else None
        deflection_basis = self.deflection_basis.text().strip() or None
        if not self.deflection_enabled.isChecked():
            deflection_basis = None
        return GuiDesignInputs(
            enabled=self.design_enabled.isChecked(),
            effective_depth_m=self.effective_depth.value(),
            bar_diameter_mm=self.design_bar_diameter.value(),
            bar_spacing_mm=self.design_bar_spacing.value(),
            ec2_cover_mm=self.ec_cover.value(),
            ec2_fct_eff_mpa=self.ec_fct_eff.value(),
            ec2_crack_limit_mm=self.ec_crack_limit.value(),
            ec2_maximum_neutral_axis_ratio=self.ec_na_ratio.value(),
            ec2_sls_basis=self.ec_sls_basis.currentText(),
            ec2_alpha_cc=self.ec_alpha_cc.value(),
            bs_nominal_cover_mm=self.bs_cover.value(),
            bs_crack_point_depth_mm=self.bs_crack_point_depth.value(),
            bs_allowable_crack_width_mm=self.bs_crack_limit.value(),
            bs_ec_modified_mpa=self.bs_ec_modified.value(),
            bs_shear_reinforcement_fyv_mpa=self.bs_fyv.value(),
            deflection_limit_mm=deflection_limit,
            deflection_limit_basis=deflection_basis,
        )

    def _apply_state(self, state: GuiProjectState) -> None:
        self._state = state
        self.project_name.setText(state.name)
        self.span_m.setValue(state.span_m)
        self.physical_length_m.setValue(state.physical_girder_length_m)
        self.deck_width_m.setValue(state.deck_width_m)
        self.carriageway_width_m.setValue(state.carriageway_width_m)
        self.carriageway_offset_m.setValue(state.carriageway_offset_m)
        self.girder_count.setValue(state.girder_count)
        self.girder_spacing_m.setValue(state.girder_spacing_m)
        self.section_type.setCurrentIndex({"rectangular": 0, "t": 1, "i": 2}[state.section_type])
        self.rect_width.setValue(state.rectangular_width_m)
        self.rect_depth.setValue(state.rectangular_depth_m)
        self.t_flange_width.setValue(state.t_flange_width_m)
        self.t_flange_thickness.setValue(state.t_flange_thickness_m)
        self.t_web_width.setValue(state.t_web_width_m)
        self.t_total_depth.setValue(state.t_total_depth_m)
        self.i_top_flange_width.setValue(state.i_top_flange_width_m)
        self.i_top_flange_thickness.setValue(state.i_top_flange_thickness_m)
        self.i_top_haunch.setValue(state.i_top_haunch_depth_m)
        self.i_web_width.setValue(state.i_web_width_m)
        self.i_web_depth.setValue(state.i_web_depth_m)
        self.i_bottom_haunch.setValue(state.i_bottom_haunch_depth_m)
        self.i_bottom_flange_width.setValue(state.i_bottom_flange_width_m)
        self.i_bottom_flange_thickness.setValue(state.i_bottom_flange_thickness_m)
        self.false_slab_depth.setValue(state.false_slab_depth_m)
        self.in_situ_depth.setValue(state.in_situ_slab_depth_m)
        self.false_slab_composite.setChecked(state.false_slab_composite)
        self.in_situ_composite.setChecked(state.in_situ_slab_composite)
        self.fck_mpa.setValue(state.fck_mpa)
        self.fcu_mpa.setValue(state.fcu_mpa)
        self.fyk_mpa.setValue(state.fyk_mpa)
        self.density.setValue(state.concrete_density_kn_m3)
        self.elastic_modulus.setValue(state.elastic_modulus_mpa)
        self.rebar_layers.setValue(state.reinforcement_layers)
        self.bars_per_layer.setValue(state.bars_per_layer)
        self.bar_diameter.setValue(state.bar_diameter_mm)
        self.surfacing_thickness.setValue(state.surfacing_thickness_m)
        self.surfacing_density.setValue(state.surfacing_density_kn_m3)
        self.barrier_load.setValue(state.barrier_kn_m)
        self.services_load.setValue(state.services_kn_m)

    def _apply_analysis_payload(self, analysis: dict[str, object]) -> None:
        code = analysis.get("code_profile")
        if isinstance(code, str) and code in {item.value for item in GuiCodeProfile}:
            self.code_profile.setCurrentText(code)
        mode = analysis.get("accuracy_mode", GuiAccuracyMode.CUSTOM.value)
        if isinstance(mode, str) and mode in {item.value for item in GuiAccuracyMode}:
            self.analysis_mode.setCurrentText(mode)
        numeric = (
            ("psi1_tandem", self.psi1_tandem),
            ("psi1_udl", self.psi1_udl),
            ("psi2_traffic", self.psi2_traffic),
            ("lm1_step_m", self.lm1_step),
            ("hb_units", self.hb_units),
        )
        for key, widget in numeric:
            value = analysis.get(key)
            if isinstance(value, int | float):
                widget.setValue(float(value))
        retained = analysis.get("retain_all_cases")
        if isinstance(retained, bool):
            self.retain_cases.setChecked(retained)
        self._sync_code_panels()

    def _apply_design_payload(self, payload: dict[str, object]) -> None:
        enabled = payload.get("enabled")
        if isinstance(enabled, bool):
            self.design_enabled.setChecked(enabled)
        mapping = (
            ("effective_depth_m", self.effective_depth),
            ("bar_diameter_mm", self.design_bar_diameter),
            ("bar_spacing_mm", self.design_bar_spacing),
            ("ec2_cover_mm", self.ec_cover),
            ("ec2_fct_eff_mpa", self.ec_fct_eff),
            ("ec2_crack_limit_mm", self.ec_crack_limit),
            ("ec2_maximum_neutral_axis_ratio", self.ec_na_ratio),
            ("ec2_alpha_cc", self.ec_alpha_cc),
            ("bs_nominal_cover_mm", self.bs_cover),
            ("bs_crack_point_depth_mm", self.bs_crack_point_depth),
            ("bs_allowable_crack_width_mm", self.bs_crack_limit),
            ("bs_ec_modified_mpa", self.bs_ec_modified),
            ("bs_shear_reinforcement_fyv_mpa", self.bs_fyv),
        )
        for key, widget in mapping:
            value = payload.get(key)
            if isinstance(value, int | float):
                widget.setValue(float(value))
        sls = payload.get("ec2_sls_basis")
        if isinstance(sls, str):
            self.ec_sls_basis.setCurrentText(sls)
        limit = payload.get("deflection_limit_mm")
        basis = payload.get("deflection_limit_basis")
        has_limit = isinstance(limit, int | float)
        self.deflection_enabled.setChecked(has_limit)
        if has_limit:
            self.deflection_limit.setValue(float(limit))
        self.deflection_basis.setText(basis if isinstance(basis, str) else "")

    def _new_project(self) -> None:
        self._current_path = None
        self._loading_inputs = True
        try:
            self._apply_state(GuiProjectState())
            self._apply_analysis_payload(self._analysis_payload(GuiAnalysisSettings()))
            self._apply_design_payload(GuiDesignInputs().__dict__)
        finally:
            self._loading_inputs = False
        self._invalidate_results("No analysis run yet.")
        if hasattr(self, "bridge_schematic"):
            self.bridge_schematic.set_state(self._read_state())
        self.statusBar().showMessage("New project")

    @staticmethod
    def _analysis_payload(settings: GuiAnalysisSettings) -> dict[str, object]:
        return {
            "code_profile": settings.code_profile.value,
            "psi1_tandem": settings.psi1_tandem,
            "psi1_udl": settings.psi1_udl,
            "psi2_traffic": settings.psi2_traffic,
            "lm1_step_m": settings.lm1_step_m,
            "accuracy_mode": settings.accuracy_mode.value,
            "hb_units": settings.hb_units,
            "retain_all_cases": settings.retain_all_cases,
        }

    def open_project(self, target: Path) -> None:
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != "rc-single-span-bridge-gui-v2":
            raise ValueError("Unsupported project file format.")
        project_payload = payload.get("project")
        if not isinstance(project_payload, dict):
            raise TypeError("Project file is missing the project object.")
        state = GuiProjectState.from_dict(project_payload)
        state.build_project()
        analysis = payload.get("analysis", {})
        design = payload.get("design", {})
        if not isinstance(analysis, dict) or not isinstance(design, dict):
            raise TypeError("Analysis and design must be JSON objects.")
        if analysis.get("code_profile", GuiCodeProfile.BS_EN.value) not in {
            item.value for item in GuiCodeProfile
        }:
            raise ValueError("Unsupported code profile in project file.")
        GuiDesignInputs(**design)
        previous = (self._read_state(), self._read_settings(), self._read_design_inputs())
        self._loading_inputs = True
        try:
            self._apply_state(state)
            self._apply_analysis_payload(self._analysis_payload(GuiAnalysisSettings()))
            self._apply_design_payload(GuiDesignInputs().__dict__)
            self._apply_analysis_payload(analysis)
            self._apply_design_payload(design)
            if self._read_state() != state:
                raise ValueError("Project geometry is outside the GUI's supported input range.")
            actual_analysis = self._analysis_payload(self._read_settings())
            actual_design = self._read_design_inputs().__dict__
            for label, saved, actual in (
                ("analysis", analysis, actual_analysis),
                ("design", design, actual_design),
            ):
                if any(key not in actual or actual[key] != value for key, value in saved.items()):
                    raise ValueError(f"Project {label} inputs exceed the GUI's supported range.")
        except (ValueError, TypeError, KeyError):
            self._apply_state(previous[0])
            self._apply_analysis_payload(self._analysis_payload(previous[1]))
            self._apply_design_payload(previous[2].__dict__)
            raise
        finally:
            self._loading_inputs = False
        self._current_path = target
        self._invalidate_results("Project opened. Run the analysis for current results.")
        if hasattr(self, "bridge_schematic"):
            self.bridge_schematic.set_state(state)
        self.statusBar().showMessage(f"Opened {target}")

    def _open_project(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open bridge project", "", "Bridge project (*.json);;JSON (*.json)"
        )
        if not file_name:
            return
        try:
            self.open_project(Path(file_name))
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            QMessageBox.critical(self, "Open failed", str(exc))

    def save_project(self, target: Path) -> None:
        state = self._read_state()
        state.build_project()
        settings = self._read_settings()
        design = self._read_design_inputs()
        payload = {
            "format": "rc-single-span-bridge-gui-v2",
            "project": state.as_dict(),
            "analysis": self._analysis_payload(settings),
            "design": design.__dict__,
        }
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(target)
        self._current_path = target
        self.statusBar().showMessage(f"Saved {target}")

    def _save_project(self) -> None:
        target = self._current_path
        if target is None:
            file_name, _ = QFileDialog.getSaveFileName(
                self, "Save bridge project", "bridge_project.json", "Bridge project (*.json)"
            )
            if not file_name:
                return
            target = Path(file_name)
        try:
            self.save_project(target)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Save failed", str(exc))

    def _run_analysis(self) -> None:
        if not self.run_button.isEnabled():
            return
        try:
            state = self._read_state()
            state.build_project()
            settings = self._read_settings()
            design = self._read_design_inputs()
        except (ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Invalid analysis input", str(exc))
            return
        self._run_state, self._run_settings, self._run_design = state, settings, design
        self._run_fingerprint = self._fingerprint()
        self._invalidate_results("Analysis in progress. Previous results were cleared.")
        self.run_button.setEnabled(False)
        self._run_action.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.analysis_progress.setValue(0)
        self.analysis_phase.setText("Preparing analysis…")
        self.statusBar().showMessage("Preparing analysis…")
        self._cancel_event = Event()
        worker = _AnalysisWorker(state, settings, design, self._cancel_event)
        worker.signals.finished.connect(self._analysis_finished)
        worker.signals.error.connect(self._analysis_failed)
        worker.signals.progress.connect(self._analysis_progress)
        worker.signals.cancelled.connect(self._analysis_cancelled)
        self._thread_pool.start(worker)

    @Slot()
    def _cancel_analysis(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.analysis_phase.setText("Cancelling…")
            self.statusBar().showMessage("Cancelling analysis…")

    @Slot(str, int, int, float)
    def _analysis_progress(self, phase: str, completed: int, total: int,
                           elapsed_seconds: float) -> None:
        if self._cancel_event is not None and self._cancel_event.is_set():
            return
        percent = min(100, round(100 * completed / max(1, total)))
        self.analysis_progress.setValue(percent)
        message = f"{phase} {percent}% · elapsed {elapsed_seconds:.1f} s"
        self.analysis_phase.setText(message)
        self.statusBar().showMessage(message)

    @Slot()
    def _analysis_cancelled(self) -> None:
        self._cancel_event = None
        self.run_button.setEnabled(True)
        self._run_action.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.analysis_progress.setValue(0)
        self.analysis_phase.setText("Analysis cancelled")
        self._invalidate_results("Analysis cancelled. No current result is available.")
        self.statusBar().showMessage("Analysis cancelled")

    @Slot(object, object)
    def _analysis_finished(self, result, summary: GuiAnalysisSummary) -> None:
        self._cancel_event = None
        self.run_button.setEnabled(True)
        self._run_action.setEnabled(True)
        self.cancel_button.setEnabled(False)
        try:
            current_fingerprint = self._fingerprint()
        except (ValueError, TypeError, KeyError):
            current_fingerprint = None
        if current_fingerprint != self._run_fingerprint:
            self._invalidate_results("Inputs changed during analysis. Run again for current results.")
            self.statusBar().showMessage("Analysis result discarded: inputs changed")
            return
        self._last_result = result
        self._last_summary = summary
        self.statusBar().showMessage("Analysis complete")
        self.analysis_progress.setValue(100)
        self.analysis_phase.setText("Analysis complete")
        self._show_summary(summary)
        self._tabs.setCurrentWidget(self.results_page)

    @Slot(str)
    def _analysis_failed(self, details: str) -> None:
        self._cancel_event = None
        self.run_button.setEnabled(True)
        self._run_action.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.analysis_progress.setValue(0)
        self.analysis_phase.setText("Analysis failed")
        self._invalidate_results("Analysis failed. No current result is available.")
        self.statusBar().showMessage("Analysis failed")
        QMessageBox.critical(self, "Analysis failed", details)

    def _show_summary(self, summary: GuiAnalysisSummary) -> None:
        self.result_basis.setText(f"Code basis: {summary.code_basis}")
        moment = summary.governing_moment
        shear = summary.governing_shear
        torsion = summary.governing_torsion
        self.governing_moment.setText(f"{moment.moment_knm:,.2f} kNm — Girder {moment.girder}")
        self.governing_shear.setText(f"{shear.shear_kn:,.2f} kN — Girder {shear.girder}")
        self.governing_torsion.setText(
            f"{torsion.torsion_knm:,.2f} kNm — Girder {torsion.girder}"
        )
        self.results_table.setRowCount(len(summary.rows))
        for row_index, row in enumerate(summary.rows):
            values = (
                str(row.girder),
                f"{row.moment_knm:.3f}",
                f"{row.shear_kn:.3f}",
                f"{row.torsion_knm:.3f}",
                row.source,
            )
            for column, value in enumerate(values):
                self.results_table.setItem(row_index, column, QTableWidgetItem(value))

        self.design_results_table.setRowCount(len(summary.design_rows))
        for row_index, row in enumerate(summary.design_rows):
            values = (
                str(row.girder),
                _number_or_dash(row.flexure_utilization),
                _status_text(row.flexure_passes),
                f"{row.shear_demand_kn:.2f}",
                f"{row.shear_max_resistance_kn:.2f}",
                _status_text(row.shear_maximum_passes),
                f"{row.required_shear_steel_mm2_per_m:.2f}",
                f"{row.crack_width_mm:.3f}",
                f"{row.crack_limit_mm:.3f}",
                _status_text(row.crack_passes),
                f"{row.deflection_mm:.3f}",
                _number_or_dash(row.deflection_limit_mm),
                _status_text(row.deflection_passes),
            )
            for column, value in enumerate(values):
                self.design_results_table.setItem(row_index, column, QTableWidgetItem(value))
        notes = list(summary.notes)
        if not summary.design_rows:
            notes.append("Code-specific design checks were not enabled for this run.")
        self.result_notes.setPlainText("\n".join(f"• {note}" for note in notes))
        if self._run_state is None or self._run_settings is None or self._run_design is None:
            raise RuntimeError("Analysis snapshot is missing; report cannot be generated.")
        self._report_html = render_calculation_report(
            self._run_state, self._run_settings, self._run_design, summary,
            result=self._last_result if isinstance(self._last_result, ReferenceRunResult) else None,
        )
        self.report_preview.setHtml(self._report_html)
        self._export_action.setEnabled(True)

    def write_report_pdf(self, target: Path) -> None:
        if self._report_html is None or self._last_summary is None:
            raise ValueError("Run the current project before exporting a calculation report.")
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setOutputFileName(str(target))
        document = QTextDocument()
        document.setHtml(self._report_html)
        document.print_(printer)
        if not target.is_file() or target.stat().st_size == 0:
            raise OSError(f"PDF export did not produce a file: {target}")

    def _export_pdf(self, *_args: object) -> None:
        if self._report_html is None:
            QMessageBox.information(self, "No current report", "Run the analysis first.")
            return
        default = (
            str(self._current_path.with_suffix(".pdf"))
            if self._current_path is not None else "bridge_calculation_report.pdf"
        )
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Export calculation report", default, "PDF (*.pdf)"
        )
        if not file_name:
            return
        try:
            self.write_report_pdf(Path(file_name))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "PDF export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {file_name}")
