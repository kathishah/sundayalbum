import Foundation

/// Typed events parsed from the Python CLI's stdout.
enum PipelineEvent: Equatable {
    /// CLI started processing a file (first INFO line).
    case jobStarted

    /// A timed pipeline step completed. `name` matches the step label in the log line.
    case stepCompleted(name: String)

    /// Number of individual photos found on the page.
    case photosExtracted(count: Int)

    /// The CLI saved an output file. `filename` is the bare filename, e.g. "SundayAlbum_cave_normal.jpg".
    case outputSaved(filename: String)

    /// All steps finished. `totalTime` is seconds.
    case processingComplete(totalTime: Double)

    /// An ERROR-level log line. `message` is the part after "ERROR - ".
    case errorLine(message: String)

    /// Any line that didn't match a known pattern.
    case unknown(raw: String)
}
