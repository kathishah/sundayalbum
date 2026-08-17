import Testing
@testable import SundayAlbum

/// Tests for CLIOutputParser using lines captured from real CLI runs.
struct CLIOutputParserTests {

    // MARK: - jobStarted

    @Test func parsesProcessingLine() {
        let line = "14:23:01 - src.pipeline - INFO - Processing: /Users/dev/dev/sundayalbum/test-images/IMG_cave_normal.HEIC"
        #expect(CLIOutputParser.parse(line: line) == .jobStarted)
    }

    // MARK: - stepCompleted

    @Test func parsesLoadTime() {
        let line = "14:23:02 - src.pipeline - INFO - load: 0.234s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Load"))
    }

    @Test func parsesNormalizeTime() {
        let line = "14:23:02 - src.pipeline - INFO - normalize: 0.123s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Normalize"))
    }

    @Test func parsesPageDetectionTime() {
        let line = "14:23:03 - src.pipeline - INFO - page_detect: 1.456s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Page Detection"))
    }

    @Test func parsesPhotoSplitTime() {
        let line = "14:23:04 - src.pipeline - INFO - photo_split: 0.678s, 3 photo(s)"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Photo Detection"))
    }

    @Test func parsesAIOrientationTime() {
        let line = "14:23:06 - src.pipeline - INFO - ai_orient: 2.345s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "AI Orientation"))
    }

    @Test func parsesGlareRemovalTime() {
        let line = "14:23:12 - src.pipeline - INFO - glare: 5.678s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Glare Removal"))
    }

    @Test func parsesGeometryCorrectionTime() {
        let line = "14:23:12 - src.pipeline - INFO - geometry: 0.089s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Geometry"))
    }

    @Test func parsesColorRestorationTime() {
        let line = "14:23:13 - src.pipeline - INFO - color_restore: 0.345s"
        #expect(CLIOutputParser.parse(line: line) == .stepCompleted(name: "Color Restoration"))
    }

    // MARK: - processingComplete

    @Test func parsesTotalProcessingTime() {
        let line = "14:23:14 - src.pipeline - INFO - Total processing time: 18.234s"
        guard case .processingComplete(let t) = CLIOutputParser.parse(line: line) else {
            Issue.record("Expected processingComplete")
            return
        }
        #expect(abs(t - 18.234) < 0.001)
    }

    // MARK: - outputSaved

    @Test func parsesSavedLine() {
        let line = "14:23:14 - src.cli - INFO - Saved: SundayAlbum_IMG_cave_normal.jpg"
        #expect(CLIOutputParser.parse(line: line) == .outputSaved(filename: "SundayAlbum_IMG_cave_normal.jpg"))
    }

    @Test func parsesSavedLineMultiPhoto() {
        let line = "14:23:14 - src.cli - INFO - Saved: SundayAlbum_IMG_three_pics_normal_Photo02.jpg"
        #expect(CLIOutputParser.parse(line: line) == .outputSaved(filename: "SundayAlbum_IMG_three_pics_normal_Photo02.jpg"))
    }

    // MARK: - photosExtracted

    @Test func parsesPhotosExtracted() {
        // This line appears inside the multi-line Processing Summary block
        let line = "14:23:14 - src.cli - INFO -   Photos extracted: 3"
        #expect(CLIOutputParser.parse(line: line) == .photosExtracted(count: 3))
    }

    // MARK: - errorLine

    @Test func parsesErrorLine() {
        let line = "14:23:14 - src.pipeline - ERROR - Failed to load image: file not found"
        #expect(CLIOutputParser.parse(line: line) == .errorLine(message: "Failed to load image: file not found"))
    }

    // MARK: - unknown / edge cases

    @Test func parsesUnknownLine() {
        let line = "14:23:14 - src.cli - INFO - ============================================================"
        guard case .unknown = CLIOutputParser.parse(line: line) else {
            Issue.record("Expected unknown for separator line")
            return
        }
    }

    @Test func handlesEmptyLine() {
        guard case .unknown = CLIOutputParser.parse(line: "") else {
            Issue.record("Expected unknown for empty line")
            return
        }
    }

    @Test func handlesMalformedLine() {
        let line = "not a valid log line at all"
        guard case .unknown = CLIOutputParser.parse(line: line) else {
            Issue.record("Expected unknown for malformed line")
            return
        }
    }

    @Test func handlesWARNINGLevel() {
        let line = "14:23:14 - src.pipeline - WARNING - Glare detection found 0 regions"
        guard case .unknown = CLIOutputParser.parse(line: line) else {
            Issue.record("Expected unknown for WARNING-level line")
            return
        }
    }
}
