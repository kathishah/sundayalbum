import Foundation

/// Scans the configured debug folder at app launch and reconstructs one `ProcessingJob`
/// per image that has been at least partially processed.
///
/// **Flat file layout** — all files live directly inside the debug folder:
///   `{baseName}_01_loaded.jpg`                    — input image loaded
///   `{baseName}_04_photo_boundaries.jpg`          — after photo split
///   `{baseName}_05b_photo_NN_oriented.jpg`        — after AI orientation (per photo)
///   `{baseName}_07_photo_NN_deglared.jpg`         — after glare removal (per photo)
///   `{baseName}_13_photo_NN_restored.jpg`         — after color correction (per photo)
///   `{baseName}_14_photo_NN_enhanced.jpg`         — final output (per photo)
///
/// A job exists for any baseName that has a `_01_loaded.jpg` file. Job state is inferred
/// from which step files are present on disk — no external metadata required.
///
/// The scan root is `AppSettings.shared.debugFolder`, which:
///   - Dev builds: defaults to `{devProjectRoot}/debug/`
///   - Prod builds: defaults to `~/Library/Application Support/SundayAlbum/debug/`
///   - Either: user-configurable in Settings → Storage.
struct DebugFolderScanner {

    // MARK: - Public

    /// Returns one `ProcessingJob` for each baseName that has a `_01_loaded.jpg` file,
    /// sorted alphabetically by baseName.
    @MainActor static func loadJobs() -> [ProcessingJob] {
        let debugDir = AppSettings.shared.debugFolder
        let fm = FileManager.default

        guard let allFiles = try? fm.contentsOfDirectory(atPath: debugDir.path) else {
            return []
        }

        // testImagesDir is used to locate original HEIC/DNG inputs for the "before" thumbnail.
        let testImagesDir = RuntimeManager.devProjectRoot?
            .appendingPathComponent("test-images")

        let allFileSet = Set(allFiles)

        let baseNames: [String] = allFiles
            .compactMap { name -> String? in
                guard name.hasSuffix("_01_loaded.jpg") else { return nil }
                return String(name.dropLast("_01_loaded.jpg".count))
            }
            .sorted()

        return baseNames.compactMap {
            jobFrom(
                baseName: $0,
                debugDir: debugDir,
                testImagesDir: testImagesDir,
                allFileSet: allFileSet,
                fm: fm
            )
        }
    }

    // MARK: - Private

    @MainActor private static func jobFrom(
        baseName: String,
        debugDir: URL,
        testImagesDir: URL?,
        allFileSet: Set<String>,
        fm: FileManager
    ) -> ProcessingJob? {
        // Helper: check whether a flat debug file exists.
        func exists(_ suffix: String) -> Bool {
            allFileSet.contains("\(baseName)_\(suffix)")
        }

        // ── Determine current step ──────────────────────────────────────────────
        // Count final per-photo outputs (1-based, sequential).
        var photoCount = 0
        while exists("14_photo_\(String(format: "%02d", photoCount + 1))_enhanced.jpg") {
            photoCount += 1
        }

        let isDone    = photoCount > 0
        let hasColor  = exists("13_photo_01_restored.jpg")
        let hasGlare  = exists("07_photo_01_deglared.jpg")
        let hasOrient = exists("05b_photo_01_oriented.jpg")
        let hasSplit  = exists("04_photo_boundaries.jpg")

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

        // ── Locate original input file (for "before" thumbnail) ────────────────
        var inputURL: URL? = nil
        var inputName = "\(baseName).HEIC"
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

        // Fall back to using the loaded debug image as the "input"
        let loadedURL = debugDir.appendingPathComponent("\(baseName)_01_loaded.jpg")
        let beforeURL: URL? = fm.fileExists(atPath: loadedURL.path) ? loadedURL : nil
        if inputURL == nil { inputURL = beforeURL }

        // ── Build job ──────────────────────────────────────────────────────────
        let job = ProcessingJob(
            inputName:   inputName,
            inputURL:    inputURL,
            state:       jobState,
            currentStep: currentStep,
            stepStatus:  stepStatus
        )

        // ── Attach extracted photos ────────────────────────────────────────────
        // Photos are visible once orientation, glare, or final step output is present.
        if isDone || hasGlare || hasOrient {
            let count = max(photoCount, 1)
            for i in 1...count {
                let idx = String(format: "%02d", i)
                let imageSuffix: String
                if isDone        { imageSuffix = "14_photo_\(idx)_enhanced.jpg" }
                else if hasGlare { imageSuffix = "07_photo_\(idx)_deglared.jpg" }
                else             { imageSuffix = "05b_photo_\(idx)_oriented.jpg" }

                let imageURL = debugDir.appendingPathComponent("\(baseName)_\(imageSuffix)")
                guard fm.fileExists(atPath: imageURL.path) else { continue }

                job.extractedPhotos.append(ExtractedPhoto(
                    imageURL:     imageURL,
                    jobInputURL:  beforeURL,
                    jobInputName: inputName,
                    jobID:        job.id,
                    photoIndex:   i
                ))
            }
        }

        return job
    }
}
