import Foundation

extension AppState {
    /// Scan the project's debug/ folder and reconstruct one ProcessingJob per processed
    /// image.  Each job's state and extracted photos are inferred from which step output
    /// files are present on disk — no hardcoded list of test images.
    ///
    /// The debug folder is flat: all files live directly inside it with names like
    ///   `{baseName}_{stepSuffix}.jpg`
    /// e.g.  `IMG_cave_normal_14_photo_01_enhanced.jpg`
    static func withMockData() -> AppState {
        // Skip the automatic debug-folder scan — we'll populate jobs manually below.
        let state = AppState(loadDebugJobs: false)

        // Use the dev project root's debug/ folder when running from Xcode.
        // Falls back to AppSettings.debugFolder (the user-configured path) otherwise.
        let debugDir: URL = {
            if let root = RuntimeManager.devProjectRoot {
                return root.appendingPathComponent("debug")
            }
            return AppSettings.shared.debugFolder
        }()

        let testImagesDir = RuntimeManager.devProjectRoot?
            .appendingPathComponent("test-images")

        let fm = FileManager.default
        guard let allFiles = try? fm.contentsOfDirectory(atPath: debugDir.path) else {
            return state
        }

        // ── Discover jobs ────────────────────────────────────────────────────────
        // A job exists if its _01_loaded.jpg file is present.
        let baseNames: [String] = allFiles
            .compactMap { name in
                guard name.hasSuffix("_01_loaded.jpg") else { return nil }
                return String(name.dropLast("_01_loaded.jpg".count))
            }
            .sorted()

        for baseName in baseNames {
            // ── Find original input file (best-effort; used for "before" thumbnail) ──
            var inputURL: URL? = nil
            var inputName = baseName + ".HEIC"
            if let testDir = testImagesDir {
                for ext in ["HEIC", "heic", "DNG", "dng", "JPG", "jpg", "JPEG", "jpeg"] {
                    let candidate = testDir.appendingPathComponent("\(baseName).\(ext)")
                    if fm.fileExists(atPath: candidate.path) {
                        inputURL = candidate
                        inputName = "\(baseName).\(ext)"
                        break
                    }
                }
            }

            // ── Determine job step by checking which output files exist ────────────
            func exists(_ suffix: String) -> Bool {
                fm.fileExists(atPath: debugDir
                    .appendingPathComponent("\(baseName)_\(suffix)").path)
            }

            // Count extracted photos by scanning for per-photo enhanced files.
            var photoCount = 0
            while exists("14_photo_\(String(format: "%02d", photoCount + 1))_enhanced.jpg") {
                photoCount += 1
            }

            let isDone      = photoCount > 0
            let hasColor    = exists("13_photo_01_restored.jpg")
            let hasGlare    = exists("07_photo_01_deglared.jpg")
            let hasOrient   = exists("05b_photo_01_oriented.jpg")
            let hasSplit    = exists("04_photo_boundaries.jpg")

            let jobState:    JobState
            let currentStep: PipelineStep
            let stepStatus:  StepStatus

            if isDone {
                jobState = .complete; currentStep = .done;            stepStatus = .complete
            } else if hasColor {
                jobState = .running;  currentStep = .colorCorrection; stepStatus = .awaitingReview
            } else if hasGlare {
                jobState = .running;  currentStep = .glareRemoval;    stepStatus = .awaitingReview
            } else if hasOrient {
                jobState = .running;  currentStep = .orientation;     stepStatus = .awaitingReview
            } else if hasSplit {
                jobState = .running;  currentStep = .photoSplit;      stepStatus = .awaitingReview
            } else {
                jobState = .running;  currentStep = .pageDetect;      stepStatus = .awaitingReview
            }

            let job = ProcessingJob(
                inputName:   inputName,
                inputURL:    inputURL,
                state:       jobState,
                currentStep: currentStep,
                stepStatus:  stepStatus
            )

            // ── Attach extracted photos ──────────────────────────────────────────
            // Photos are available once glare removal (or any later step) has run.
            if isDone || hasGlare || hasOrient {
                let count = max(photoCount, 1)
                for i in 1...count {
                    let idx = String(format: "%02d", i)
                    // Use the best available per-photo image for the current step.
                    let imageSuffix: String
                    if isDone        { imageSuffix = "14_photo_\(idx)_enhanced.jpg" }
                    else if hasGlare { imageSuffix = "07_photo_\(idx)_deglared.jpg" }
                    else             { imageSuffix = "05b_photo_\(idx)_oriented.jpg" }

                    let imageURL = debugDir.appendingPathComponent("\(baseName)_\(imageSuffix)")
                    guard fm.fileExists(atPath: imageURL.path) else { continue }

                    job.extractedPhotos.append(ExtractedPhoto(
                        imageURL:      imageURL,
                        jobInputURL:   debugDir.appendingPathComponent("\(baseName)_01_loaded.jpg"),
                        jobInputName:  inputName,
                        jobID:         job.id,
                        photoIndex:    i
                    ))
                }
            }

            state.jobs.append(job)
        }

        return state
    }
}
