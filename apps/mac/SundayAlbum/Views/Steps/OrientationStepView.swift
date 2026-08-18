import SwiftUI
import AppKit

/// Orientation review for a single extracted photo.
/// The tree in StepDetailView handles photo selection; this view shows one photo's controls.
struct OrientationStepView: View {
    @Bindable var job: ProcessingJob
    let photoIndex: Int   // 0-based

    var photo: ExtractedPhoto? { job.extractedPhotos[safe: photoIndex] }

    var body: some View {
        if let photo {
            OrientationPhotoPanel(
                photo: photo,
                job: job,
                inputName: job.inputName,
                photoIndex: photoIndex + 1
            )
        } else {
            OrientationPlaceholder()
        }
    }
}

// MARK: - Per-photo control panel

private struct OrientationPhotoPanel: View {
    @Bindable var photo: ExtractedPhoto
    let job: ProcessingJob
    let inputName: String
    let photoIndex: Int
    @Environment(AppState.self) private var appState

    @State private var image: NSImage?
    @State private var pendingRotation: Int = 0
    @State private var pendingDescription: String = ""
    @State private var isDirty = false

    var body: some View {
        VStack(spacing: 0) {
            // ── Image canvas ──────────────────────────────────────────
            ZStack {
                Color.saStone900
                if let img = image {
                    Image(nsImage: img)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .rotationEffect(.degrees(Double(pendingRotation)))
                        .animation(.saStandard, value: pendingRotation)
                        .padding(24)
                } else {
                    ProgressView().controlSize(.large)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Divider()

            // ── Controls footer ───────────────────────────────────────
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 16) {
                    Text("Rotate")
                        .font(.dmSans(12, weight: .semibold))
                        .foregroundStyle(Color.saTextSecondary)

                    RotationPicker(selected: $pendingRotation)
                        .onChange(of: pendingRotation) { checkDirty() }

                    Spacer()
                }

                HStack(spacing: 8) {
                    Text("Scene description")
                        .font(.dmSans(11))
                        .foregroundStyle(Color.saTextTertiary)
                        .frame(width: 110, alignment: .leading)
                    TextField("Leave blank for AI description", text: $pendingDescription)
                        .font(.dmSans(12))
                        .textFieldStyle(.roundedBorder)
                        .onChange(of: pendingDescription) { checkDirty() }
                        .accessibilityIdentifier("field-scene-desc-orientation")
                }

                if isDirty {
                    HStack {
                        Spacer()
                        Button("Discard") {
                            pendingRotation = photo.rotationOverride ?? 0
                            pendingDescription = photo.sceneDescription ?? ""
                            isDirty = false
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)

                        Button("Apply & Reprocess") {
                            photo.rotationOverride = pendingRotation == 0 ? nil : pendingRotation
                            photo.sceneDescription = pendingDescription.isEmpty ? nil : pendingDescription
                            appState.saveOverrides(for: photo)
                            isDirty = false
                            let runner = PipelineRunner(job: job)
                            runner.reprocessFromOrientation(
                                rotationDegrees: pendingRotation,
                                sceneDescription: pendingDescription
                            )
                        }
                        .buttonStyle(.borderedProminent)
                        .tint(Color.saAmber500)
                        .controlSize(.small)
                        .accessibilityIdentifier("btn-reprocess-orientation")
                    }
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .background(Color.saCard)
        }
        .task(id: photoIndex) {
            let url = PipelineStep.orientation.debugImageURL(
                forInputName: inputName, photoIndex: photoIndex
            ) ?? photo.imageURL
            image = NSImage(contentsOf: url)
            pendingRotation = photo.rotationOverride ?? 0
            pendingDescription = photo.sceneDescription ?? ""
            isDirty = false
        }
    }

    private func checkDirty() {
        isDirty = pendingRotation != (photo.rotationOverride ?? 0)
            || pendingDescription != (photo.sceneDescription ?? "")
    }
}

// MARK: - Rotation picker

private struct RotationPicker: View {
    @Binding var selected: Int

    private let options: [(label: String, degrees: Int)] = [
        ("0°",   0),
        ("90°",  90),
        ("180°", 180),
        ("270°", 270),
    ]

    var body: some View {
        HStack(spacing: 6) {
            ForEach(options, id: \.degrees) { opt in
                Button {
                    withAnimation(.saStandard) { selected = opt.degrees }
                } label: {
                    HStack(spacing: 4) {
                        if opt.degrees != 0 {
                            Image(systemName: "rotate.right")
                                .font(.system(size: 10))
                        }
                        Text(opt.label)
                            .font(.dmSans(12, weight: selected == opt.degrees ? .semibold : .regular))
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 5)
                    .background(selected == opt.degrees ? Color.saAmber500 : Color.saCard)
                    .foregroundStyle(selected == opt.degrees ? Color.white : Color.saTextPrimary)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay {
                        RoundedRectangle(cornerRadius: 6)
                            .strokeBorder(
                                selected == opt.degrees ? Color.clear : Color.saStone200,
                                lineWidth: 1
                            )
                    }
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("btn-rotation-\(opt.degrees)")
            }
        }
    }
}

// MARK: - Placeholder

private struct OrientationPlaceholder: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "rotate.right")
                .font(.system(size: 40, weight: .light))
                .foregroundStyle(Color.saStone600)
            Text("Waiting for photos to be extracted…")
                .font(.dmSans(14))
                .foregroundStyle(Color.saStone500)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.saStone900)
    }
}

// MARK: - Safe subscript

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
