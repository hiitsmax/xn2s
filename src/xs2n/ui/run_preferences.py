from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import fltk

from xs2n.ui.run_arguments import DigestRunArguments, LatestRunArguments, RunCommand
from xs2n.ui.fltk_style import apply_widget_theme, style_widget
from xs2n.ui.run_list import (
    DEFAULT_RUN_LIST_COLUMN_KEYS,
    RUN_LIST_COLUMNS,
    normalize_run_list_column_keys,
)
from xs2n.ui.theme import (
    APPEARANCE_MODE_OPTIONS,
    CLASSIC_LIGHT_THEME,
    UiTheme,
    normalize_appearance_mode,
    to_fltk_color,
)


PREFERENCES_WINDOW_WIDTH = 820
PREFERENCES_WINDOW_HEIGHT = 372
WINDOW_PADDING = 12
FORM_ROW_HEIGHT = 24
FORM_ROW_GAP = 10
FORM_LABEL_WIDTH = 108
FORM_COLUMN_GAP = 24
ACTION_ROW_HEIGHT = 32
ACTION_BUTTON_WIDTH = 88
ACTION_BUTTON_GAP = 8


@dataclass(slots=True)
class _AppliedPreferencesState:
    digest_arguments: DigestRunArguments
    latest_arguments: LatestRunArguments
    run_list_column_keys: tuple[str, ...]
    appearance_mode: str
    digest_navigation_visible: bool


class RunPreferencesWindow:
    def __init__(
        self,
        *,
        appearance_mode: str = "system",
        digest_navigation_visible: bool = False,
        theme: UiTheme = CLASSIC_LIGHT_THEME,
        on_appearance_mode_changed: Callable[[str], None] | None = None,
        on_digest_navigation_preference_changed: Callable[[bool], None] | None = None,
        on_run_list_preferences_changed: Callable[[tuple[str, ...]], None]
        | None = None,
    ) -> None:
        self.theme = theme
        self.on_appearance_mode_changed = on_appearance_mode_changed
        self.on_digest_navigation_preference_changed = (
            on_digest_navigation_preference_changed
        )
        self.on_run_list_preferences_changed = on_run_list_preferences_changed
        self.run_list_column_toggles: dict[str, object] = {}
        self.form_inputs: list[object] = []
        self.form_checkboxes: list[object] = []
        self.form_selects: list[object] = []
        self.static_labels: list[object] = []
        self.applied_state = _AppliedPreferencesState(
            digest_arguments=DigestRunArguments(),
            latest_arguments=LatestRunArguments(),
            run_list_column_keys=DEFAULT_RUN_LIST_COLUMN_KEYS,
            appearance_mode=normalize_appearance_mode(appearance_mode),
            digest_navigation_visible=bool(digest_navigation_visible),
        )
        self.window = fltk.Fl_Double_Window(
            PREFERENCES_WINDOW_WIDTH,
            PREFERENCES_WINDOW_HEIGHT,
            "Preferences",
        )
        self._build_window()
        self._reset_draft_to_applied()
        self.apply_theme(self.theme)

    def show(self) -> None:
        self.window.show()

    def hide(self) -> None:
        self.window.hide()

    def show_digest_tab(self) -> None:
        self.tabs.value(self.digest_tab)
        self.show()

    def show_issues_tab(self) -> None:
        self.show_digest_tab()

    def show_latest_tab(self) -> None:
        self.tabs.value(self.latest_tab)
        self.show()

    def show_run_list_tab(self) -> None:
        self.tabs.value(self.run_list_tab)
        self.show()

    def show_appearance_tab(self) -> None:
        self.tabs.value(self.appearance_tab)
        self.show()

    def current_digest_command(self) -> RunCommand:
        return self.applied_state.digest_arguments.to_command()

    def current_issues_command(self) -> RunCommand:
        return self.current_digest_command()

    def current_latest_command(self) -> RunCommand:
        return self.applied_state.latest_arguments.to_command()

    def current_following_refresh_command(self) -> RunCommand:
        return self.applied_state.latest_arguments.to_following_refresh_command()

    def current_run_list_column_keys(self) -> tuple[str, ...]:
        return self.applied_state.run_list_column_keys

    def current_appearance_mode(self) -> str:
        return self.applied_state.appearance_mode

    def current_digest_navigation_visible(self) -> bool:
        return self.applied_state.digest_navigation_visible

    def _build_window(self) -> None:
        self.window.begin()
        style_widget(self.window, label_size=14)

        tabs_width = PREFERENCES_WINDOW_WIDTH - (WINDOW_PADDING * 2)
        tabs_height = PREFERENCES_WINDOW_HEIGHT - (
            (WINDOW_PADDING * 2) + ACTION_ROW_HEIGHT + FORM_ROW_GAP
        )
        tabs_group_x = WINDOW_PADDING + 4
        tabs_group_y = WINDOW_PADDING + 28
        tabs_group_width = tabs_width - 8
        tabs_group_height = tabs_height - 34
        tab_body_x = tabs_group_x + 8
        tab_body_y = tabs_group_y + 10
        tab_body_width = tabs_group_width - 16

        self.tabs = fltk.Fl_Tabs(
            WINDOW_PADDING,
            WINDOW_PADDING,
            tabs_width,
            tabs_height,
        )
        style_widget(self.tabs, label_size=13, text_size=13)
        self.tabs.begin()

        self.appearance_tab = fltk.Fl_Group(
            tabs_group_x,
            tabs_group_y,
            tabs_group_width,
            tabs_group_height,
            "Appearance",
        )
        self.appearance_tab.begin()
        self._build_appearance_tab(
            x=tab_body_x,
            y=tab_body_y,
            width=tab_body_width,
        )
        self.appearance_tab.end()

        self.digest_tab = fltk.Fl_Group(
            tabs_group_x,
            tabs_group_y,
            tabs_group_width,
            tabs_group_height,
            "Issues",
        )
        self.digest_tab.begin()
        self._build_digest_tab(
            x=tab_body_x,
            y=tab_body_y,
            width=tab_body_width,
        )
        self.digest_tab.end()

        self.latest_tab = fltk.Fl_Group(
            tabs_group_x,
            tabs_group_y,
            tabs_group_width,
            tabs_group_height,
            "Latest",
        )
        self.latest_tab.begin()
        self._build_latest_tab(
            x=tab_body_x,
            y=tab_body_y,
            width=tab_body_width,
        )
        self.latest_tab.end()

        self.run_list_tab = fltk.Fl_Group(
            tabs_group_x,
            tabs_group_y,
            tabs_group_width,
            tabs_group_height,
            "Run List",
        )
        self.run_list_tab.begin()
        self._build_run_list_tab(
            x=tab_body_x,
            y=tab_body_y,
            width=tab_body_width,
        )
        self.run_list_tab.end()

        self.tabs.end()
        self.tabs.value(self.appearance_tab)

        action_y = WINDOW_PADDING + tabs_height + FORM_ROW_GAP
        cancel_x = PREFERENCES_WINDOW_WIDTH - WINDOW_PADDING - ACTION_BUTTON_WIDTH
        apply_x = cancel_x - ACTION_BUTTON_GAP - ACTION_BUTTON_WIDTH

        self.apply_button = fltk.Fl_Return_Button(
            apply_x,
            action_y,
            ACTION_BUTTON_WIDTH,
            ACTION_ROW_HEIGHT,
            "Apply",
        )
        style_widget(self.apply_button, label_size=12, bold=True)
        self.apply_button.callback(self._on_apply_clicked, None)

        self.cancel_button = fltk.Fl_Button(
            cancel_x,
            action_y,
            ACTION_BUTTON_WIDTH,
            ACTION_ROW_HEIGHT,
            "Cancel",
        )
        style_widget(self.cancel_button, label_size=12)
        self.cancel_button.callback(self._on_cancel_clicked, None)

        self.window.end()
        self.window.resizable(self.tabs)
        self.window.callback(self._on_close_clicked, None)

    def _build_appearance_tab(
        self,
        *,
        x: int,
        y: int,
        width: int,
    ) -> None:
        intro = fltk.Fl_Box(
            x,
            y,
            width,
            FORM_ROW_HEIGHT * 2,
            "Choose whether the desktop UI follows the system appearance or uses an explicit classic theme override.",
        )
        intro.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_WRAP)
        style_widget(intro, label_size=12)
        self.static_labels.append(intro)

        self.appearance_mode_choice = self._create_choice_input(
            x=x,
            y=y + (FORM_ROW_HEIGHT * 2) + FORM_ROW_GAP,
            width=width,
            label="Mode",
            options=APPEARANCE_MODE_OPTIONS,
            value=self.applied_state.appearance_mode,
            tooltip="`System` follows the OS appearance at launch. The classic overrides force the app theme immediately.",
        )
        self.digest_navigation_toggle = self._create_checkbox_input(
            x=x,
            y=y + (FORM_ROW_HEIGHT * 3) + (FORM_ROW_GAP * 2),
            width=width,
            label="Keep middle navigation column visible in digest viewer",
            value=self.applied_state.digest_navigation_visible,
            tooltip=(
                "When disabled, selecting `digest.html` hides the middle column "
                "and lets the digest viewer take that space."
            ),
        )

    def _build_digest_tab(
        self,
        *,
        x: int,
        y: int,
        width: int,
    ) -> None:
        default_digest_arguments = DigestRunArguments()
        row_y = y

        self.digest_timeline_input = self._create_text_input(
            x=x,
            y=row_y,
            width=width,
            label="Timeline",
            value=str(default_digest_arguments.timeline_file),
            tooltip="Timeline JSON used by `xs2n report issues`.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.digest_output_dir_input = self._create_text_input(
            x=x,
            y=row_y,
            width=width,
            label="Output dir",
            value=str(default_digest_arguments.output_dir),
            tooltip="Directory where issue run artifacts are written.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.digest_model_input = self._create_text_input(
            x=x,
            y=row_y,
            width=width,
            label="Model",
            value=default_digest_arguments.model,
            tooltip="Model name passed through to `xs2n report issues`.",
        )

    def _build_latest_tab(
        self,
        *,
        x: int,
        y: int,
        width: int,
    ) -> None:
        default_latest_arguments = LatestRunArguments()
        column_width = (width - FORM_COLUMN_GAP) // 2
        left_x = x
        right_x = x + column_width + FORM_COLUMN_GAP
        row_y = y

        self.latest_since_input = self._create_text_input(
            x=left_x,
            y=row_y,
            width=column_width,
            label="Since",
            value="",
            tooltip="Optional ISO datetime. Leave blank to use the lookback window instead.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_lookback_hours_input = self._create_text_input(
            x=left_x,
            y=row_y,
            width=column_width,
            label="Lookback",
            value=str(default_latest_arguments.lookback_hours),
            input_class=fltk.Fl_Int_Input,
            tooltip="Used when `Since` is blank.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_cookies_file_input = self._create_text_input(
            x=left_x,
            y=row_y,
            width=column_width,
            label="Cookies",
            value=str(default_latest_arguments.cookies_file),
            tooltip="Twikit cookies file for authenticated timeline scraping.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_limit_input = self._create_text_input(
            x=left_x,
            y=row_y,
            width=column_width,
            label="Limit",
            value=str(default_latest_arguments.limit),
            input_class=fltk.Fl_Int_Input,
            tooltip="Maximum number of timeline entries to ingest in this run.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_timeline_file_input = self._create_text_input(
            x=left_x,
            y=row_y,
            width=column_width,
            label="Timeline",
            value=str(default_latest_arguments.timeline_file),
            tooltip="Timeline JSON written by the ingestion step and read by digest generation.",
        )

        row_y = y
        self.latest_sources_file_input = self._create_text_input(
            x=right_x,
            y=row_y,
            width=column_width,
            label="Sources",
            value=str(default_latest_arguments.sources_file),
            tooltip="Source catalog used when Home -> Following mode is disabled.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_output_dir_input = self._create_text_input(
            x=right_x,
            y=row_y,
            width=column_width,
            label="Output dir",
            value=str(default_latest_arguments.output_dir),
            tooltip="Directory where issue run artifacts are written.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_model_input = self._create_text_input(
            x=right_x,
            y=row_y,
            width=column_width,
            label="Model",
            value=default_latest_arguments.model,
            tooltip="Model name passed through to `xs2n report latest`.",
        )
        row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
        self.latest_home_latest_toggle = self._create_checkbox_input(
            x=right_x,
            y=row_y,
            width=column_width,
            label="Use Home -> Following feed",
            value=default_latest_arguments.home_latest,
            tooltip=(
                "When enabled, `report latest` uses the authenticated Home -> "
                "Following timeline instead of the sources file."
            ),
        )

    def _build_run_list_tab(
        self,
        *,
        x: int,
        y: int,
        width: int,
    ) -> None:
        intro = fltk.Fl_Box(
            x,
            y,
            width,
            FORM_ROW_HEIGHT * 2,
            "Choose which columns appear in the left run list.\nChanges apply only when you click Apply.",
        )
        intro.align(fltk.FL_ALIGN_LEFT | fltk.FL_ALIGN_INSIDE | fltk.FL_ALIGN_CLIP)
        style_widget(intro, label_size=12)
        self.static_labels.append(intro)

        column_width = (width - FORM_COLUMN_GAP) // 2
        left_x = x
        right_x = x + column_width + FORM_COLUMN_GAP
        row_y = y + (FORM_ROW_HEIGHT * 2) + FORM_ROW_GAP

        for index, column in enumerate(RUN_LIST_COLUMNS):
            column_x = left_x if index % 2 == 0 else right_x
            if index and index % 2 == 0:
                row_y += FORM_ROW_HEIGHT + FORM_ROW_GAP
            checkbox = self._create_checkbox_input(
                x=column_x,
                y=row_y,
                width=column_width,
                label=column.label,
                value=column.key in DEFAULT_RUN_LIST_COLUMN_KEYS,
                tooltip=column.tooltip,
            )
            self.run_list_column_toggles[column.key] = checkbox

    def _on_close_clicked(self, widget=None, data=None) -> None:  # noqa: ANN001
        self._cancel_pending_changes()

    def _on_apply_clicked(
        self,
        widget=None,
        data=None,
    ) -> None:  # noqa: ANN001
        try:
            digest_arguments = self._draft_digest_arguments()
        except ValueError as error:
            self.show_digest_tab()
            fltk.fl_alert(str(error))
            return

        try:
            latest_arguments = self._draft_latest_arguments()
        except ValueError as error:
            self.show_latest_tab()
            fltk.fl_alert(str(error))
            return

        run_list_column_keys = self._draft_run_list_column_keys()
        appearance_mode = self._draft_appearance_mode()
        digest_navigation_visible = self._draft_digest_navigation_visible()

        applied_state = self.applied_state
        run_list_changed = run_list_column_keys != applied_state.run_list_column_keys
        appearance_changed = appearance_mode != applied_state.appearance_mode
        digest_navigation_changed = (
            digest_navigation_visible != applied_state.digest_navigation_visible
        )
        self.applied_state = _AppliedPreferencesState(
            digest_arguments=digest_arguments,
            latest_arguments=latest_arguments,
            run_list_column_keys=run_list_column_keys,
            appearance_mode=appearance_mode,
            digest_navigation_visible=digest_navigation_visible,
        )
        self._reset_draft_to_applied()

        if run_list_changed and self.on_run_list_preferences_changed is not None:
            self.on_run_list_preferences_changed(
                self.applied_state.run_list_column_keys
            )
        if appearance_changed and self.on_appearance_mode_changed is not None:
            self.on_appearance_mode_changed(self.applied_state.appearance_mode)
        if (
            digest_navigation_changed
            and self.on_digest_navigation_preference_changed is not None
        ):
            self.on_digest_navigation_preference_changed(
                self.applied_state.digest_navigation_visible
            )

    def _on_cancel_clicked(
        self,
        widget=None,
        data=None,
    ) -> None:  # noqa: ANN001
        self._cancel_pending_changes()

    def _cancel_pending_changes(self) -> None:
        self._reset_draft_to_applied()
        self.hide()

    def _draft_digest_arguments(self) -> DigestRunArguments:
        return DigestRunArguments.from_form(
            timeline_file=self.digest_timeline_input.value(),
            output_dir=self.digest_output_dir_input.value(),
            model=self.digest_model_input.value(),
        )

    def _draft_latest_arguments(self) -> LatestRunArguments:
        return LatestRunArguments.from_form(
            since=self.latest_since_input.value(),
            lookback_hours=self.latest_lookback_hours_input.value(),
            cookies_file=self.latest_cookies_file_input.value(),
            limit=self.latest_limit_input.value(),
            timeline_file=self.latest_timeline_file_input.value(),
            sources_file=self.latest_sources_file_input.value(),
            home_latest=bool(self.latest_home_latest_toggle.value()),
            output_dir=self.latest_output_dir_input.value(),
            model=self.latest_model_input.value(),
        )

    def _draft_run_list_column_keys(self) -> tuple[str, ...]:
        selected_keys = tuple(
            column.key
            for column in RUN_LIST_COLUMNS
            if self.run_list_column_toggles[column.key].value()
        )
        return normalize_run_list_column_keys(selected_keys)

    def _draft_appearance_mode(self) -> str:
        raw_value = self.appearance_mode_choice.value()
        if isinstance(raw_value, str):
            return normalize_appearance_mode(raw_value)
        if isinstance(raw_value, int):
            if 0 <= raw_value < len(APPEARANCE_MODE_OPTIONS):
                return APPEARANCE_MODE_OPTIONS[raw_value][1]
        return "system"

    def _draft_digest_navigation_visible(self) -> bool:
        return bool(self.digest_navigation_toggle.value())

    def _reset_draft_to_applied(self) -> None:
        self._write_digest_arguments(self.applied_state.digest_arguments)
        self._write_latest_arguments(self.applied_state.latest_arguments)
        self._write_run_list_column_keys(self.applied_state.run_list_column_keys)
        self._write_appearance_mode(self.applied_state.appearance_mode)
        self._write_digest_navigation_visible(
            self.applied_state.digest_navigation_visible
        )

    def _write_digest_arguments(self, arguments: DigestRunArguments) -> None:
        self.digest_timeline_input.value(str(arguments.timeline_file))
        self.digest_output_dir_input.value(str(arguments.output_dir))
        self.digest_model_input.value(arguments.model)

    def _write_latest_arguments(self, arguments: LatestRunArguments) -> None:
        self.latest_since_input.value(arguments.since or "")
        self.latest_lookback_hours_input.value(str(arguments.lookback_hours))
        self.latest_cookies_file_input.value(str(arguments.cookies_file))
        self.latest_limit_input.value(str(arguments.limit))
        self.latest_timeline_file_input.value(str(arguments.timeline_file))
        self.latest_sources_file_input.value(str(arguments.sources_file))
        self.latest_home_latest_toggle.value(int(arguments.home_latest))
        self.latest_output_dir_input.value(str(arguments.output_dir))
        self.latest_model_input.value(arguments.model)

    def _write_run_list_column_keys(self, column_keys: tuple[str, ...]) -> None:
        normalized_keys = normalize_run_list_column_keys(column_keys)
        selected_keys = set(normalized_keys)
        for column in RUN_LIST_COLUMNS:
            self.run_list_column_toggles[column.key].value(
                int(column.key in selected_keys)
            )

    def _write_appearance_mode(self, appearance_mode: str) -> None:
        normalized_mode = normalize_appearance_mode(appearance_mode)
        index = next(
            (
                option_index
                for option_index, (_label, mode) in enumerate(APPEARANCE_MODE_OPTIONS)
                if mode == normalized_mode
            ),
            0,
        )
        if hasattr(self.appearance_mode_choice, "text"):
            self.appearance_mode_choice.value(index)
            return
        self.appearance_mode_choice.value(normalized_mode)

    def _write_digest_navigation_visible(self, visible: bool) -> None:
        self.digest_navigation_toggle.value(int(visible))

    def _create_text_input(  # noqa: ANN001
        self,
        *,
        x: int,
        y: int,
        width: int,
        label: str,
        value: str,
        tooltip: str,
        input_class=fltk.Fl_Input,
    ):
        widget = input_class(
            x + FORM_LABEL_WIDTH,
            y,
            width - FORM_LABEL_WIDTH,
            FORM_ROW_HEIGHT,
            label,
        )
        widget.box(fltk.FL_BORDER_BOX)
        widget.value(value)
        widget.tooltip(tooltip)
        style_widget(widget, label_size=12, text_size=13)
        self.form_inputs.append(widget)
        return widget

    def _create_checkbox_input(  # noqa: ANN001
        self,
        *,
        x: int,
        y: int,
        width: int,
        label: str,
        value: bool,
        tooltip: str,
    ):
        widget = fltk.Fl_Check_Button(
            x,
            y,
            width,
            FORM_ROW_HEIGHT,
            label,
        )
        widget.value(int(value))
        widget.tooltip(tooltip)
        style_widget(widget, label_size=12)
        self.form_checkboxes.append(widget)
        return widget

    def _create_choice_input(  # noqa: ANN001
        self,
        *,
        x: int,
        y: int,
        width: int,
        label: str,
        options: tuple[tuple[str, str], ...],
        value: str,
        tooltip: str,
    ):
        widget = fltk.Fl_Choice(
            x + FORM_LABEL_WIDTH,
            y,
            width - FORM_LABEL_WIDTH,
            FORM_ROW_HEIGHT,
            label,
        )
        widget.box(fltk.FL_BORDER_BOX)
        for option_label, _option_value in options:
            widget.add(option_label)
        widget.tooltip(tooltip)
        style_widget(widget, label_size=12, text_size=13)
        self.form_selects.append(widget)
        normalized_value = normalize_appearance_mode(value)
        selected_index = next(
            (
                option_index
                for option_index, (_option_label, option_value) in enumerate(options)
                if option_value == normalized_value
            ),
            0,
        )
        widget.value(selected_index)
        return widget

    def apply_theme(self, theme: UiTheme) -> None:
        self.theme = theme
        window_color = to_fltk_color(fltk, theme.window_bg)
        panel_color = to_fltk_color(fltk, theme.panel_bg)
        panel_bg2_color = to_fltk_color(fltk, theme.panel_bg2)
        pressed_color = to_fltk_color(fltk, theme.control_pressed_bg)
        text_color = to_fltk_color(fltk, theme.text)
        muted_text_color = to_fltk_color(fltk, theme.muted_text)
        selection_color = to_fltk_color(fltk, theme.selection_bg)

        apply_widget_theme((self.window,), color=window_color)
        apply_widget_theme(
            (self.tabs,),
            color=panel_color,
            selection_color=selection_color,
            label_color=text_color,
        )
        apply_widget_theme(
            (
                self.appearance_tab,
                self.digest_tab,
                self.latest_tab,
                self.run_list_tab,
            ),
            color=window_color,
            label_color=text_color,
        )
        apply_widget_theme(
            self.static_labels,
            color=window_color,
            label_color=muted_text_color,
        )
        apply_widget_theme(
            self.form_inputs,
            color=panel_bg2_color,
            selection_color=selection_color,
            text_color=text_color,
            label_color=text_color,
        )
        apply_widget_theme(
            self.form_selects,
            color=panel_bg2_color,
            selection_color=selection_color,
            text_color=text_color,
            label_color=text_color,
        )
        apply_widget_theme(
            self.form_checkboxes,
            color=window_color,
            selection_color=selection_color,
            label_color=text_color,
        )
        apply_widget_theme(
            (self.apply_button, self.cancel_button),
            color=panel_color,
            selection_color=pressed_color,
            label_color=text_color,
        )

        self.window.redraw()
