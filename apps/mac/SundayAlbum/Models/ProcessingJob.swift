import Foundation
import Observation

enum JobState {
    case queued
    case running
    case complete
    case failed
}

@Observable
final class ProcessingJob: Identifiable {
    let id: UUID
    let inputName: String
    let inputURL: URL?
    var state: JobState
    var currentStep: PipelineStep
    var stepStatus: StepStatus
    var extractedPhotos: [ExtractedPhoto]
    var errorMessage: String?
    var processingTime: Double?
    /// Human-readable name of the step currently executing (set by PipelineRunner from CLI output).
    var currentStepName: String?
    /// Number of individual photos the CLI reported finding on the page.
    var photosExtractedCount: Int?

    /// All steps before the current one are considered complete
    var completedSteps: Set<PipelineStep> {
        Set(PipelineStep.allCases.filter { $0.rawValue < currentStep.rawValue })
    }

    /// 0..1 progress based on how far through the pipeline we are
    var progressFraction: Double {
        Double(currentStep.rawValue) / Double(PipelineStep.allCases.count - 1)
    }

    init(
        id: UUID = UUID(),
        inputName: String,
        inputURL: URL? = nil,
        state: JobState = .queued,
        currentStep: PipelineStep = .load,
        stepStatus: StepStatus = .pending,
        extractedPhotos: [ExtractedPhoto] = [],
        errorMessage: String? = nil,
        processingTime: Double? = nil,
        currentStepName: String? = nil,
        photosExtractedCount: Int? = nil
    ) {
        self.id = id
        self.inputName = inputName
        self.inputURL = inputURL
        self.state = state
        self.currentStep = currentStep
        self.stepStatus = stepStatus
        self.extractedPhotos = extractedPhotos
        self.errorMessage = errorMessage
        self.processingTime = processingTime
        self.currentStepName = currentStepName
        self.photosExtractedCount = photosExtractedCount
    }

    /// Advance to the next pipeline step (mock)
    func advance() {
        guard let next = currentStep.next else { return }
        currentStep = next
        if next == .done {
            state = .complete
            stepStatus = .complete
        } else if next.requiresReview {
            stepStatus = .awaitingReview
        } else {
            stepStatus = .running
            // Auto-advance non-review steps after a short delay in real app
        }
    }
}
