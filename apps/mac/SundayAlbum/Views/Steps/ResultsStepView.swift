import SwiftUI
import AppKit

/// Final step — single focused photo view with prev/next navigation and export.
struct ResultsStepView: View {
    let job: ProcessingJob

    @State private var selectedIndex: Int
    @State private var image: NSImage?

    /// `photoIndex` seeds the initial selection so "Photo 2 > Done" opens on photo 2.
    init(job: ProcessingJob, photoIndex: Int = 0) {
        self.job = job
        self._selectedIndex = State(initialValue: photoIndex)
    }

    var photos: [ExtractedPhoto] { job.extractedPhotos }
    var total: Int { photos.count }
    var currentPhoto: ExtractedPhoto? { photos[safe: selectedIndex] }

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
                        .transition(.opacity)
                } else {
                    ProgressView().controlSize(.large)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .animation(.saStandard, value: selectedIndex)

            Divider()

            // ── Footer ──────────────────────────────────────────────
            HStack(spacing: 12) {
                // Prev / Next (only when multiple photos)
                if total > 1 {
                    HStack(spacing: 6) {
                        Button {
                            withAnimation(.saStandard) { selectedIndex = max(0, selectedIndex - 1) }
                        } label: {
                            Image(systemName: "chevron.left")
                                .font(.system(size: 11, weight: .semibold))
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .disabled(selectedIndex == 0)

                        Text("\(selectedIndex + 1)")
                            .font(.jetbrainsMono(12))
                            .foregroundStyle(Color.saTextPrimary)
                        + Text(" / \(total)")
                            .font(.jetbrainsMono(12))
                            .foregroundStyle(Color.saTextTertiary)

                        Button {
                            withAnimation(.saStandard) { selectedIndex = min(total - 1, selectedIndex + 1) }
                        } label: {
                            Image(systemName: "chevron.right")
                                .font(.system(size: 11, weight: .semibold))
                        }
                        .buttonStyle(.bordered)
                        .controlSize(.small)
                        .disabled(selectedIndex == total - 1)
                    }
                }

                Spacer()

                // Filename
                if let photo = currentPhoto {
                    Text(photo.imageURL.lastPathComponent)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(Color.saTextTertiary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .frame(maxWidth: 200)
                }

                // Export current
                if let photo = currentPhoto {
                    Button {
                        ExportActions.showInFinder(photo.imageURL)
                    } label: {
                        Label(total > 1 ? "Export Photo \(selectedIndex + 1)" : "Export",
                              systemImage: "square.and.arrow.up")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color.saAmber500)
                    .controlSize(.small)
                    .font(.dmSans(12, weight: .semibold))
                }

                // Export all (when multiple)
                if total > 1 {
                    Button("Export All (\(total))") {
                        ExportActions.exportToFolder(photos)
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .font(.dmSans(12, weight: .medium))
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(Color.saCard)
        }
        .task(id: selectedIndex) {
            image = nil
            if let url = currentPhoto?.imageURL {
                image = NSImage(contentsOf: url)
            }
        }
        .onChange(of: job.extractedPhotos.count) {
            // Clamp index if photos were removed
            selectedIndex = min(selectedIndex, max(0, total - 1))
        }
    }
}

// MARK: - Safe subscript

private extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
