import Foundation

/// Parses a single stdout line from the Python CLI into a typed `PipelineEvent`.
///
/// Log format: `HH:MM:SS - <module> - <LEVEL> - <message>`
///
/// All public methods are static and side-effect free, making this easy to unit test.
struct CLIOutputParser {

    // MARK: - Public API

    /// Parse one raw stdout line into a `PipelineEvent`.
    static func parse(line: String) -> PipelineEvent {
        let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return .unknown(raw: line) }

        // Split off the log prefix: "HH:MM:SS - module - LEVEL - message"
        // We need at least 4 components separated by " - "
        let parts = trimmed.components(separatedBy: " - ")
        guard parts.count >= 4 else {
            // Some multi-line summaries are indented continuation lines — treat as unknown
            return .unknown(raw: line)
        }

        let level = parts[2].trimmingCharacters(in: .whitespaces)
        // Message is everything from the 4th component onward (handles " - " in messages)
        let message = parts[3...].joined(separator: " - ").trimmingCharacters(in: .whitespaces)

        if level == "ERROR" {
            return .errorLine(message: message)
        }

        guard level == "INFO" else {
            return .unknown(raw: line)
        }

        return parseInfoMessage(message)
    }

    // MARK: - Private helpers

    private static func parseInfoMessage(_ message: String) -> PipelineEvent {
        // "Processing: /path/to/file.HEIC"
        if message.hasPrefix("Processing: ") {
            return .jobStarted
        }

        // "load: 0.234s"
        if message.hasPrefix("load:") {
            return .stepCompleted(name: "Load")
        }

        // "normalize: 0.123s"
        if message.hasPrefix("normalize:") {
            return .stepCompleted(name: "Normalize")
        }

        // "page_detect: 1.234s"
        if message.hasPrefix("page_detect:") {
            return .stepCompleted(name: "Page Detection")
        }

        // "photo_split: 0.678s, 3 photo(s)"
        if message.hasPrefix("photo_split:") {
            return .stepCompleted(name: "Photo Detection")
        }

        // "ai_orient: 2.345s"
        if message.hasPrefix("ai_orient:") {
            return .stepCompleted(name: "AI Orientation")
        }

        // "glare: 5.678s"
        if message.hasPrefix("glare:") {
            return .stepCompleted(name: "Glare Removal")
        }

        // "geometry: 0.089s"
        if message.hasPrefix("geometry:") {
            return .stepCompleted(name: "Geometry")
        }

        // "color_restore: 0.345s"
        if message.hasPrefix("color_restore:") {
            return .stepCompleted(name: "Color Restoration")
        }

        // "Total processing time: 18.234s"
        if message.hasPrefix("Total processing time:") {
            let seconds = extractSeconds(from: message)
            return .processingComplete(totalTime: seconds ?? 0)
        }

        // "Saved: SundayAlbum_cave_normal.jpg"
        if message.hasPrefix("Saved: ") {
            let filename = String(message.dropFirst("Saved: ".count))
            return .outputSaved(filename: filename)
        }

        // "  Photos extracted: 3" (inside the Processing Summary block)
        let stripped = message.trimmingCharacters(in: .whitespaces)
        if stripped.hasPrefix("Photos extracted:") {
            let rest = stripped.dropFirst("Photos extracted:".count).trimmingCharacters(in: .whitespaces)
            if let count = Int(rest) {
                return .photosExtracted(count: count)
            }
        }

        return .unknown(raw: message)
    }

    /// Extract the numeric seconds value from a string like "Load time: 1.234s" or "Total processing time: 18.234s"
    private static func extractSeconds(from message: String) -> Double? {
        // Find the last run of digits/dots followed by optional 's'
        let pattern = #"(\d+\.\d+)s"#
        if let range = message.range(of: pattern, options: .regularExpression) {
            let match = String(message[range]).replacingOccurrences(of: "s", with: "")
            return Double(match)
        }
        return nil
    }
}
