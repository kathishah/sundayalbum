import SwiftUI
import AppKit

// MARK: - Colors

extension Color {
    // ── Amber — primary accent ───────────────────────────────────────────────
    static let saAmber50  = Color(red: 1.000, green: 0.973, blue: 0.941)
    static let saAmber100 = Color(red: 0.996, green: 0.941, blue: 0.863)
    static let saAmber200 = Color(red: 0.992, green: 0.878, blue: 0.753)
    static let saAmber400 = Color(red: 0.984, green: 0.749, blue: 0.141)
    static let saAmber500 = Color(red: 0.851, green: 0.467, blue: 0.024)
    static let saAmber600 = Color(red: 0.706, green: 0.325, blue: 0.035)
    static let saAmber700 = Color(red: 0.565, green: 0.243, blue: 0.043)

    // ── Stone — neutrals ─────────────────────────────────────────────────────
    static let saStone50  = Color(red: 0.980, green: 0.980, blue: 0.976)
    static let saStone100 = Color(red: 0.961, green: 0.961, blue: 0.957)
    static let saStone200 = Color(red: 0.906, green: 0.898, blue: 0.894)
    static let saStone300 = Color(red: 0.820, green: 0.812, blue: 0.804)
    static let saStone400 = Color(red: 0.659, green: 0.635, blue: 0.620)
    static let saStone500 = Color(red: 0.471, green: 0.443, blue: 0.424)
    static let saStone600 = Color(red: 0.341, green: 0.325, blue: 0.306)
    static let saStone700 = Color(red: 0.267, green: 0.251, blue: 0.235)
    static let saStone800 = Color(red: 0.180, green: 0.161, blue: 0.149)
    static let saStone900 = Color(red: 0.110, green: 0.098, blue: 0.090)
    static let saStone950 = Color(red: 0.047, green: 0.039, blue: 0.035)

    // ── Status ───────────────────────────────────────────────────────────────
    static let saSuccess = Color(red: 0.086, green: 0.639, blue: 0.290)
    static let saError   = Color(red: 0.863, green: 0.149, blue: 0.149)

    // ── Adaptive helper ──────────────────────────────────────────────────────
    /// Returns a color that switches between `light` and `dark` based on the
    /// current macOS appearance (Aqua vs. Dark Aqua).
    static func dynamic(light: Color, dark: Color) -> Color {
        Color(NSColor(name: nil) { appearance in
            appearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
                ? NSColor(dark) : NSColor(light)
        })
    }

    // ── Semantic adaptive tokens ─────────────────────────────────────────────
    // Page / window background
    static let saBackground = dynamic(
        light: .white,
        dark:  .black
    )
    // Card surfaces (album page cards, panels)
    static let saCard = dynamic(
        light: Color(red: 0.941, green: 0.937, blue: 0.933),  // soft warm light grey
        dark:  Color(red: 0.137, green: 0.122, blue: 0.114)   // soft dark grey
    )
    // Inset surfaces (step strip, comparison pane, results pane)
    static let saSurface = dynamic(
        light: Color(red: 0.961, green: 0.961, blue: 0.957),  // stone-100, slightly lighter than card
        dark:  Color(red: 0.094, green: 0.082, blue: 0.075)   // between black and card
    )
    // Card / panel borders
    static let saBorder = dynamic(
        light: Color(red: 0.859, green: 0.851, blue: 0.843),  // subtle on grey cards
        dark:  Color(red: 0.216, green: 0.196, blue: 0.184)   // warm dark border
    )
    // Card shadow — dark drop in light mode, soft white glow in dark mode
    static let saShadow = dynamic(
        light: Color(red: 0.110, green: 0.098, blue: 0.090, opacity: 0.45),
        dark:  Color(red: 1.000, green: 1.000, blue: 1.000, opacity: 0.12)
    )

    // ── Adaptive text tokens ─────────────────────────────────────────────────
    static let saTextPrimary = dynamic(
        light: Color(red: 0.267, green: 0.251, blue: 0.235),  // stone-700
        dark:  Color(red: 0.961, green: 0.961, blue: 0.957)   // stone-100
    )
    static let saTextSecondary = dynamic(
        light: Color(red: 0.471, green: 0.443, blue: 0.424),  // stone-500
        dark:  Color(red: 0.659, green: 0.635, blue: 0.620)   // stone-400
    )
    static let saTextTertiary = dynamic(
        light: Color(red: 0.659, green: 0.635, blue: 0.620),  // stone-400
        dark:  Color(red: 0.471, green: 0.443, blue: 0.424)   // stone-500
    )
}

// MARK: - Typography

extension Font {
    static func fraunces(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .custom("Fraunces", size: size).weight(weight)
    }

    static func dmSans(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        .custom("DM Sans", size: size).weight(weight)
    }

    static func jetbrainsMono(_ size: CGFloat) -> Font {
        .custom("JetBrains Mono", size: size)
    }
}

// MARK: - Animation

extension Animation {
    /// Standard ease — 200ms, smooth deceleration
    static let saStandard = Animation.timingCurve(0.16, 1, 0.3, 1, duration: 0.2)
    /// Panel slide — 350ms
    static let saSlide    = Animation.timingCurve(0.16, 1, 0.3, 1, duration: 0.35)
    /// Signature glare reveal — 600ms
    static let saReveal   = Animation.timingCurve(0.16, 1, 0.3, 1, duration: 0.6)
    /// Spring for hover/select feedback
    static let saSpring   = Animation.spring(response: 0.4, dampingFraction: 0.6)
}
