import Foundation

/// Launches the Python CLI pipeline as a subprocess and streams stdout line-by-line.
///
/// One `PipelineRunner` per input file. Not reusable — create a new instance for each job.
///
/// All `@MainActor` updates ensure `@Observable` model mutations happen on the main thread,
/// which is required for SwiftUI observation to work correctly.
///
/// Python path resolution is delegated to `RuntimeManager`:
/// - **Dev** (Xcode): `.venv/` found by walking up from the bundle; CWD = project root.
/// - **Production**: `~/Library/AS/SundayAlbum/venv/bin/python`; CWD = `Contents/Resources/`
///   with `PYTHONPATH` injected so `src.*` imports resolve against the bundled package.
@MainActor
final class PipelineRunner {

    private let job: ProcessingJob
    private var process: Process?
    private let outputDir: URL

    // MARK: - Init

    init(job: ProcessingJob) {
        self.job = job
        // Per-job output directory inside the user-configured output folder.
        outputDir = AppSettings.shared.outputFolder.appendingPathComponent(job.id.uuidString)
        try? FileManager.default.createDirectory(at: outputDir, withIntermediateDirectories: true)
    }

    // MARK: - Public API

    /// Start the pipeline subprocess. Updates `job` state as stdout lines arrive.
    func start() {
        guard let inputURL = job.inputURL else {
            job.state = .failed
            job.errorMessage = "No input file URL"
            return
        }

        let runtime = RuntimeManager.shared

        guard let pythonURL = runtime.pythonURL else {
            job.state = .failed
            job.errorMessage = "Python runtime not ready. Complete setup first (launch the app and follow the setup screen)."
            return
        }

        let proc = Process()
        proc.executableURL = pythonURL
        var args = ["-m", "src.cli", "process", inputURL.path, "--output", outputDir.path]

        let s = AppSettings.shared
        if s.useOpenCVFallback { args.append("--no-openai-glare") }
        if s.debugOutputEnabled {
            args += ["--debug", "--debug-dir", s.debugFolder.path]
            try? FileManager.default.createDirectory(at: s.debugFolder, withIntermediateDirectories: true)
        }

        proc.arguments = args
        proc.currentDirectoryURL = runtime.cliWorkingDirectory

        // Build environment: inherit process env + secrets.json/SettingsStorage keys + PYTHONUNBUFFERED.
        let secrets = SecretsLoader(projectRoot: runtime.cliWorkingDirectory)
        var env = secrets.environment()

        // Production only: inject PYTHONPATH so `import src.*` resolves against the bundled package.
        if let extraPath = runtime.extraPythonPath {
            let existing = env["PYTHONPATH"] ?? ""
            env["PYTHONPATH"] = existing.isEmpty ? extraPath : "\(extraPath):\(existing)"
        }

        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe   // merge stderr so we catch Python tracebacks too

        // Stream lines as they arrive. The handler fires on a background thread — dispatch
        // all model mutations to @MainActor via Task.
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            let lines = text.components(separatedBy: "\n")
            Task { @MainActor [weak self] in
                self?.handle(lines: lines)
            }
        }

        proc.terminationHandler = { [weak proc] _ in
            let status = proc?.terminationStatus ?? -1
            Task { @MainActor [weak self] in
                self?.handleTermination(exitCode: Int(status))
            }
        }

        self.process = proc
        job.state = .running

        do {
            try proc.run()
        } catch {
            job.state = .failed
            job.errorMessage = "Failed to launch Python: \(error.localizedDescription)"
        }
    }

    /// Terminate a running job.
    func cancel() {
        process?.terminate()
        job.state = .failed
        job.errorMessage = "Cancelled"
    }

    /// Restart the pipeline from the photo_split step onward.
    ///
    /// Assumes ``_05_photo_detections.json`` has already been written to the
    /// debug folder by the caller (e.g. ``PhotoSplitStepView``).  Builds a CLI
    /// invocation with ``--steps photo_split,...`` so that load, normalize,
    /// page_detect, and photo_detect are all skipped.
    func reprocessFromPhotoSplit() {
        job.extractedPhotos = []
        _launchReprocess(extraArgs: PipelineRunner._photoSplitArgs(), startingStep: .photoSplit)
    }

    /// Restart from AI orientation onward, applying an optional rotation override
    /// and/or scene description for the glare removal prompt.
    func reprocessFromOrientation(rotationDegrees: Int, sceneDescription: String) {
        _launchReprocess(
            extraArgs: PipelineRunner._orientationArgs(rotationDegrees: rotationDegrees, sceneDescription: sceneDescription),
            startingStep: .orientation
        )
    }

    /// Restart from glare removal onward, using an optional scene description
    /// override for the OpenAI prompt.
    func reprocessFromGlare(sceneDescription: String) {
        _launchReprocess(
            extraArgs: PipelineRunner._glareArgs(sceneDescription: sceneDescription),
            startingStep: .glareRemoval
        )
    }

    /// Restart from color restoration onward with custom vibrance and sharpness values.
    func reprocessFromColor(vibranceBoost: Double, sharpenAmount: Double) {
        _launchReprocess(
            extraArgs: PipelineRunner._colorArgs(vibranceBoost: vibranceBoost, sharpenAmount: sharpenAmount),
            startingStep: .colorCorrection
        )
    }

    // MARK: - Testable arg builders
    // `nonisolated` so unit tests can call them synchronously without @MainActor.

    nonisolated static func _photoSplitArgs() -> [String] {
        let steps = ["photo_split", "ai_orientation", "glare_detect",
                     "keystone_correct", "dewarp", "rotation_correct",
                     "white_balance", "color_restore", "deyellow", "sharpen"].joined(separator: ",")
        return ["--steps", steps]
    }

    nonisolated static func _orientationArgs(rotationDegrees: Int, sceneDescription: String) -> [String] {
        let steps = ["ai_orientation", "glare_detect", "keystone_correct",
                     "dewarp", "rotation_correct", "white_balance",
                     "color_restore", "deyellow", "sharpen"].joined(separator: ",")
        var args = ["--steps", steps]
        if rotationDegrees != 0 { args += ["--forced-rotation", "\(rotationDegrees)"] }
        if !sceneDescription.isEmpty { args += ["--scene-desc", sceneDescription] }
        return args
    }

    nonisolated static func _glareArgs(sceneDescription: String) -> [String] {
        let steps = ["glare_detect", "keystone_correct", "dewarp",
                     "rotation_correct", "white_balance", "color_restore",
                     "deyellow", "sharpen"].joined(separator: ",")
        var args = ["--steps", steps]
        if !sceneDescription.isEmpty { args += ["--scene-desc", sceneDescription] }
        return args
    }

    nonisolated static func _colorArgs(vibranceBoost: Double, sharpenAmount: Double) -> [String] {
        ["--steps", "white_balance,color_restore,deyellow,sharpen",
         "--color-vibrance", String(format: "%.3f", vibranceBoost),
         "--sharpen-amount", String(format: "%.3f", sharpenAmount)]
    }

    // MARK: - Private

    /// Shared subprocess launcher for all reprocess entry points.
    ///
    /// Builds a `python -m src.cli process <input> --output <dir> [extraArgs]`
    /// invocation, wires stdout/stderr to the line handler, and starts the process.
    private func _launchReprocess(extraArgs: [String], startingStep: PipelineStep) {
        // In UI-test mode skip the actual subprocess so tests run without Python.
        // The job transitions to .running; tests can assert on that state change.
        #if DEBUG
        if ProcessInfo.processInfo.environment["UITEST_MODE"] == "1" {
            job.state = .running
            job.currentStep = startingStep
            job.stepStatus = .running
            return
        }
        #endif

        guard let inputURL = job.inputURL else {
            job.state = .failed
            job.errorMessage = "No input file URL"
            return
        }

        let runtime = RuntimeManager.shared
        guard let pythonURL = runtime.pythonURL else {
            job.state = .failed
            job.errorMessage = "Python runtime not ready."
            return
        }

        var args = ["-m", "src.cli", "process", inputURL.path, "--output", outputDir.path]
        args += extraArgs

        let s = AppSettings.shared
        if s.useOpenCVFallback { args.append("--no-openai-glare") }
        if s.debugOutputEnabled {
            args += ["--debug", "--debug-dir", s.debugFolder.path]
        }

        let proc = Process()
        proc.executableURL = pythonURL
        proc.arguments = args
        proc.currentDirectoryURL = runtime.cliWorkingDirectory

        let secrets = SecretsLoader(projectRoot: runtime.cliWorkingDirectory)
        var env = secrets.environment()
        if let extraPath = runtime.extraPythonPath {
            let existing = env["PYTHONPATH"] ?? ""
            env["PYTHONPATH"] = existing.isEmpty ? extraPath : "\(extraPath):\(existing)"
        }
        proc.environment = env

        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            let lines = text.components(separatedBy: "\n")
            Task { @MainActor [weak self] in
                self?.handle(lines: lines)
            }
        }

        proc.terminationHandler = { [weak proc] _ in
            let status = proc?.terminationStatus ?? -1
            Task { @MainActor [weak self] in
                self?.handleTermination(exitCode: Int(status))
            }
        }

        self.process = proc
        job.state = .running
        job.currentStep = startingStep
        job.stepStatus = .running

        do {
            try proc.run()
        } catch {
            job.state = .failed
            job.errorMessage = "Failed to launch Python: \(error.localizedDescription)"
        }
    }

    private func handle(lines: [String]) {
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }

            // Always print to Xcode console for debugging
            print("[Pipeline] \(trimmed)")

            let event = CLIOutputParser.parse(line: trimmed)
            apply(event: event)
        }
    }

    private func apply(event: PipelineEvent) {
        switch event {
        case .jobStarted:
            job.state = .running

        case .stepCompleted(let name):
            job.currentStepName = name
            // Advance the UI progress wheel by mapping CLI step name → PipelineStep
            switch name {
            case "Load", "Normalize":
                job.currentStep = .load
            case "Page Detection":
                job.currentStep = .pageDetect
            case "Photo Detection":
                job.currentStep = .photoSplit
            case "AI Orientation":
                job.currentStep = .orientation
            case "Glare Removal":
                job.currentStep = .glareRemoval
            case "Geometry", "Color Restoration":
                job.currentStep = .colorCorrection
            default:
                break
            }

        case .photosExtracted(let count):
            job.photosExtractedCount = count

        case .outputSaved(let filename):
            let photoURL = outputDir.appendingPathComponent(filename)
            let photo = ExtractedPhoto(
                imageURL: photoURL,
                jobInputURL: job.inputURL,
                jobInputName: job.inputName,
                jobID: job.id
            )
            job.extractedPhotos.append(photo)

        case .processingComplete(let totalTime):
            job.processingTime = totalTime
            job.state = .complete
            job.currentStep = .done
            job.stepStatus = .complete

        case .errorLine(let message):
            job.errorMessage = message

        case .unknown:
            break
        }
    }

    private func handleTermination(exitCode: Int) {
        pipe_fileHandleForReading_cleanup()
        if exitCode != 0 && job.state != .complete {
            job.state = .failed
            if job.errorMessage == nil {
                job.errorMessage = "Process exited with code \(exitCode)"
            }
        }
    }

    private func pipe_fileHandleForReading_cleanup() {
        // Remove the readability handler to avoid retain cycles after termination
        if let pipe = process?.standardOutput as? Pipe {
            pipe.fileHandleForReading.readabilityHandler = nil
        }
    }
}
