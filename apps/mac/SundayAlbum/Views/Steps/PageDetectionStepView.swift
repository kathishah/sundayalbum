import SwiftUI
import AppKit

/// Shows the input image with a draggable quadrilateral border overlay.
/// The user can drag any of the 4 corner handles to correct the detected page boundary.
struct PageDetectionStepView: View {
    let job: ProcessingJob

    @State private var image: NSImage?

    // Normalized corner positions (0–1 relative to the overlay area).
    // Initialised to a realistic "slightly inset" detected page.
    @State private var tl = CGPoint(x: 0.05, y: 0.07)
    @State private var tr = CGPoint(x: 0.95, y: 0.05)
    @State private var br = CGPoint(x: 0.93, y: 0.95)
    @State private var bl = CGPoint(x: 0.07, y: 0.93)

    var body: some View {
        ZStack {
            Color.black

            if let img = image {
                Image(nsImage: img)
                    .resizable()
                    .aspectRatio(contentMode: .fit)
            }

            // Overlay: dashed border + draggable corner handles
            GeometryReader { geo in
                let sz = geo.size

                // Dim outside detected region
                BorderDimOverlay(tl: tl, tr: tr, br: br, bl: bl, size: sz)
                    .allowsHitTesting(false)

                // Dashed quad border
                Path { p in
                    p.move(to: tl.scaled(to: sz))
                    p.addLine(to: tr.scaled(to: sz))
                    p.addLine(to: br.scaled(to: sz))
                    p.addLine(to: bl.scaled(to: sz))
                    p.closeSubpath()
                }
                .stroke(Color.saAmber500, style: StrokeStyle(lineWidth: 2, dash: [10, 5]))

                // Corner handles
                CornerHandle(normalized: $tl, size: sz)
                CornerHandle(normalized: $tr, size: sz)
                CornerHandle(normalized: $br, size: sz)
                CornerHandle(normalized: $bl, size: sz)
            }
        }
        .task {
            if let url = job.inputURL {
                image = NSImage(contentsOf: url)
            }
        }
    }
}

// MARK: - Dim overlay

private struct BorderDimOverlay: View {
    let tl, tr, br, bl: CGPoint
    let size: CGSize

    var body: some View {
        Canvas { ctx, canvasSize in
            // Full rect minus the quad = dimmed region
            var outside = Path(CGRect(origin: .zero, size: canvasSize))
            var inside = Path()
            inside.move(to: tl.scaled(to: size))
            inside.addLine(to: tr.scaled(to: size))
            inside.addLine(to: br.scaled(to: size))
            inside.addLine(to: bl.scaled(to: size))
            inside.closeSubpath()
            outside.addPath(inside)  // even-odd fill subtracts interior
            ctx.fill(outside, with: .color(.black.opacity(0.45)), style: FillStyle(eoFill: true))
        }
    }
}

// MARK: - Draggable corner handle

private struct CornerHandle: View {
    @Binding var normalized: CGPoint
    let size: CGSize

    var actual: CGPoint { normalized.scaled(to: size) }

    var body: some View {
        ZStack {
            Circle()
                .fill(Color.saAmber500)
                .frame(width: 20, height: 20)
            Circle()
                .strokeBorder(Color.white, lineWidth: 2)
                .frame(width: 20, height: 20)
        }
        .shadow(color: .black.opacity(0.4), radius: 4)
        .position(actual)
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { v in
                    normalized = CGPoint(
                        x: (v.location.x / size.width).clamped(to: 0...1),
                        y: (v.location.y / size.height).clamped(to: 0...1)
                    )
                }
        )
    }
}

// MARK: - Helpers

private extension CGPoint {
    func scaled(to size: CGSize) -> CGPoint {
        CGPoint(x: x * size.width, y: y * size.height)
    }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}
