import SwiftUI
import AppKit

struct ComparisonView: View {
    let photo: ExtractedPhoto

    @State private var afterOpacity: Double = 0
    @State private var showGlow = false
    @State private var originalImage: NSImage?
    @State private var processedImage: NSImage?

    var body: some View {
        VStack(spacing: 0) {
            // Column headers
            HStack {
                Text("BEFORE")
                    .font(.dmSans(10, weight: .semibold))
                    .foregroundStyle(Color.saStone400)
                    .tracking(1.5)
                    .frame(maxWidth: .infinity)

                Text("AFTER")
                    .font(.dmSans(10, weight: .semibold))
                    .foregroundStyle(Color.saAmber500)
                    .tracking(1.5)
                    .frame(maxWidth: .infinity)
            }
            .padding(.top, 16)
            .padding(.horizontal, 12)
            .padding(.bottom, 8)

            // Image pair
            HStack(spacing: 8) {
                // Before — original input
                thumbnailView(originalImage)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .shadow(color: Color.saStone900.opacity(0.12), radius: 4, y: 2)

                // After — processed output (glare reveal animation)
                thumbnailView(processedImage)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .shadow(
                        color: showGlow ? Color.saAmber500.opacity(0.22) : .clear,
                        radius: 16
                    )
                    .opacity(afterOpacity)
            }
            .padding(.horizontal, 12)
            .frame(maxHeight: .infinity)

            Divider()
                .padding(.top, 8)

            // Metadata + actions
            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 3) {
                    Text(photo.jobInputName)
                        .font(.jetbrainsMono(11))
                        .foregroundStyle(Color.saTextSecondary)
                        .lineLimit(1)

                    Text("Extracted · glare removed · color restored")
                        .font(.dmSans(12))
                        .foregroundStyle(Color.saTextTertiary)
                }

                HStack(spacing: 8) {
                    Button("Show in Finder") {
                        ExportActions.showInFinder(photo.imageURL)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color.saAmber500)
                    .controlSize(.small)

                    Button("Add to Photos") {
                        Task { await ExportActions.addToPhotos(url: photo.imageURL) }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
        }
        .background(Color.saSurface)
        .id(photo.id)   // forces full redraw + re-animation on photo change
        .task {
            // Load images then trigger the signature reveal animation
            if let url = photo.jobInputURL {
                originalImage = NSImage(contentsOf: url)
            }
            processedImage = NSImage(contentsOf: photo.imageURL)

            try? await Task.sleep(for: .milliseconds(40))

            withAnimation(.saReveal) {
                afterOpacity = 1
            }
            withAnimation(.saReveal.delay(0.35)) {
                showGlow = true
            }
        }
    }

    @ViewBuilder
    func thumbnailView(_ image: NSImage?) -> some View {
        Group {
            if let img = image {
                Image(nsImage: img)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
            } else {
                Rectangle()
                    .fill(Color.saStone100)
                    .aspectRatio(4 / 3, contentMode: .fit)
                    .overlay {
                        ProgressView()
                            .controlSize(.small)
                    }
            }
        }
        .frame(maxWidth: .infinity)
    }
}
