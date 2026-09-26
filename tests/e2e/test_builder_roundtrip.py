"""
E2E tests for the cue builder.

These tests guard against action-mapping bugs: the builder translates between
YAML action types (what the engine uses) and UI types (what the builder shows).
A broken mapping renders steps as "No configuration needed" with no fields.
"""
import pytest
from playwright.sync_api import Page, expect


def open_builder_tab(page: Page):
    page.click('[data-tab="routines"]')
    page.wait_for_selector("#bldr-steps", timeout=3000)


def load_cue(page: Page, cue_id: str):
    """Click a cue in the library sidebar to load it into the builder."""
    page.wait_for_selector(f'.bldr-lib-item[data-id="{cue_id}"]', timeout=5000)
    page.click(f'.bldr-lib-item[data-id="{cue_id}"]')
    page.wait_for_function(
        "document.querySelectorAll('#bldr-steps .bldr-step').length > 0",
        timeout=5000,
    )


def expand_step(page: Page, step_index: int):
    """Click the ▼ expand button on a step to open its property form.

    bldrToggleExpand() re-renders the whole card, so we must not hold a stale
    element reference across the click — re-query from the page after.
    """
    steps = page.query_selector_all("#bldr-steps .bldr-step")
    assert step_index < len(steps), f"No step at index {step_index}"
    expand_btn = steps[step_index].query_selector(".bldr-step-actions button:first-child")
    assert expand_btn is not None, "Expand button not found"
    expand_btn.click()
    # Re-query after re-render; nth-of-type is 1-based
    page.wait_for_selector(
        f"#bldr-steps .bldr-step:nth-child({step_index + 1}) .bldr-step-form",
        timeout=3000,
    )


def get_step_type(page: Page, step_index: int) -> str:
    steps = page.query_selector_all("#bldr-steps .bldr-step")
    return steps[step_index].query_selector(".bldr-step-type").inner_text()


class TestSetVarRoundtrip:
    """
    YAML stores set_var; the builder must display it as set_flag / clear_flag.
    Bug: mapLoadedAction was missing the set_var → set_flag conversion, so
    steps loaded as type 'set_var' (unknown to ACT) and showed 'No configuration needed'.
    """

    def test_set_var_true_loads_as_set_flag(self, page: Page):
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")

        step_type = get_step_type(page, 0)
        assert step_type.upper() == "SET FLAG", (
            f"Expected 'SET FLAG', got '{step_type}' — "
            "set_var(value=true) must map to set_flag in the builder"
        )

    def test_set_var_false_loads_as_clear_flag(self, page: Page):
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")

        step_type = get_step_type(page, 1)
        assert step_type.upper() == "CLEAR FLAG", (
            f"Expected 'CLEAR FLAG', got '{step_type}' — "
            "set_var(value=false) must map to clear_flag in the builder"
        )

    def test_set_flag_form_has_configuration(self, page: Page):
        """Expanding a set_flag step must show a flag name input, not the fallback message."""
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")
        expand_step(page, 0)

        form = page.query_selector("#bldr-steps .bldr-step:nth-child(1) .bldr-step-form")
        assert "No configuration needed" not in form.inner_text(), (
            "set_flag step shows 'No configuration needed' — "
            "the ACT definition is missing or the type mapping failed"
        )

    def test_set_flag_flag_name_is_populated(self, page: Page):
        """
        The flag field renders as a <select> for known flags.
        The select's selected value must equal the flag name from the loaded action.
        """
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")
        expand_step(page, 0)

        flag_select = page.query_selector(
            "#bldr-steps .bldr-step:nth-child(1) .bldr-step-form select"
        )
        assert flag_select is not None, "Flag select not found in set_flag form"
        selected = flag_select.input_value()
        assert selected == "e2e_flag", (
            f"Expected flag select value 'e2e_flag', got '{selected}'"
        )


class TestPixelChaseDurationRoundtrip:
    """
    pixel_chase stores duration_ms in milliseconds in YAML but the builder
    displays it in seconds. On load, mapLoadedAction must divide by 1000.
    Bug: without the conversion, a 3000ms chase displayed as '3000' in the
    seconds field instead of '3'.
    """

    def test_pixel_chase_step_type_label(self, page: Page):
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")

        step_type = get_step_type(page, 2)
        assert "PIXEL" in step_type.upper(), (
            f"Expected pixel chase step at index 2, got '{step_type}'"
        )

    def test_pixel_chase_duration_displayed_in_seconds(self, page: Page):
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")
        expand_step(page, 2)

        form = page.query_selector("#bldr-steps .bldr-step:nth-child(3) .bldr-step-form")

        # Find the duration field by checking label text within each .bldr-field div
        # (can't zip all-labels with all-inputs because mixed field types misalign them)
        duration_val = None
        for field_div in form.query_selector_all(".bldr-field"):
            label_el = field_div.query_selector("label")
            inp_el = field_div.query_selector("input[type=number]")
            if label_el and inp_el and "duration" in label_el.inner_text().lower():
                duration_val = float(inp_el.input_value())
                break

        assert duration_val is not None, "Duration field not found in pixel_chase form"
        assert duration_val == pytest.approx(3.0), (
            f"Expected duration 3.0s (converted from 3000ms in YAML), got {duration_val} — "
            "mapLoadedAction must divide duration_ms by 1000 for pixel_chase"
        )


class TestBuilderTabNavigation:
    """Basic smoke tests — ensures the builder loads without JS errors."""

    def test_builder_tab_loads(self, page: Page):
        open_builder_tab(page)
        expect(page.locator("#bldr-steps")).to_be_visible()
        expect(page.locator(".bldr-add-btn")).to_be_visible()

    def test_library_sidebar_shows_cues(self, page: Page):
        open_builder_tab(page)
        page.wait_for_selector(".bldr-lib-item", timeout=5000)
        items = page.query_selector_all(".bldr-lib-item")
        assert len(items) > 0, "Library sidebar must show at least one loaded cue"

    def test_no_js_errors_on_load(self, page: Page):
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        open_builder_tab(page)
        load_cue(page, "_e2e_test_cue")
        assert errors == [], f"JS errors on page: {errors}"


class TestManualTabFixtures:
    """Manual tab must show fixture cards once setup data is loaded."""

    def test_manual_tab_shows_fixture_cards(self, page: Page):
        page.click('[data-tab="manual"]')
        page.wait_for_selector("#manual-fixture-grid", timeout=5000)

        grid = page.query_selector("#manual-fixture-grid")
        assert "Load the Setup tab first" not in grid.inner_text(), (
            "Manual tab shows placeholder instead of fixtures — "
            "setupLoad() must complete before manualRender() is called"
        )

    def test_manual_tab_has_channel_sliders(self, page: Page):
        page.click('[data-tab="manual"]')
        page.wait_for_selector("#manual-fixture-grid input[type=range]", timeout=5000)
        sliders = page.query_selector_all("#manual-fixture-grid input[type=range]")
        assert len(sliders) > 0, "Expected channel sliders in fixture cards"
