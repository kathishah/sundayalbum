import SwiftUI
import AppKit

// MARK: - Selection model

/// What the user is currently viewing in the step detail canvas.
enum StepSelection: Equatable, Hashable {
    /// Job-level pre-split steps (Load, Page Detect, Photo Split)
    case preSplit(PipelineStep)
    /// Per-photo post-split steps (Orient, Glare, Color, Done) for a given 0-based photo index
    case photo(index: Int, step: PipelineStep)

    var pipelineStep: PipelineStep {
        switch self {
        case .preSplit(let s):      return s
        case .photo(_, let s):     return s
        }
    }
}

// MARK: - Main detail view

struct StepDetailView: View {
    @Environment(AppState.self) private var appState
    @Bindable var job: ProcessingJob
    @State private var selection: StepSelection

    init(job: ProcessingJob) {
        self.job = job
        self._selection = State(initialValue: Self.startSelection(for: job))
    }

    private static func startSelection(for job: ProcessingJob) -> StepSelection {
        switch job.currentStep {
        case .load, .pageDetect, .photoSplit:
            return .preSplit(job.currentStep)
        case .done:
            return .photo(index: 0, step: .colorCorrection)
        default:
            return .photo(index: 0, step: job.currentStep)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // ── Breadcrumb ────────────────────────────────────────────
            BreadcrumbBar(crumbs: ["Library", job.inputName]) {
                appState.navigateBack()
            }

            Divider()

            // ── Left tree + right canvas ─────────────────────────────
            HStack(spacing: 0) {
                StepTree(job: job, selection: $selection)
                    .frame(width: 196)

                Divider()

                StepCanvas(job: job, selection: selection)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .id(selection)
                    .overlay(alignment: .bottom) {
                        if job.state == .running {
                            ProcessingProgressBanner(job: job)
                                .transition(.move(edge: .bottom).combined(with: .opacity))
                        }
                    }
                    .animation(.saStandard, value: job.state == .running)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // ── Action bar ───────────────────────────────────────────
            let selStep = selection.pipelineStep
            if selStep == job.currentStep && selStep.requiresReview {
                StepActionBar(job: job)
            } else if selStep.rawValue < job.currentStep.rawValue && selStep != .done {
                ReprocessBar(job: job, fromStep: selStep)
            }
        }
        .background(Color.saBackground)
        .onChange(of: job.currentStep) { _, newStep in
            withAnimation(.saStandard) {
                switch newStep {
                case .load, .pageDetect, .photoSplit:
                    selection = .preSplit(newStep)
                case .done:
                    break
                default:
                    selection = .photo(index: 0, step: newStep)
                }
            }
        }
    }
}

// MARK: - Step tree (left pane)

private struct StepTree: View {
    let job: ProcessingJob
    @Binding var selection: StepSelection

    private let preSplitSteps: [PipelineStep] = [.load, .pageDetect, .photoSplit]
    private let perPhotoSteps: [PipelineStep] = [.orientation, .glareRemoval, .colorCorrection, .done]

    var body: some View {
        ScrollView(showsIndicators: true) {
            VStack(alignment: .leading, spacing: 1) {
                // Job-level steps
                ForEach(preSplitSteps) { step in
                    TreeRow(
                        icon: step.systemImage,
                        label: step.title,
                        isSelected: selection == .preSplit(step),
                        isComplete: job.completedSteps.contains(step),
                        isCurrent: step == job.currentStep,
                        isAccessible: canAccess(step),
                        isRunning: job.state == .running && step == job.currentStep
                    )
                    .contentShape(Rectangle())
                    .onTapGesture {
                        guard canAccess(step) else { return }
                        withAnimation(.saStandard) { selection = .preSplit(step) }
                    }
                }

                let photos = job.extractedPhotos

                if photos.count > 1 {
                    // Multi-photo branches
                    ForEach(Array(photos.enumerated()), id: \.offset) { idx, photo in
                        PhotoBranchGroup(
                            photo: photo,
                            photoIndex: idx,
                            steps: perPhotoSteps,
                            job: job,
                            selection: $selection
                        )
                    }
                } else {
                    // Single photo or pre-split: flat per-photo list
                    ForEach(perPhotoSteps) { step in
                        TreeRow(
                            icon: step.systemImage,
                            label: step.title,
                            isSelected: selection == .photo(index: 0, step: step),
                            isComplete: job.completedSteps.contains(step),
                            isCurrent: step == job.currentStep,
                            isAccessible: canAccess(step),
                            isRunning: job.state == .running && step == job.currentStep
                        )
                        .contentShape(Rectangle())
                        .onTapGesture {
                            guard canAccess(step) else { return }
                            withAnimation(.saStandard) { selection = .photo(index: 0, step: step) }
                        }
                    }
                }
            }
            .padding(.top, 4)
            .padding(.bottom, 20)
        }
        .background(Color.saSurface)
    }

    private func canAccess(_ step: PipelineStep) -> Bool {
        job.completedSteps.contains(step) || step == job.currentStep
    }
}

// MARK: - Photo branch group

private struct PhotoBranchGroup: View {
    let photo: ExtractedPhoto
    let photoIndex: Int
    let steps: [PipelineStep]
    let job: ProcessingJob
    @Binding var selection: StepSelection

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Photo header
            HStack(spacing: 8) {
                PhotoMiniThumb(url: photo.imageURL)

                VStack(alignment: .leading, spacing: 1) {
                    Text("Photo \(photoIndex + 1)")
                        .font(.dmSans(12, weight: .semibold))
                        .foregroundStyle(Color.saTextPrimary)
                    if let rot = photo.rotationOverride {
                        Text("\(rot)° override")
                            .font(.dmSans(9))
                            .foregroundStyle(Color.saAmber600)
                    }
                }
                Spacer()
            }
            .padding(.leading, 10)
            .padding(.trailing, 8)
            .padding(.top, 10)
            .padding(.bottom, 4)

            // Indented step rows with connector line
            HStack(alignment: .top, spacing: 0) {
                Rectangle()
                    .fill(Color.saStone200)
                    .frame(width: 1)
                    .padding(.leading, 23)
                    .padding(.bottom, 4)

                VStack(alignment: .leading, spacing: 1) {
                    ForEach(steps) { step in
                        TreeRow(
                            icon: step.systemImage,
                            label: step.title,
                            isSelected: selection == .photo(index: photoIndex, step: step),
                            isComplete: job.completedSteps.contains(step),
                            isCurrent: step == job.currentStep,
                            isAccessible: canAccess(step),
                            isRunning: job.state == .running && step == job.currentStep
                        )
                        .contentShape(Rectangle())
                        .onTapGesture {
                            guard canAccess(step) else { return }
                            withAnimation(.saStandard) {
                                selection = .photo(index: photoIndex, step: step)
                            }
                        }
                    }
                }
            }
        }
    }

    private func canAccess(_ step: PipelineStep) -> Bool {
        job.completedSteps.contains(step) || step == job.currentStep
    }
}

// MARK: - Photo mini thumbnail

private struct PhotoMiniThumb: View {
    let url: URL
    @State private var image: NSImage?

    var body: some View {
        Group {
            if let img = image {
                Image(nsImage: img).resizable().aspectRatio(contentMode: .fill)
            } else {
                Rectangle().fill(Color.saStone300)
            }
        }
        .frame(width: 30, height: 30)
        .clipShape(RoundedRectangle(cornerRadius: 4))
        .task { image = NSImage(contentsOf: url) }
    }
}

// MARK: - Pulsing ring (active step indicator)

private struct PulsingRing: View {
    @State private var animate = false

    var body: some View {
        Circle()
            .strokeBorder(Color.saAmber400, lineWidth: 2)
            .frame(width: 28, height: 28)
            .scaleEffect(animate ? 1.7 : 0.8)
            .opacity(animate ? 0 : 0.8)
            .onAppear {
                withAnimation(.easeOut(duration: 0.9).repeatForever(autoreverses: false)) {
                    animate = true
                }
            }
    }
}

// MARK: - Tree row

private struct TreeRow: View {
    let icon: String
    let label: String
    let isSelected: Bool
    let isComplete: Bool
    let isCurrent: Bool
    let isAccessible: Bool
    let isRunning: Bool

    var body: some View {
        HStack(spacing: 8) {
            ZStack {
                if isRunning {
                    PulsingRing()
                }
                Circle()
                    .fill(isSelected ? Color.saAmber500 : Color.clear)
                    .frame(width: 22, height: 22)
                Image(systemName: isComplete ? "checkmark" : icon)
                    .font(.system(
                        size: isComplete ? 8 : 10,
                        weight: isSelected ? .semibold : .regular
                    ))
                    .foregroundStyle(
                        isSelected ? .white
                        : isComplete ? Color.saSuccess
                        : Color.saTextTertiary
                    )
            }

            Text(label)
                .font(.dmSans(12, weight: isSelected ? .semibold : .regular))
                .foregroundStyle(isSelected ? Color.saAmber600 : Color.saTextPrimary)
                .lineLimit(1)

            Spacer()

            if isCurrent && !isSelected {
                Circle()
                    .fill(Color.saAmber400)
                    .frame(width: 5, height: 5)
                    .padding(.trailing, 2)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(isSelected ? Color.saAmber500.opacity(0.10) : Color.clear)
        .opacity(isAccessible ? 1.0 : 0.35)
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("tree-row-\(label)")
    }
}

// MARK: - Step canvas (right pane)

private struct StepCanvas: View {
    let job: ProcessingJob
    let selection: StepSelection

    var body: some View {
        Group {
            switch selection {
            case .preSplit(let step):
                preSplitCanvas(step)
            case .photo(let idx, let step):
                photoCanvas(idx, step)
            }
        }
    }

    @ViewBuilder
    private func preSplitCanvas(_ step: PipelineStep) -> some View {
        switch step {
        case .load:
            DebugImageView(step: .load, inputName: job.inputName)
        case .pageDetect:
            PageDetectionStepView(job: job)
        default:
            PhotoSplitStepView(job: job)
        }
    }

    @ViewBuilder
    private func photoCanvas(_ idx: Int, _ step: PipelineStep) -> some View {
        switch step {
        case .orientation:
            OrientationStepView(job: job, photoIndex: idx)
        case .glareRemoval:
            GlareRemovalStepView(job: job, photoIndex: idx)
        case .colorCorrection:
            ColorCorrectionStepView(job: job, photoIndex: idx)
        default:
            ResultsStepView(job: job, photoIndex: idx)
        }
    }
}

// MARK: - Breadcrumb

struct BreadcrumbBar: View {
    let crumbs: [String]
    var onBack: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            Button { withAnimation(.saSlide) { onBack() } } label: {
                Image(systemName: "chevron.left")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(Color.saAmber600)
            }
            .buttonStyle(.plain)

            ForEach(Array(crumbs.enumerated()), id: \.offset) { idx, crumb in
                if idx > 0 {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 9, weight: .medium))
                        .foregroundStyle(Color.saStone400)
                }
                if idx < crumbs.count - 1 {
                    Button(crumb) { withAnimation(.saSlide) { onBack() } }
                        .buttonStyle(.plain)
                        .font(.dmSans(13))
                        .foregroundStyle(Color.saAmber600)
                } else {
                    Text(crumb)
                        .font(.dmSans(13, weight: .semibold))
                        .foregroundStyle(Color.saTextPrimary)
                        .lineLimit(1)
                }
            }
            Spacer()
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 11)
        .background(Color.saSurface)
    }
}

// MARK: - Action bar (current step awaiting review)

struct StepActionBar: View {
    @Bindable var job: ProcessingJob

    var body: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 10) {
                Button {
                    // mock: re-run this step
                } label: {
                    Label("Redo", systemImage: "arrow.counterclockwise")
                        .font(.dmSans(13))
                }
                .buttonStyle(.bordered)
                .controlSize(.regular)

                Spacer()

                Button {
                    // mock: open manual editor
                } label: {
                    Label("Edit Manually", systemImage: "pencil")
                        .font(.dmSans(13))
                }
                .buttonStyle(.bordered)
                .controlSize(.regular)

                Button {
                    withAnimation(.saStandard) { job.advance() }
                } label: {
                    HStack(spacing: 6) {
                        Text("Looks Good")
                            .font(.dmSans(13, weight: .semibold))
                        Image(systemName: "arrow.right")
                            .font(.system(size: 11, weight: .semibold))
                    }
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.saAmber500)
                .controlSize(.regular)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
        }
        .background(Color.saStone50)
    }
}

// MARK: - Reprocess bar (browsing a past step)

struct ReprocessBar: View {
    @Bindable var job: ProcessingJob
    let fromStep: PipelineStep

    var body: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                Image(systemName: "info.circle")
                    .foregroundStyle(Color.saAmber500)
                Text("Viewing \(fromStep.title) — make adjustments above")
                    .font(.dmSans(13))
                    .foregroundStyle(Color.saStone500)
                Spacer()
                Button {
                    withAnimation(.saStandard) {
                        job.currentStep = fromStep
                        job.stepStatus = fromStep.requiresReview ? .awaitingReview : .running
                        job.state = .running
                        if fromStep.rawValue <= PipelineStep.photoSplit.rawValue {
                            job.extractedPhotos = []
                        }
                    }
                } label: {
                    Label("Save & Re-process from Here", systemImage: "arrow.clockwise")
                        .font(.dmSans(13, weight: .semibold))
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.saAmber500)
                .controlSize(.regular)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
        }
        .background(Color.saStone50)
    }
}

// MARK: - Processing progress banner (overlay shown while pipeline runs)

private struct ProcessingProgressBanner: View {
    let job: ProcessingJob
    private let totalSteps = PipelineStep.allCases.count - 1

    var body: some View {
        VStack(spacing: 0) {
            Divider()
            HStack(spacing: 12) {
                ProgressView()
                    .controlSize(.small)
                    .scaleEffect(0.85)

                VStack(alignment: .leading, spacing: 4) {
                    let stepNum = min(job.currentStep.rawValue + 1, totalSteps)
                    let stepLabel = job.currentStepName ?? job.currentStep.description
                    Text("Step \(stepNum) of \(totalSteps): \(stepLabel)")
                        .font(.dmSans(12, weight: .semibold))
                        .foregroundStyle(Color.saTextPrimary)
                        .lineLimit(1)

                    GeometryReader { geo in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Color.saStone200)
                            Capsule()
                                .fill(Color.saAmber500)
                                .frame(width: geo.size.width * job.progressFraction)
                                .animation(.saStandard, value: job.progressFraction)
                        }
                    }
                    .frame(height: 3)
                }

                Spacer()

                Text("\(Int(job.progressFraction * 100))%")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(Color.saStone500)
                    .animation(.saStandard, value: job.progressFraction)
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 12)
        }
        .background(.ultraThinMaterial)
    }
}

// MARK: - Debug image viewer (load step)

struct DebugImageView: View {
    let step: PipelineStep
    let inputName: String
    @State private var image: NSImage?

    var body: some View {
        ZStack {
            Color.saStone900
            if let img = image {
                Image(nsImage: img)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
            } else {
                VStack(spacing: 12) {
                    Image(systemName: step.systemImage)
                        .font(.system(size: 40, weight: .light))
                        .foregroundStyle(Color.saStone600)
                    Text("No debug image for this step")
                        .font(.dmSans(14))
                        .foregroundStyle(Color.saStone500)
                }
            }
        }
        .task {
            if let url = step.debugImageURL(forInputName: inputName) {
                image = NSImage(contentsOf: url)
            }
        }
    }
}
