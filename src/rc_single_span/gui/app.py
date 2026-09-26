from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from rc_single_span.gui.engine_adapter import (
    GuiAnalysisSettings,
    GuiAnalysisSummary,
    GuiCodeProfile,
    run_gui_analysis,
)
from rc_single_span.gui.project_state import GuiProjectState


class _WorkerSignals(QObject):
    finished = Signal(object, object)
    error = Signal(str)


class _AnalysisWorker(QRunnable):
    def __init__(self, state: GuiProjectState, settings: GuiAnalysisSettings) -> None:
        super().__init__()
        self.state = state
        self.settings = settings
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            project = self.state.build_project()
            result, summary = run_gui_analysis(project, self.settings)
        except Exception:
            self.signals.error.emit(traceback.format_exc())
            return
        self.signals.finished.emit(result, summary)


def _double_spin(
    value: float,
    *,
    minimum: float = 0.0,
    maximum: float = 1_000_000.0,
    decimals: int = 3,
    step: float = 0.01,
    suffix: str = "",
) -> QDoubleSpinBox:
    widget = QDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setDecimals(decimals)
    widget.setSingleStep(step)
    widget.setValue(value)
    if suffix:
        widget.setSuffix(suffix)
    return widget


def _int_spin(
    value: int,
    *,
    minimum: int = 1,
    maximum: int = 10_000,
) -> QSpinBox:
    widget = QSpinBox()
    widget.setRange(minimum, maximum)
    widget.setValue(value)
    return widget


def _form_page(title: str) -> tuple[QWidget, QFormLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    group = QGroupBox(title)
    form = QFormLayout(group)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    layout.addWidget(group)
    layout.addStretch(1)
    return page, form


class BridgeMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RC Single-Span Bridge Analysis")
        self.resize(1280, 820)
        self._thread_pool = QThreadPool.globalInstance()
        self._current_path: Path | None = None
        self._last_result = None
        self._state = GuiProjectState()

        self._tabs = QTabWidget()
        self.setCentralWidget(self._tabs)
        self.setStatusBar(QStatusBar())

        self._build_toolbar()
        self._build_project_tab()
        self._build_geometry_tab()
        self._build_materials_tab()
        self._build_loads_tab()
        self._build_analysis_tab()
        self._build_results_tab()
        self._build_verification_tab()
        self._build_research_tab()
        self._apply_state(self._state)
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Project")
        self.addToolBar(toolbar)

        action_new = QAction("New", self)
        action_new.triggered.connect(self._new_project)
        toolbar.addAction(action_new)

        action_open = QAction("Open", self)
        action_open.triggered.connect(self._open_project)
        toolbar.addAction(action_open)

        action_save = QAction("Save", self)
        action_save.triggered.connect(self._save_project)
        toolbar.addAction(action_save)

        toolbar.addSeparator()
        action_run = QAction("Run Analysis", self)
        action_run.triggered.connect(self._run_analysis)
        toolbar.addAction(action_run)

    def _build_project_tab(self) -> None:
        page, form = _form_page("Project")
        self.project_name = QTextEdit()
        self.project_name.setMaximumHeight(60)
        form.addRow("Project name", self.project_name)
        self._tabs.addTab(page, "Project")

    def _build_geometry_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)

        general_box = QGroupBox("Bridge geometry")
        general = QFormLayout(general_box)
        self.span_m = _double_spin(15.0, suffix=" m")
        self.physical_length_m = _double_spin(14.95, suffix=" m")
        self.deck_width_m = _double_spin(11.0, suffix=" m")
        self.carriageway_width_m = _double_spin(7.0, suffix=" m")
        self.carriageway_offset_m = _double_spin(
            0.0,
            minimum=-100.0,
            maximum=100.0,
            suffix=" m",
        )
        self.girder_count = _int_spin(7, minimum=2, maximum=100)
        self.girder_spacing_m = _double_spin(1.70, suffix=" m")
        general.addRow("Analysis span", self.span_m)
        general.addRow("Physical girder length", self.physical_length_m)
        general.addRow("Deck width", self.deck_width_m)
        general.addRow("Carriageway width", self.carriageway_width_m)
        general.addRow("Carriageway offset", self.carriageway_offset_m)
        general.addRow("Girder count", self.girder_count)
        general.addRow("Girder spacing", self.girder_spacing_m)
        layout.addWidget(general_box)

        section_box = QGroupBox("Precast girder section")
        section_layout = QVBoxLayout(section_box)
        self.section_type = QComboBox()
        self.section_type.addItems(["Rectangular", "T", "I"])
        self.section_type.currentIndexChanged.connect(self._section_changed)
        section_layout.addWidget(self.section_type)

        self.section_stack = QStackedWidget()
        rect_page, rect_form = _form_page("Rectangular")
        self.rect_width = _double_spin(0.40, suffix=" m")
        self.rect_depth = _double_spin(0.95, suffix=" m")
        rect_form.addRow("Width", self.rect_width)
        rect_form.addRow("Depth", self.rect_depth)
        self.section_stack.addWidget(rect_page)

        t_page, t_form = _form_page("T-section")
        self.t_flange_width = _double_spin(1.70, suffix=" m")
        self.t_flange_thickness = _double_spin(0.175, suffix=" m")
        self.t_web_width = _double_spin(0.40, suffix=" m")
        self.t_total_depth = _double_spin(1.125, suffix=" m")
        t_form.addRow("Flange width", self.t_flange_width)
        t_form.addRow("Flange thickness", self.t_flange_thickness)
        t_form.addRow("Web width", self.t_web_width)
        t_form.addRow("Total depth", self.t_total_depth)
        self.section_stack.addWidget(t_page)

        i_page, i_form = _form_page("I-section")
        self.i_top_flange_width = _double_spin(0.40, suffix=" m")
        self.i_top_flange_thickness = _double_spin(0.15, suffix=" m")
        self.i_top_haunch = _double_spin(0.0, suffix=" m")
        self.i_web_width = _double_spin(0.20, suffix=" m")
        self.i_web_depth = _double_spin(0.65, suffix=" m")
        self.i_bottom_haunch = _double_spin(0.0, suffix=" m")
        self.i_bottom_flange_width = _double_spin(0.40, suffix=" m")
        self.i_bottom_flange_thickness = _double_spin(0.15, suffix=" m")
        i_form.addRow("Top flange width", self.i_top_flange_width)
        i_form.addRow("Top flange thickness", self.i_top_flange_thickness)
        i_form.addRow("Top haunch depth", self.i_top_haunch)
        i_form.addRow("Web width", self.i_web_width)
        i_form.addRow("Clear web depth", self.i_web_depth)
        i_form.addRow("Bottom haunch depth", self.i_bottom_haunch)
        i_form.addRow("Bottom flange width", self.i_bottom_flange_width)
        i_form.addRow("Bottom flange thickness", self.i_bottom_flange_thickness)
        self.section_stack.addWidget(i_page)

        section_layout.addWidget(self.section_stack)
        layout.addWidget(section_box)

        deck_box = QGroupBox("Deck construction")
        deck = QFormLayout(deck_box)
        self.false_slab_depth = _double_spin(0.075, suffix=" m")
        self.in_situ_depth = _double_spin(0.175, suffix=" m")
        self.false_slab_composite = QCheckBox("Participates in final composite section")
        self.in_situ_composite = QCheckBox("Participates in final composite section")
        self.in_situ_composite.setChecked(True)
        deck.addRow("Precast false slab", self.false_slab_depth)
        deck.addRow("", self.false_slab_composite)
        deck.addRow("Cast in-situ slab", self.in_situ_depth)
        deck.addRow("", self.in_situ_composite)
        layout.addWidget(deck_box)
        layout.addStretch(1)
        self._tabs.addTab(page, "Geometry")

    def _build_materials_tab(self) -> None:
        page, form = _form_page("Materials and reinforcement")
        self.fck_mpa = _double_spin(35.0, suffix=" MPa")
        self.fcu_mpa = _double_spin(45.0, suffix=" MPa")
        self.fyk_mpa = _double_spin(500.0, suffix=" MPa")
        self.density = _double_spin(25.0, suffix=" kN/m³")
        self.elastic_modulus = _double_spin(34000.0, suffix=" MPa", decimals=0, step=100.0)
        self.rebar_layers = _int_spin(4, minimum=1, maximum=20)
        self.bars_per_layer = _int_spin(4, minimum=1, maximum=30)
        self.bar_diameter = _double_spin(32.0, suffix=" mm", decimals=1, step=1.0)
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
        page, form = _form_page("Permanent actions")
        self.surfacing_thickness = _double_spin(0.080, suffix=" m")
        self.surfacing_density = _double_spin(22.0, suffix=" kN/m³")
        self.barrier_load = _double_spin(10.0, suffix=" kN/m")
        self.services_load = _double_spin(2.0, suffix=" kN/m")
        form.addRow("Surfacing thickness", self.surfacing_thickness)
        form.addRow("Surfacing density", self.surfacing_density)
        form.addRow("Barrier line load (each side)", self.barrier_load)
        form.addRow("Services line load (each side)", self.services_load)
        note = QLabel(
            "The GUI keeps these values explicit. They are not silently treated as surveyed "
            "or as-built data."
        )
        note.setWordWrap(True)
        form.addRow(note)
        self._tabs.addTab(page, "Loads")

    def _build_analysis_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        box = QGroupBox("Analysis settings")
        form = QFormLayout(box)

        self.code_profile = QComboBox()
        self.code_profile.addItems([GuiCodeProfile.BS_EN.value, GuiCodeProfile.BS_5400.value])
        self.psi1_tandem = _double_spin(0.75, maximum=1.0, decimals=2, step=0.05)
        self.psi1_udl = _double_spin(0.40, maximum=1.0, decimals=2, step=0.05)
        self.psi2_traffic = _double_spin(0.0, maximum=1.0, decimals=2, step=0.05)
        self.lm1_step = _double_spin(0.6, minimum=0.05, maximum=5.0, suffix=" m")
        self.hb_units = _double_spin(45.0, minimum=1.0, maximum=100.0, decimals=1)
        self.retain_cases = QCheckBox("Retain all traffic cases for detailed review")

        form.addRow("Code profile", self.code_profile)
        form.addRow("BS EN frequent TS factor ψ1", self.psi1_tandem)
        form.addRow("BS EN frequent UDL factor ψ1", self.psi1_udl)
        form.addRow("BS EN quasi-permanent ψ2", self.psi2_traffic)
        form.addRow("LM1 longitudinal step", self.lm1_step)
        form.addRow("HB units", self.hb_units)
        form.addRow("", self.retain_cases)
        layout.addWidget(box)

        self.run_button = QPushButton("Run deterministic analysis")
        self.run_button.clicked.connect(self._run_analysis)
        layout.addWidget(self.run_button)

        self.analysis_note = QLabel(
            "Runs the verified common deterministic engine. Design/detailing checks are only "
            "reported when their required project-specific inputs are supplied."
        )
        self.analysis_note.setWordWrap(True)
        layout.addWidget(self.analysis_note)
        layout.addStretch(1)
        self._tabs.addTab(page, "Analysis")

    def _build_results_tab(self) -> None:
        page = QWidget()
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
        self.results_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.results_table)

        self.result_notes = QTextEdit()
        self.result_notes.setReadOnly(True)
        self.result_notes.setMaximumHeight(130)
        layout.addWidget(self.result_notes)
        self._tabs.addTab(page, "Results")

    def _build_verification_tab(self) -> None:
        page = QWidget()
        layout = QVBoxLayout(page)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "Deterministic verification status\n\n"
            "• BS EN deterministic V1: verified within the documented software scope.\n"
            "• BS 5400 / BD 37 deterministic V1: verified within the documented software scope.\n"
            "• External STAAD evidence verifies structural-response behaviour for the documented "
            "reference campaign; it is not approval of an individual bridge.\n\n"
            "Planned GUI additions: STAAD export/import review, calculation-report browser, "
            "verification evidence viewer and model comparison dashboard."
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
            "The research engine already contains LHS sampling, ANN surrogate training, FORM, "
            "Monte Carlo validation, dependence support and RBDO infrastructure. This GUI tab "
            "will expose those controls after the deterministic project/results workflow is stable.\n\n"
            "Research outputs remain validation-pending until the probabilistic model, sample-size "
            "convergence, surrogate accuracy near g=0, reliability cross-checks and final optimum "
            "verification are documented."
        )
        layout.addWidget(text)
        self._tabs.addTab(page, "ANN / Reliability")

    def _section_changed(self, index: int) -> None:
        self.section_stack.setCurrentIndex(index)

    def _read_state(self) -> GuiProjectState:
        section_value = ("rectangular", "t", "i")[self.section_type.currentIndex()]
        return GuiProjectState(
            name=self.project_name.toPlainText().strip() or "Untitled bridge project",
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
            retain_all_cases=self.retain_cases.isChecked(),
            hb_units=self.hb_units.value(),
        )

    def _apply_state(self, state: GuiProjectState) -> None:
        self._state = state
        self.project_name.setPlainText(state.name)
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

    def _new_project(self) -> None:
        self._current_path = None
        self._last_result = None
        self._apply_state(GuiProjectState())
        self.results_table.setRowCount(0)
        self.result_basis.setText("No analysis run yet.")
        self.statusBar().showMessage("New project")

    def _open_project(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open bridge project",
            "",
            "Bridge project (*.json);;JSON (*.json)",
        )
        if not file_name:
            return
        try:
            payload = json.loads(Path(file_name).read_text(encoding="utf-8"))
            state = GuiProjectState.from_dict(payload["project"])
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._current_path = Path(file_name)
        self._apply_state(state)
        analysis = payload.get("analysis", {})
        code = analysis.get("code_profile")
        if code in {profile.value for profile in GuiCodeProfile}:
            self.code_profile.setCurrentText(code)
        self.statusBar().showMessage(f"Opened {file_name}")

    def _save_project(self) -> None:
        try:
            state = self._read_state()
            state.build_project()
            settings = self._read_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid project", str(exc))
            return

        target = self._current_path
        if target is None:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save bridge project",
                "bridge_project.json",
                "Bridge project (*.json)",
            )
            if not file_name:
                return
            target = Path(file_name)
        payload = {
            "format": "rc-single-span-bridge-gui-v1",
            "project": state.as_dict(),
            "analysis": {
                "code_profile": settings.code_profile.value,
                "psi1_tandem": settings.psi1_tandem,
                "psi1_udl": settings.psi1_udl,
                "psi2_traffic": settings.psi2_traffic,
                "lm1_step_m": settings.lm1_step_m,
                "hb_units": settings.hb_units,
                "retain_all_cases": settings.retain_all_cases,
            },
        }
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self._current_path = target
        self.statusBar().showMessage(f"Saved {target}")

    def _run_analysis(self) -> None:
        if not self.run_button.isEnabled():
            return
        try:
            state = self._read_state()
            state.build_project()
            settings = self._read_settings()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid analysis input", str(exc))
            return

        self.run_button.setEnabled(False)
        self.statusBar().showMessage("Running deterministic analysis…")
        worker = _AnalysisWorker(state, settings)
        worker.signals.finished.connect(self._analysis_finished)
        worker.signals.error.connect(self._analysis_failed)
        self._thread_pool.start(worker)

    @Slot(object, object)
    def _analysis_finished(self, result, summary: GuiAnalysisSummary) -> None:
        self._last_result = result
        self.run_button.setEnabled(True)
        self.statusBar().showMessage("Analysis complete")
        self._show_summary(summary)
        self._tabs.setCurrentWidget(self.results_table.parentWidget())

    @Slot(str)
    def _analysis_failed(self, details: str) -> None:
        self.run_button.setEnabled(True)
        self.statusBar().showMessage("Analysis failed")
        QMessageBox.critical(self, "Analysis failed", details)

    def _show_summary(self, summary: GuiAnalysisSummary) -> None:
        self.result_basis.setText(f"Code basis: {summary.code_basis}")
        moment = summary.governing_moment
        shear = summary.governing_shear
        torsion = summary.governing_torsion
        self.governing_moment.setText(
            f"{moment.moment_knm:,.2f} kNm — Girder {moment.girder}"
        )
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
        self.result_notes.setPlainText("\n".join(f"• {note}" for note in summary.notes))


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("RC Single-Span Bridge Analysis")
    window = BridgeMainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
