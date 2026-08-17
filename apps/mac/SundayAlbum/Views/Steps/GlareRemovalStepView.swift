import SwiftUI
import AppKit

// The static part of the prompt sent to OpenAI gpt-image-1.5.
// Source: src/glare/remover_openai.py _build_prompt()
private let kPromptStatic =
    "We used an iPhone camera to photograph a picture printed on glossy paper for digitization. " +
    "Remove glare/reflections caused by the glossy surface. " +
    "Preserve the original composition, geometry, textures, and colors. " +
    "Only modify pixels necessary to remove glare/reflections; do not change framing. " +
    "Description of the printed photo: "

/// Glare removal result view for a single extracted photo.
/// Shows the deglared image with a reveal animation, and displays
/// the prompt template used for the OpenAI call.
struct GlareRemovalStepView: View {
    let job: ProcessingJob
    let photoIndex: Int   // 0-based
    @Environment(AppState.self) private var appState

    @State private var afterOpacity: Double = 0
    @State private var showGlow = false
    @State private var sceneDesc: String = ""
    @State private var isProcessing = false

    var photo: ExtractedPhoto? { job.extractedPhotos[safe: photoIndex] }

    var body: some View {
        VStack(spacing: 0) {
            // ── Image canvas ────────────────────────────────────────
            ZStack {
                Color.saStone900
                ImagePane(url: photo?.imageURL)
                    .shadow(
                        color: showGlow ? Color.saAmber500.opacity(0.2) : .clear,
                        radius: 20
                    )
                    .opacity(afterOpacity)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .onAppear { triggerReveal() }
            .onChange(of: photoIndex) { triggerReveal() }

            Divider()

            // ── Prompt footer ───────────────────────────────────────
            VStack(alignment: .leading, spacing: 10) {
                Text("Prompt sent to OpenAI")
                    .font(.dmSans(11, weight: .semibold))
                    .foregroundStyle(Color.saStone400)
                    .textCase(.uppercase)

                // Prompt template (monospace, wrapping)
                Text(kPromptStatic + (sceneDesc.isEmpty ? "[AI auto-detected scene description]" : sceneDesc))
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(Color.saTextSecondary)
                    .lineLimit(nil)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(10)
                    .background(Color.saCard)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay {
                        RoundedRectangle(cornerRadius: 6)
                            .strokeBorder(Color.saStone200, lineWidth: 1)
                    }

                HStack(spacing: 8) {
                    Text("Override scene description")
                        .font(.dmSans(11))
                        .foregroundStyle(Color.saTextTertiary)
                    TextField("Leave blank for AI description", text: $sceneDesc)
                        .font(.dmSans(12))
                        .textFieldStyle(.roundedBorder)
                        .accessibilityIdentifier("field-scene-desc-glare")
                }

                // ── Action row ──────────────────────────────────────
                HStack {
                    Spacer()
                    Button("Discard") {
                        sceneDesc = photo?.sceneDescription ?? ""
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .accessibilityIdentifier("btn-discard-glare")

                    Button("Re-run Glare Removal") {
                        isProcessing = true
                        // Persist the scene description override before launching the runner.
                        if let p = photo {
                            p.sceneDescription = sceneDesc.isEmpty ? nil : sceneDesc
                            appState.saveOverrides(for: p)
                        }
                        let runner = PipelineRunner(job: job)
                        runner.reprocessFromGlare(sceneDescription: sceneDesc)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color.saAmber500)
                    .controlSize(.small)
                    .disabled(isProcessing)
                    .accessibilityIdentifier("btn-rerun-glare")
                }
            }
            .padding(16)
            .background(Color.saCard)
        }
    }

    private func triggerReveal() {
        afterOpacity = 0
        showGlow = false
        isProcessing = false
        sceneDesc = photo?.sceneDescription ?? ""
        Task {
            try? await Task.sleep(for: .milliseconds(80))
            withAnimation(.saReveal) { afterOpacity = 1 }
            withAnimation(.saReveal.delay(0.4)) { showGlow = true }
        }
    }
}

// MARK: - Image pane

private struct ImagePane: View {
    let url: URL?
    @State private var image: NSImage?

    var body: some View {
        Group {
            if let img = image {
                Image(nsImage: img).resizable().aspectRatio(contentMode: .fit)
            } else {
                Rectangle().fill(Color.saStone800)
                    .aspectRatio(4 / 3, contentMode: .fit)
                    .overlay { ProgressView().controlSize(.regular) }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .task(id: url) {
            image = nil
            if let u = url { image = NSImage(contentsOf: u) }
        }
    }
}

// MARK: - Safe subscript

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
