import Testing
@testable import SundayAlbum

// MARK: - PipelineRunner argument-building tests
//
// These tests exercise the static `_*Args` methods on PipelineRunner so that
// regressions in CLI flag names or step lists are caught immediately without
// needing to launch a subprocess.  The methods are `nonisolated static`, so
// no main-actor hop is required.

struct PipelineRunnerArgsTests {

    // MARK: - Color restoration

    @Test func colorArgsContainCorrectSteps() {
        let args = PipelineRunner._colorArgs(vibranceBoost: 0.25, sharpenAmount: 0.5)
        let steps = stepsValue(in: args)
        #expect(steps != nil)
        #expect(steps!.contains("color_restore"))
        #expect(steps!.contains("white_balance"))
        #expect(steps!.contains("deyellow"))
        #expect(steps!.contains("sharpen"))
    }

    @Test func colorArgsDoNotContainPreSplitSteps() {
        let args = PipelineRunner._colorArgs(vibranceBoost: 0.25, sharpenAmount: 0.5)
        let steps = stepsValue(in: args)!
        // Reprocessing color must not re-run photo detection
        #expect(!steps.contains("photo_detect"))
        #expect(!steps.contains("photo_split"))
        #expect(!steps.contains("ai_orientation"))
    }

    @Test func colorArgsContainVibranceFlag() {
        let args = PipelineRunner._colorArgs(vibranceBoost: 0.4, sharpenAmount: 0.8)
        #expect(args.contains("--color-vibrance"))
        // Regression guard: the old (wrong) key name must never appear
        #expect(!args.contains("--saturation-boost"))
        #expect(!args.contains("saturation_boost"))
    }

    @Test func colorArgsContainSharpenFlag() {
        let args = PipelineRunner._colorArgs(vibranceBoost: 0.4, sharpenAmount: 0.8)
        #expect(args.contains("--sharpen-amount"))
    }

    @Test func colorArgsFormatVibranceToThreeDecimals() {
        let args = PipelineRunner._colorArgs(vibranceBoost: 0.4, sharpenAmount: 0.5)
        let idx = args.firstIndex(of: "--color-vibrance")
        guard let i = idx else { Issue.record("--color-vibrance flag missing"); return }
        #expect(args[i + 1] == "0.400")
    }

    @Test func colorArgsFormatSharpenToThreeDecimals() {
        let args = PipelineRunner._colorArgs(vibranceBoost: 0.25, sharpenAmount: 0.8)
        let idx = args.firstIndex(of: "--sharpen-amount")
        guard let i = idx else { Issue.record("--sharpen-amount flag missing"); return }
        #expect(args[i + 1] == "0.800")
    }

    // MARK: - Glare removal

    @Test func glareArgsContainCorrectSteps() {
        let args = PipelineRunner._glareArgs(sceneDescription: "")
        let steps = stepsValue(in: args)
        #expect(steps != nil)
        #expect(steps!.contains("glare_detect"))
        #expect(steps!.contains("color_restore"))
        #expect(steps!.contains("sharpen"))
    }

    @Test func glareArgsOmitSceneDescWhenEmpty() {
        let args = PipelineRunner._glareArgs(sceneDescription: "")
        #expect(!args.contains("--scene-desc"))
    }

    @Test func glareArgsIncludeSceneDescWhenProvided() {
        let args = PipelineRunner._glareArgs(sceneDescription: "A cave interior")
        #expect(args.contains("--scene-desc"))
        let idx = args.firstIndex(of: "--scene-desc")!
        #expect(args[idx + 1] == "A cave interior")
    }

    // MARK: - Orientation

    @Test func orientationArgsContainCorrectSteps() {
        let args = PipelineRunner._orientationArgs(rotationDegrees: 0, sceneDescription: "")
        let steps = stepsValue(in: args)
        #expect(steps != nil)
        #expect(steps!.contains("ai_orientation"))
        #expect(steps!.contains("color_restore"))
        #expect(steps!.contains("sharpen"))
    }

    @Test func orientationArgsDoNotRerunPhotoDetect() {
        let args = PipelineRunner._orientationArgs(rotationDegrees: 90, sceneDescription: "")
        let steps = stepsValue(in: args)!
        #expect(!steps.contains("photo_detect"))
        #expect(!steps.contains("photo_split"))
    }

    @Test func orientationArgsOmitRotationFlagWhenZero() {
        let args = PipelineRunner._orientationArgs(rotationDegrees: 0, sceneDescription: "")
        #expect(!args.contains("--forced-rotation"))
    }

    @Test func orientationArgsIncludeRotationFlagWhenNonZero() {
        let args = PipelineRunner._orientationArgs(rotationDegrees: 90, sceneDescription: "")
        #expect(args.contains("--forced-rotation"))
        let idx = args.firstIndex(of: "--forced-rotation")!
        #expect(args[idx + 1] == "90")
    }

    @Test func orientationArgs270Degrees() {
        let args = PipelineRunner._orientationArgs(rotationDegrees: 270, sceneDescription: "")
        let idx = args.firstIndex(of: "--forced-rotation")!
        #expect(args[idx + 1] == "270")
    }

    // MARK: - Photo split

    @Test func photoSplitArgsContainPhotoSplitStep() {
        let args = PipelineRunner._photoSplitArgs()
        let steps = stepsValue(in: args)
        #expect(steps != nil)
        #expect(steps!.contains("photo_split"))
    }

    @Test func photoSplitArgsContainDownstreamSteps() {
        let args = PipelineRunner._photoSplitArgs()
        let steps = stepsValue(in: args)!
        #expect(steps.contains("ai_orientation"))
        #expect(steps.contains("glare_detect"))
        #expect(steps.contains("color_restore"))
        #expect(steps.contains("sharpen"))
    }

    // MARK: - Helpers

    /// Extract the value following `--steps` from an args array.
    private func stepsValue(in args: [String]) -> String? {
        guard let idx = args.firstIndex(of: "--steps"), idx + 1 < args.count else { return nil }
        return args[idx + 1]
    }
}
