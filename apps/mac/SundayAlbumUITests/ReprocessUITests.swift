import XCTest

// MARK: - Reprocess step-view UI tests
//
// These tests use the MOCK_DATA + UITEST_MODE launch flags so:
//   • The library is pre-populated with four jobs — no real processing needed.
//   • Clicking "Apply & Reprocess" or "Re-run Glare Removal" transitions
//     job.state to .running WITHOUT launching a Python subprocess.
//
// The completed mock job is "IMG_cave_normal.HEIC".  Its step detail opens
// straight to Color Correction (StepDetailView.startSelection returns
// .photo(index:0, step:.colorCorrection) when currentStep == .done).
//
// Tree-row labels use PipelineStep.title (short form):
//   "Orient"  — orientation step
//   "Glare"   — glare removal step
//   "Color"   — color correction step
//
// Accessibility identifiers used (set in each step view):
//   • job-card-<inputName>          AlbumPageCard
//   • tree-row-<label>              StepDetailView TreeRow  (label = step.title)
//   • slider-saturation             InlineSlider inside ColorCorrectionStepView
//   • btn-reprocess-color           ColorCorrectionStepView "Apply & Reprocess"
//   • btn-rerun-glare               GlareRemovalStepView "Re-run Glare Removal"
//   • btn-discard-glare             GlareRemovalStepView "Discard"
//   • field-scene-desc-glare        GlareRemovalStepView scene description field
//   • btn-reprocess-orientation     OrientationStepView "Apply & Reprocess"
//   • btn-rotation-90               RotationPicker "90°" button
//   • field-scene-desc-orientation  OrientationStepView scene description field

final class ReprocessUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication.launchForUITests()
        // Navigate into the completed cave job
        XCTAssertTrue(app.openJob(inputName: "IMG_cave_normal.HEIC"),
                      "Cave job card should be visible in the mock library")
    }

    override func tearDownWithError() throws {
        app.terminate()
    }

    // ── T-mac-01: Color Correction reprocess controls ─────────────────────────

    func testColorCorrectionSliderExists() throws {
        // Step detail opens on Color Correction for a complete job
        let slider = app.sliders["slider-saturation"]
        assertExists(slider, "Saturation slider should be visible in Color Correction view")
    }

    func testColorCorrectionReprocessButtonHiddenByDefault() throws {
        // "Apply & Reprocess" is only shown when isDirty — sliders are at defaults
        let btn = app.buttons["btn-reprocess-color"]
        // Should NOT exist yet (isDirty == false)
        XCTAssertFalse(btn.waitForExistence(timeout: 2),
                       "Reprocess button should be hidden while sliders are at defaults")
    }

    func testColorCorrectionReprocessButtonAppearsAfterSliderMove() throws {
        let slider = app.sliders["slider-saturation"]
        assertExists(slider)
        // Move slider away from default to make isDirty = true
        slider.adjust(toNormalizedSliderPosition: 0.8)

        let btn = app.buttons["btn-reprocess-color"]
        assertExists(btn, timeout: 3, "Reprocess button should appear after slider is moved")
    }

    func testColorCorrectionReprocessButtonTriggersProcessing() throws {
        let slider = app.sliders["slider-saturation"]
        assertExists(slider)
        slider.adjust(toNormalizedSliderPosition: 0.8)

        let btn = app.buttons["btn-reprocess-color"]
        assertExists(btn, timeout: 3)
        btn.click()

        // In UITEST_MODE the job transitions to .running immediately.
        // The button hides (isProcessing = true suppresses the isDirty panel).
        let progressIndicator = app.progressIndicators.firstMatch
        XCTAssertTrue(
            progressIndicator.waitForExistence(timeout: 3) || !btn.exists,
            "Clicking Reprocess should start processing (progress shown or button gone)"
        )
    }

    // ── T-mac-02: Glare Removal controls ──────────────────────────────────────
    // Tree-row label for glare removal is "Glare" (PipelineStep.glareRemoval.title)

    func testGlareRemovalActionRowExists() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Glare"),
                      "Glare Removal row should be accessible for the complete cave job")

        assertExists(app.buttons["btn-rerun-glare"],
                     "Re-run Glare Removal button should always be visible")
        assertExists(app.buttons["btn-discard-glare"],
                     "Discard button should always be visible")
    }

    func testGlareSceneDescFieldExists() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Glare"))
        assertExists(app.textFields["field-scene-desc-glare"],
                     "Scene description text field should be visible")
    }

    func testGlareRerunButtonTriggersProcessing() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Glare"))
        let btn = app.buttons["btn-rerun-glare"]
        assertExists(btn)
        btn.click()

        let progressIndicator = app.progressIndicators.firstMatch
        XCTAssertTrue(
            progressIndicator.waitForExistence(timeout: 3) || !btn.isEnabled,
            "Clicking Re-run Glare Removal should start processing"
        )
    }

    // ── T-mac-03: Orientation controls ────────────────────────────────────────
    // Tree-row label for orientation is "Orient" (PipelineStep.orientation.title)

    func testOrientationRotationPickerExists() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Orient"),
                      "Orient row should be accessible for the complete cave job")

        // All four rotation options should be visible
        for degrees in [0, 90, 180, 270] {
            assertExists(app.buttons["btn-rotation-\(degrees)"],
                         "Rotation button \(degrees)° should exist")
        }
    }

    func testOrientationSceneDescFieldExists() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Orient"))
        assertExists(app.textFields["field-scene-desc-orientation"],
                     "Scene description field should be visible in Orientation view")
    }

    func testOrientationReprocessButtonHiddenByDefault() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Orient"))
        // isDirty is false until user picks a non-zero rotation
        let btn = app.buttons["btn-reprocess-orientation"]
        XCTAssertFalse(btn.waitForExistence(timeout: 2),
                       "Reprocess button should be hidden when rotation is 0°")
    }

    func testOrientationReprocessButtonAppearsAfterRotationPick() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Orient"))
        app.buttons["btn-rotation-90"].click()

        let btn = app.buttons["btn-reprocess-orientation"]
        assertExists(btn, timeout: 3,
                     "Reprocess button should appear after selecting a non-zero rotation")
    }

    func testOrientationReprocessButtonTriggersProcessing() throws {
        XCTAssertTrue(app.selectTreeRow(label: "Orient"))
        app.buttons["btn-rotation-90"].click()

        let btn = app.buttons["btn-reprocess-orientation"]
        assertExists(btn, timeout: 3)
        btn.click()

        let progressIndicator = app.progressIndicators.firstMatch
        XCTAssertTrue(
            progressIndicator.waitForExistence(timeout: 3) || !btn.exists,
            "Clicking Apply & Reprocess should start processing"
        )
    }
}
