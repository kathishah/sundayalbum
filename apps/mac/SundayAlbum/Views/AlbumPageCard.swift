import SwiftUI
import AppKit

// MARK: - Compact card (library grid)

struct AlbumPageCard: View {
    let job: ProcessingJob
    @Environment(AppState.self) private var appState
    @State private var beforeImage: NSImage?
    @State private var isHovered = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {

            // ── Thumbnail row — geometry-aware so after-thumbs fill remaining space ──
            GeometryReader { geo in
                let hPad: CGFloat = 12
                let beforeW: CGFloat = 60
                let fixedChrome: CGFloat = 10 + 11 + 10  // HStack spacing × 2 + arrow icon
                let afterW = max(geo.size.width - hPad * 2 - beforeW - fixedChrome, 40)

                HStack(alignment: .center, spacing: 10) {
                    Spacer(minLength: 0)

                    ThumbBox(image: beforeImage)
                        .frame(width: beforeW, height: 88)

                    Image(systemName: "arrow.right")
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(Color.saAmber400)

                    AfterSection(job: job, thumbHeight: 88, sectionWidth: afterW)

                    Spacer(minLength: 0)
                }
                // Fill the full GeometryReader height so SwiftUI vertically centers content
                .frame(width: geo.size.width, height: geo.size.height, alignment: .center)
            }
            .frame(height: 88 + 24)  // thumbHeight + top/bottom padding

            // ── File name — no divider, tight padding ─────────────────
            Text(job.inputName)
                .font(.dmSans(12, weight: .semibold))
                .foregroundStyle(Color.saTextPrimary)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.horizontal, 12)
                .padding(.top, 4)
                .padding(.bottom, 10)
        }
        .background(Color.saCard)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .shadow(color: Color.saShadow, radius: 6, y: 3)
        .overlay(alignment: .topTrailing) {
            if isHovered {
                Button {
                    appState.removeJob(id: job.id)
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 16))
                        .symbolRenderingMode(.hierarchical)
                        .foregroundStyle(
                            job.state == .running || job.state == .queued
                                ? Color.saError : Color.saStone400
                        )
                }
                .buttonStyle(.plain)
                .padding(8)
                .transition(.opacity.combined(with: .scale(scale: 0.8)))
            }
        }
        .animation(.saStandard, value: isHovered)
        .onHover { isHovered = $0 }
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("job-card-\(job.inputName)")
        .task { beforeImage = job.loadBeforeImage() }
    }
}

// MARK: - Expanded overlay card (single-click)

struct ExpandedAlbumCard: View {
    let job: ProcessingJob
    var onViewDetails: () -> Void

    @State private var beforeImage: NSImage?

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {

            // ── Large thumbnail row — no labels ──────────────────────
            HStack(alignment: .center, spacing: 16) {
                Spacer(minLength: 0)

                ThumbBox(image: beforeImage)
                    .frame(width: 120, height: 160)

                Image(systemName: "arrow.right")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Color.saAmber500)

                AfterSection(job: job, thumbHeight: 160)

                Spacer(minLength: 0)
            }
            .padding(20)

            Divider()

            // ── Footer ───────────────────────────────────────────────
            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(job.inputName)
                        .font(.dmSans(14, weight: .semibold))
                        .foregroundStyle(Color.saTextPrimary)
                        .lineLimit(1)
                    JobStatusLine(job: job)
                }
                Spacer()
                Button("View Step Details") {
                    withAnimation(.saSlide) { onViewDetails() }
                }
                .buttonStyle(.borderedProminent)
                .tint(Color.saAmber500)
                .font(.dmSans(13, weight: .semibold))
                .controlSize(.regular)
            }
            .padding(20)
        }
        .background(Color.saCard)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.saBorder, lineWidth: 1)
        }
        .shadow(color: Color.saStone900.opacity(0.22), radius: 32, y: 12)
        .task { beforeImage = job.loadBeforeImage() }
    }
}

// MARK: - ThumbBox (before — always portrait crop, no label)

struct ThumbBox: View {
    let image: NSImage?

    var body: some View {
        Group {
            if let img = image {
                Image(nsImage: img)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } else {
                Rectangle()
                    .fill(Color.saSurface)
                    .overlay { ProgressView().controlSize(.small) }
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }
}

// MARK: - AfterSection

struct AfterSection: View {
    let job: ProcessingJob
    let thumbHeight: CGFloat
    /// When set (compact card), all photos share this total width equally.
    /// When nil (expanded card), thumbnails use natural aspect ratios up to 3 shown.
    var sectionWidth: CGFloat? = nil

    var body: some View {
        if job.state == .complete, !job.extractedPhotos.isEmpty {
            if let totalWidth = sectionWidth {
                // Compact mode: every extracted photo gets an equal-width slot.
                let photos = job.extractedPhotos
                let gap: CGFloat = 4
                let slotW = max((totalWidth - gap * CGFloat(photos.count - 1)) / CGFloat(photos.count), 20)
                HStack(spacing: gap) {
                    ForEach(photos) { photo in
                        AfterThumb(url: photo.imageURL, height: thumbHeight, slotWidth: slotW)
                    }
                }
                .frame(width: totalWidth)
            } else {
                // Expanded mode: natural aspect ratios, up to 3 shown.
                let visible = Array(job.extractedPhotos.prefix(3))
                let overflow = job.extractedPhotos.count - visible.count
                HStack(spacing: 8) {
                    ForEach(visible) { photo in
                        AfterThumb(url: photo.imageURL, height: thumbHeight)
                    }
                    if overflow > 0 {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6).fill(Color.saStone200)
                            Text("+\(overflow)")
                                .font(.dmSans(12, weight: .semibold))
                                .foregroundStyle(Color.saStone500)
                        }
                        .frame(width: thumbHeight * 0.65, height: thumbHeight)
                    }
                }
            }
        } else {
            // In progress or queued — show pie-chart progress wheel
            PipelineProgressWheel(job: job, size: thumbHeight)
        }
    }
}

// MARK: - AfterThumb

struct AfterThumb: View {
    let url: URL
    let height: CGFloat
    /// When set (compact equal-slot mode), fills the given width with .fill cropping.
    /// When nil (expanded mode), width is derived from the image's natural aspect ratio.
    var slotWidth: CGFloat? = nil

    @State private var image: NSImage?

    private var thumbWidth: CGFloat {
        if let w = slotWidth { return w }
        guard let img = image else { return height * 0.75 }
        let ratio = img.size.width / img.size.height
        return height * min(ratio, 1.5)
    }

    var body: some View {
        Group {
            if let img = image {
                Image(nsImage: img)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
            } else {
                Rectangle().fill(Color.saStone200)
            }
        }
        .frame(width: thumbWidth, height: height)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .animation(.saStandard, value: thumbWidth)
        .task { image = NSImage(contentsOf: url) }
    }
}

// MARK: - PipelineProgressWheel (replaces blank processing placeholder)

struct PipelineProgressWheel: View {
    let job: ProcessingJob
    let size: CGFloat

    private let totalSteps = PipelineStep.allCases.count - 1  // 6 real steps (exclude .done)

    private var completedCount: Int {
        min(job.currentStep.rawValue, totalSteps)
    }

    var body: some View {
        ZStack {
            // Pie segments — one per step
            ForEach(0..<totalSteps, id: \.self) { i in
                if job.state == .running && i == completedCount {
                    // Next segment pulses to show active processing
                    PulsingPieSegment(index: i, total: totalSteps)
                } else {
                    PieSegment(index: i, total: totalSteps)
                        .fill(i < completedCount ? Color.saAmber500 : Color.saStone200)
                }
            }

            // Donut hole
            Circle()
                .fill(Color.saCard)
                .padding(size * 0.22)

            // Center label
            VStack(spacing: 1) {
                Text("\(completedCount)")
                    .font(.dmSans(size * 0.22, weight: .bold))
                    .foregroundStyle(Color.saTextPrimary)
                Text("of \(totalSteps)")
                    .font(.dmSans(size * 0.12))
                    .foregroundStyle(Color.saTextTertiary)
            }
        }
        .frame(width: size, height: size)
    }
}

// MARK: - Pulsing pie segment (active / next step)

private struct PulsingPieSegment: View {
    let index: Int
    let total: Int
    @State private var lit = false

    var body: some View {
        PieSegment(index: index, total: total)
            .fill(lit ? Color.saAmber400 : Color.saStone200)
            .onAppear {
                withAnimation(.easeInOut(duration: 0.65).repeatForever(autoreverses: true)) {
                    lit = true
                }
            }
    }
}

struct PieSegment: Shape {
    let index: Int
    let total: Int
    private let gapDegrees: Double = 3

    func path(in rect: CGRect) -> Path {
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2
        let slice = 360.0 / Double(total)
        let start = Angle.degrees(Double(index) * slice - 90 + gapDegrees / 2)
        let end   = Angle.degrees(Double(index + 1) * slice - 90 - gapDegrees / 2)

        var path = Path()
        path.move(to: center)
        path.addArc(center: center, radius: radius,
                    startAngle: start, endAngle: end, clockwise: false)
        path.closeSubpath()
        return path
    }
}

// MARK: - JobStatusLine

struct JobStatusLine: View {
    let job: ProcessingJob
    private let totalSteps = PipelineStep.allCases.count - 1

    var body: some View {
        switch job.state {
        case .queued:
            Label("Queued", systemImage: "clock")
                .font(.dmSans(11))
                .foregroundStyle(Color.saStone400)

        case .running:
            HStack(spacing: 6) {
                // Slim custom bar — avoids NSProgressIndicator layout warnings
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.saStone200)
                        Capsule().fill(Color.saAmber500)
                            .frame(width: geo.size.width * job.progressFraction)
                    }
                }
                .frame(width: 52, height: 3)

                let stepNum = min(job.currentStep.rawValue + 1, totalSteps)
                let stepLabel = job.currentStepName ?? job.currentStep.title
                Text("Step \(stepNum) of \(totalSteps): \(stepLabel)")
                    .font(.dmSans(11))
                    .foregroundStyle(
                        job.stepStatus == .awaitingReview ? Color.saAmber600 : Color.saTextSecondary
                    )
            }

        case .complete:
            Label(
                "\(job.extractedPhotos.count) photo\(job.extractedPhotos.count == 1 ? "" : "s") extracted"
                    + (job.processingTime.map { " · \(String(format: "%.1f", $0))s" } ?? ""),
                systemImage: "checkmark.circle.fill"
            )
            .font(.dmSans(11))
            .foregroundStyle(Color.saSuccess)

        case .failed:
            Label(job.errorMessage ?? "Failed", systemImage: "exclamationmark.circle.fill")
                .font(.dmSans(11))
                .foregroundStyle(Color.saError)
        }
    }
}

// MARK: - Helpers

private extension ProcessingJob {
    /// Use debug/01_loaded.jpg if available (faster), else fall back to original HEIC
    @MainActor
    func loadBeforeImage() -> NSImage? {
        if let url = PipelineStep.load.debugImageURL(forInputName: inputName) {
            return NSImage(contentsOf: url)
        }
        return inputURL.flatMap { NSImage(contentsOf: $0) }
    }
}
