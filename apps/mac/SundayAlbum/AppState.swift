import Foundation
import Observation

enum AppScreen: Equatable {
    case library
    case stepDetail(jobID: UUID)
}

@MainActor
@Observable
final class AppState {
    var jobs: [ProcessingJob] = []
    var expandedJobID: UUID?      // single-click expand in library
    var currentScreen: AppScreen = .library

    /// Active PipelineRunners keyed by job ID.
    private var runners: [UUID: PipelineRunner] = [:]

    init(loadDebugJobs: Bool = true) {
        if loadDebugJobs {
            jobs = DebugFolderScanner.loadJobs()
            OverridesStore.apply(to: jobs)
        }
    }

    /// Rescan the debug folder and replace the library with fresh job data.
    /// Called when the debug folder setting changes or on explicit user request.
    func reloadJobs() {
        jobs = DebugFolderScanner.loadJobs()
        OverridesStore.apply(to: jobs)
        // Return to library view so stale job detail views don't linger.
        currentScreen = .library
    }

    /// Persist overrides for a photo after the user commits a change to
    /// `rotationOverride` or `sceneDescription`.
    func saveOverrides(for photo: ExtractedPhoto) {
        OverridesStore.update(for: photo)
    }

    var selectedJob: ProcessingJob? {
        if case .stepDetail(let id) = currentScreen {
            return jobs.first { $0.id == id }
        }
        return nil
    }

    func jobFor(id: UUID) -> ProcessingJob? {
        jobs.first { $0.id == id }
    }

    /// Call from views, wrapped in withAnimation if desired
    func navigate(to screen: AppScreen) {
        currentScreen = screen
        expandedJobID = nil
    }

    func navigateBack() {
        currentScreen = .library
    }

    /// Enqueues new files, skipping any whose inputURL is already in the library.
    /// Pass `startProcessing: false` in tests to suppress subprocess launch.
    func addFiles(_ urls: [URL], startProcessing: Bool = true) {
        let existingURLs = Set(jobs.compactMap(\.inputURL))
        let newJobs = urls
            .filter { !existingURLs.contains($0) }
            .map { ProcessingJob(inputName: $0.lastPathComponent, inputURL: $0) }
        jobs.append(contentsOf: newJobs)

        guard startProcessing else { return }

        guard AppSettings.shared.canProcess else {
            for job in newJobs {
                job.state = .failed
                job.errorMessage = "Anthropic API key required. Open Settings (⌘,) to add it."
            }
            return
        }

        for job in newJobs {
            let runner = PipelineRunner(job: job)
            runners[job.id] = runner
            runner.start()
        }
    }

    /// Cancels a running job and removes its runner.
    func cancel(jobID: UUID) {
        runners[jobID]?.cancel()
        runners.removeValue(forKey: jobID)
    }

    /// Cancels (if running) and removes a job from the library.
    func removeJob(id: UUID) {
        cancel(jobID: id)
        jobs.removeAll { $0.id == id }
    }
}
