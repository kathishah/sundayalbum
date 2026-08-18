import SwiftUI
import AppKit

/// Photo split step view — shows detected regions overlaid on the fitted page image.
/// Each region has 4 independently-draggable corner handles.
///
/// Architecture mirrors PageDetectionStepView exactly:
/// • Each CornerHandle is a DIRECT child of the GeometryReader (no wrapper ZStack).
/// • CornerHandle holds @Binding var pixelPos: CGPoint and updates it directly,
///   just like PageDetectionStepView.CornerHandle updates @Binding var normalized.
/// • This keeps gesture state alive across re-renders (SwiftUI updates the binding
///   in-place instead of recreating the view and its gesture recogniser).
struct PhotoSplitStepView: View {
    let job: ProcessingJob
    @Environment(AppState.self) private var appState

    @State private var pageImage: NSImage?
    @State private var regions: [EditableRegion] = []
    @State private var isDrawing = false
    @State private var drawStart: CGPoint? = nil
    @State private var drawCurrent: CGPoint? = nil
    @State private var isRerunning = false
    @State private var errorMessage: String? = nil
    @State private var loadDebugPath: String? = nil

    private var stem: String {
        URL(fileURLWithPath: job.inputName).deletingPathExtension().lastPathComponent
    }

    var body: some View {
        VStack(spacing: 0) {
            // ── Image canvas ───────────────────────────────────────────
            ZStack {
                Color.black

                GeometryReader { geo in
                    let imgSize = pageImage?.size ?? CGSize(width: 1, height: 1)
                    let fitted  = fitSize(imgSize, in: geo.size)
                    let origin  = CGPoint(
                        x: (geo.size.width  - fitted.width)  / 2,
                        y: (geo.size.height - fitted.height) / 2
                    )
                    let scaleX = imgSize.width  > 0 ? fitted.width  / imgSize.width  : 1
                    let scaleY = imgSize.height > 0 ? fitted.height / imgSize.height : 1

                    // ── Background image ──────────────────────────────
                    if let img = pageImage {
                        Image(nsImage: img)
                            .resizable()
                            .frame(width: fitted.width, height: fitted.height)
                            .position(x: origin.x + fitted.width  / 2,
                                      y: origin.y + fitted.height / 2)
                            .allowsHitTesting(false)
                    } else if let debugPath = loadDebugPath {
                        VStack(spacing: 8) {
                            Image(systemName: "photo.badge.exclamationmark")
                                .font(.system(size: 32))
                                .foregroundStyle(Color.saTextSecondary)
                            Text("Could not load image")
                                .font(.dmSans(13, weight: .semibold))
                                .foregroundStyle(Color.saTextSecondary)
                            Text(debugPath)
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundStyle(Color.saTextTertiary)
                                .multilineTextAlignment(.center)
                                .padding(.horizontal, 20)
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                        .allowsHitTesting(false)
                    }

                    // ── Region polygon borders + labels ───────────────
                    // (non-interactive; handles are separate below)
                    ForEach(Array(regions.enumerated()), id: \.element.id) { ri, region in
                        let cc = canvasCorners(of: region, origin: origin,
                                               scaleX: scaleX, scaleY: scaleY)
                        let col = palette[ri % palette.count]

                        // Polygon outline
                        Path { p in
                            p.move(to: cc[0])
                            p.addLine(to: cc[1])
                            p.addLine(to: cc[2])
                            p.addLine(to: cc[3])
                            p.closeSubpath()
                        }
                        .stroke(col, lineWidth: 2)
                        .allowsHitTesting(false)

                        // Label + delete button near TL corner
                        HStack(spacing: 4) {
                            Text(region.label)
                                .font(.dmSans(11, weight: .semibold))
                                .foregroundStyle(.white)
                                .padding(.horizontal, 6).padding(.vertical, 3)
                                .background(col)
                                .clipShape(RoundedRectangle(cornerRadius: 4))
                            Button { removeRegion(id: region.id) } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .font(.system(size: 13))
                                    .foregroundStyle(col)
                                    .background(Color.black.opacity(0.01))
                            }
                            .buttonStyle(.plain)
                        }
                        .padding(4)
                        .position(x: cc[0].x + 52, y: cc[0].y + 14)
                        .allowsHitTesting(!isDrawing)
                    }

                    // ── Corner handles — direct children of GeometryReader ──
                    // Mirrors PageDetectionStepView.CornerHandle exactly.
                    // Each handle has @Binding to its pixel corner and updates
                    // it directly — no closure, no intermediate wrapper view.
                    ForEach(regions.indices, id: \.self) { ri in
                        let col = palette[ri % palette.count]
                        ForEach(0..<4, id: \.self) { ci in
                            CornerHandle(
                                pixelPos: Binding(
                                    get: { regions[ri].corners[ci] },
                                    set: { newPx in
                                        var r = regions[ri]
                                        r.corners[ci] = newPx
                                        regions[ri] = r
                                    }
                                ),
                                origin: origin,
                                scaleX: scaleX,
                                scaleY: scaleY,
                                colour: col
                            )
                            .allowsHitTesting(!isDrawing)
                        }
                    }

                    // ── In-progress draw rectangle ────────────────────
                    if isDrawing, let s = drawStart, let c = drawCurrent {
                        Path { p in p.addRect(rectFrom(a: s, b: c)) }
                            .stroke(Color.saAmber500,
                                    style: StrokeStyle(lineWidth: 2, dash: [6]))
                            .allowsHitTesting(false)
                    }

                    // ── Draw gesture (transparent hit layer) ──────────
                    // allowsHitTesting(isDrawing) ensures this overlay only
                    // captures gestures when actively drawing — otherwise
                    // events fall through to the corner handles below.
                    Color.clear
                        .contentShape(Rectangle())
                        .gesture(
                            DragGesture(minimumDistance: 4)
                                .onChanged { v in
                                    if drawStart == nil { drawStart = v.startLocation }
                                    drawCurrent = v.location
                                }
                                .onEnded { v in
                                    guard let s = drawStart else { return }
                                    let r = rectFrom(a: s, b: v.location)
                                    let px = CGRect(
                                        x: (r.minX - origin.x) / scaleX,
                                        y: (r.minY - origin.y) / scaleY,
                                        width:  r.width  / scaleX,
                                        height: r.height / scaleY
                                    )
                                    if px.width > 10 && px.height > 10 {
                                        regions.append(EditableRegion(
                                            pixelRect: px,
                                            label: "Photo \(regions.count + 1)"
                                        ))
                                    }
                                    drawStart   = nil
                                    drawCurrent = nil
                                    isDrawing   = false
                                }
                        )
                        .allowsHitTesting(isDrawing)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .task { loadState() }
            .task(id: job.currentStep.rawValue) { loadState() }

            Divider()

            // ── Footer ─────────────────────────────────────────────────
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 10) {
                    Button {
                        isDrawing = true
                    } label: {
                        Label("Add Region", systemImage: "plus.rectangle.on.rectangle")
                            .font(.dmSans(12, weight: .medium))
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .tint(isDrawing ? Color.saAmber500 : nil)

                    Text("\(regions.count) region\(regions.count == 1 ? "" : "s")")
                        .font(.dmSans(12))
                        .foregroundStyle(Color.saTextSecondary)

                    Spacer()

                    if let err = errorMessage {
                        Text(err)
                            .font(.dmSans(11))
                            .foregroundStyle(Color.saError)
                    }

                    Button {
                        Task { await confirmAndRerun() }
                    } label: {
                        HStack(spacing: 6) {
                            if isRerunning { ProgressView().controlSize(.mini) }
                            Text(isRerunning ? "Starting…" : "Confirm & Re-run from Here")
                                .font(.dmSans(13, weight: .semibold))
                            if !isRerunning {
                                Image(systemName: "arrow.clockwise")
                                    .font(.system(size: 11, weight: .semibold))
                            }
                        }
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color.saAmber500)
                    .controlSize(.regular)
                    .disabled(isRerunning || regions.isEmpty)
                }

                Text("Drag any corner handle freely to adjust shape. Tap \"Add Region\" then draw to create a new one.")
                    .font(.dmSans(11))
                    .foregroundStyle(Color.saTextTertiary)
            }
            .padding(16)
            .background(Color.saCard)
        }
    }

    // MARK: - Load

    @MainActor
    private func loadState() {
        let debugDir = effectiveDebugFolder()
        let s = stem
        print("[PhotoSplitStepView] loadState — stem: \(s), debugDir: \(debugDir.path)")

        var loaded = false
        for name in ["\(s)_04_photo_boundaries.jpg", "\(s)_03_page_warped.jpg"] {
            let url = debugDir.appendingPathComponent(name)
            guard FileManager.default.fileExists(atPath: url.path) else { continue }
            if let data = try? Data(contentsOf: url), let img = NSImage(data: data) {
                pageImage = img
                loadDebugPath = nil
                loaded = true
                break
            }
        }
        if !loaded && pageImage == nil {
            loadDebugPath = debugDir.appendingPathComponent("\(s)_04_photo_boundaries.jpg").path
        }

        let jsonURL = debugDir.appendingPathComponent("\(s)_05_photo_detections.json")
        guard let data = try? Data(contentsOf: jsonURL),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let dets = root["detections"] as? [[String: Any]] else { return }

        regions = dets.enumerated().compactMap { idx, d in
            let label = "Photo \(idx + 1)"

            // Prefer corners key (free-form quad) if present
            if let rawCorners = d["corners"] as? [[Any]], rawCorners.count == 4 {
                let pts: [CGPoint] = rawCorners.compactMap { arr in
                    guard arr.count == 2,
                          let x = (arr[0] as? NSNumber).map({ CGFloat($0.doubleValue) }),
                          let y = (arr[1] as? NSNumber).map({ CGFloat($0.doubleValue) })
                    else { return nil }
                    return CGPoint(x: x, y: y)
                }
                if pts.count == 4 { return EditableRegion(corners: pts, label: label) }
            }

            // Fall back to bbox
            guard let raw = d["bbox"] as? [Any], raw.count == 4,
                  let x1 = (raw[0] as? NSNumber).map({ CGFloat($0.doubleValue) }),
                  let y1 = (raw[1] as? NSNumber).map({ CGFloat($0.doubleValue) }),
                  let x2 = (raw[2] as? NSNumber).map({ CGFloat($0.doubleValue) }),
                  let y2 = (raw[3] as? NSNumber).map({ CGFloat($0.doubleValue) })
            else { return nil }
            return EditableRegion(
                pixelRect: CGRect(x: x1, y: y1, width: x2 - x1, height: y2 - y1),
                label: label
            )
        }
    }

    // MARK: - Confirm & re-run

    @MainActor
    private func confirmAndRerun() async {
        isRerunning = true
        errorMessage = nil
        defer { isRerunning = false }

        let dets: [[String: Any]] = regions.map { r in
            let xs = r.corners.map { $0.x }
            let ys = r.corners.map { $0.y }
            return [
                "bbox": [
                    Int((xs.min() ?? 0).rounded()),
                    Int((ys.min() ?? 0).rounded()),
                    Int((xs.max() ?? 0).rounded()),
                    Int((ys.max() ?? 0).rounded()),
                ],
                "corners": r.corners.map { [Int($0.x.rounded()), Int($0.y.rounded())] },
                "confidence": 1.0,
                "region_type": "photo",
                "orientation": "unknown",
            ]
        }
        let payload: [String: Any] = [
            "photo_count": dets.count,
            "multi_blob": false,
            "detections": dets,
        ]

        let debugDir = effectiveDebugFolder()
        let jsonURL = debugDir.appendingPathComponent("\(stem)_05_photo_detections.json")
        do {
            try FileManager.default.createDirectory(at: debugDir, withIntermediateDirectories: true)
            let jsonData = try JSONSerialization.data(withJSONObject: payload, options: [.prettyPrinted])
            try jsonData.write(to: jsonURL)
        } catch {
            errorMessage = "Could not write detections: \(error.localizedDescription)"
            return
        }

        let runner = PipelineRunner(job: job)
        runner.reprocessFromPhotoSplit()
    }

    // MARK: - Helpers

    private func removeRegion(id: UUID) {
        regions.removeAll { $0.id == id }
        for i in regions.indices { regions[i].label = "Photo \(i + 1)" }
    }

    private func canvasCorners(of region: EditableRegion,
                                origin: CGPoint,
                                scaleX: CGFloat,
                                scaleY: CGFloat) -> [CGPoint] {
        region.corners.map {
            CGPoint(x: origin.x + $0.x * scaleX, y: origin.y + $0.y * scaleY)
        }
    }

    private func effectiveDebugFolder() -> URL {
        let s = AppSettings.shared
        return s.debugOutputEnabled
            ? s.debugFolder
            : RuntimeManager.shared.cliWorkingDirectory.appendingPathComponent("debug")
    }

    private func fitSize(_ imgSize: CGSize, in container: CGSize) -> CGSize {
        guard imgSize.width > 0, imgSize.height > 0,
              container.width > 0, container.height > 0 else { return container }
        let scale = min(container.width / imgSize.width, container.height / imgSize.height)
        return CGSize(width: imgSize.width * scale, height: imgSize.height * scale)
    }

    private func rectFrom(a: CGPoint, b: CGPoint) -> CGRect {
        CGRect(x: min(a.x, b.x), y: min(a.y, b.y),
               width: abs(b.x - a.x), height: abs(b.y - a.y))
    }

    private let palette: [Color] = [
        .saAmber500,
        Color(red: 0.18, green: 0.55, blue: 0.34),
        Color(red: 0.24, green: 0.48, blue: 0.78),
        Color(red: 0.80, green: 0.25, blue: 0.25),
        Color(red: 0.55, green: 0.25, blue: 0.78),
    ]
}

// MARK: - Region model

struct EditableRegion: Identifiable {
    let id = UUID()
    /// Corner points in pixel space: [TL, TR, BR, BL] (clockwise from top-left).
    var corners: [CGPoint]
    var label: String

    init(corners: [CGPoint], label: String) {
        self.corners = corners
        self.label = label
    }

    init(pixelRect: CGRect, label: String) {
        self.corners = [
            CGPoint(x: pixelRect.minX, y: pixelRect.minY),
            CGPoint(x: pixelRect.maxX, y: pixelRect.minY),
            CGPoint(x: pixelRect.maxX, y: pixelRect.maxY),
            CGPoint(x: pixelRect.minX, y: pixelRect.maxY),
        ]
        self.label = label
    }
}

// MARK: - Corner handle
//
// Mirrors PageDetectionStepView.CornerHandle exactly:
// • @Binding var pixelPos: CGPoint — direct binding, updated in onChanged.
// • .position(canvasPos) — hit area follows the dot.
// • DragGesture with no coordinateSpace — works correctly because the handle
//   is a direct child of GeometryReader (same as PageDetectionStepView).

private struct CornerHandle: View {
    @Binding var pixelPos: CGPoint
    let origin: CGPoint
    let scaleX: CGFloat
    let scaleY: CGFloat
    let colour: Color

    private var canvasPos: CGPoint {
        CGPoint(x: origin.x + pixelPos.x * scaleX,
                y: origin.y + pixelPos.y * scaleY)
    }

    var body: some View {
        ZStack {
            Circle()
                .fill(colour)
                .frame(width: 20, height: 20)
            Circle()
                .strokeBorder(Color.white, lineWidth: 2)
                .frame(width: 20, height: 20)
        }
        .shadow(color: .black.opacity(0.4), radius: 4)
        .position(canvasPos)
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { v in
                    pixelPos = CGPoint(
                        x: (v.location.x - origin.x) / scaleX,
                        y: (v.location.y - origin.y) / scaleY
                    )
                }
        )
    }
}
