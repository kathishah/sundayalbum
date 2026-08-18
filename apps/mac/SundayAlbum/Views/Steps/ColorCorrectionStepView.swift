import SwiftUI
import AppKit

/// Color correction view for a single extracted photo.
/// The tree in StepDetailView handles photo selection; this view shows one photo's controls.
struct ColorCorrectionStepView: View {
    let job: ProcessingJob
    let photoIndex: Int   // 0-based
    @Environment(AppState.self) private var appState

    @State private var image: NSImage?
    @State private var saturation: Double = 0.15
    @State private var sharpness: Double = 0.50
    @State private var isProcessing = false

    var photo: ExtractedPhoto? { job.extractedPhotos[safe: photoIndex] }

    private let defaultSaturation = 0.15
    private let defaultSharpness  = 0.50

    var isDirty: Bool {
        abs(saturation - defaultSaturation) > 0.001 || abs(sharpness - defaultSharpness) > 0.001
    }

    var body: some View {
        VStack(spacing: 0) {
            // ── Image canvas ────────────────────────────────────────
            ZStack {
                Color.saStone900
                if let img = image {
                    Image(nsImage: img)
                        .resizable()
                        .aspectRatio(contentMode: .fit)
                        .padding(24)
                } else {
                    ProgressView().controlSize(.large)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            Divider()

            // ── Controls footer (horizontal) ─────────────────────────
            HStack(spacing: 20) {
                InlineSlider(
                    label: "Saturation",
                    icon: "drop",
                    value: $saturation,
                    range: 0...0.5
                )

                InlineSlider(
                    label: "Sharpness",
                    icon: "camera.aperture",
                    value: $sharpness,
                    range: 0...1.0
                )

                Spacer()

                if isDirty && !isProcessing {
                    Button("Discard") {
                        withAnimation(.saStandard) {
                            saturation = defaultSaturation
                            sharpness  = defaultSharpness
                        }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)

                    Button("Apply & Reprocess") {
                        isProcessing = true
                        let runner = PipelineRunner(job: job)
                        runner.reprocessFromColor(
                            vibranceBoost: saturation,
                            sharpenAmount: sharpness
                        )
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color.saAmber500)
                    .controlSize(.small)
                    .accessibilityIdentifier("btn-reprocess-color")
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 14)
            .background(Color.saCard)
        }
        .task(id: photoIndex) {
            isProcessing = false
            image = nil
            let url = PipelineStep.colorCorrection.debugImageURL(
                forInputName: job.inputName,
                photoIndex: photoIndex + 1
            ) ?? photo?.imageURL ?? job.inputURL
            if let u = url { image = NSImage(contentsOf: u) }
            saturation = defaultSaturation
            sharpness  = defaultSharpness
        }
    }
}

// MARK: - Inline slider (label + track in a compact row)

private struct InlineSlider: View {
    let label: String
    let icon: String
    @Binding var value: Double
    let range: ClosedRange<Double>

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(Color.saStone400)
            Text(label)
                .font(.dmSans(12, weight: .medium))
                .foregroundStyle(Color.saStone700)
            Slider(value: $value, in: range)
                .tint(Color.saAmber500)
                .frame(width: 120)
                .accessibilityIdentifier("slider-\(label.lowercased())")
            Text(String(format: "%+.0f%%", value * 100))
                .font(.jetbrainsMono(11))
                .foregroundStyle(Color.saStone400)
                .frame(width: 40, alignment: .trailing)
        }
    }
}

// MARK: - Safe subscript

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
