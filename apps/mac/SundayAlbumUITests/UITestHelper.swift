import XCTest

// MARK: - Launch helper

extension XCUIApplication {
    /// Launch the app with MOCK_DATA pre-populated and the Python subprocess
    /// skipped (UITEST_MODE).  The mock library contains four jobs including
    /// "IMG_cave_normal.HEIC" which is fully complete.
    static func launchForUITests() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchEnvironment["MOCK_DATA"]   = "1"
        app.launchEnvironment["UITEST_MODE"] = "1"
        app.launch()
        return app
    }
}

// MARK: - Navigation helpers

extension XCUIApplication {
    /// Double-click the library card for a job to open its step-detail view.
    /// `inputName` is the exact job.inputName string (e.g. "IMG_cave_normal.HEIC").
    @discardableResult
    func openJob(inputName: String, timeout: TimeInterval = 10) -> Bool {
        let card = anyDescendant(identifier: "job-card-\(inputName)")
        guard card.waitForExistence(timeout: timeout) else { return false }
        card.doubleClick()
        return true
    }

    /// Click a row in the step tree by its label (e.g. "Color Correction").
    @discardableResult
    func selectTreeRow(label: String, timeout: TimeInterval = 5) -> Bool {
        let row = anyDescendant(identifier: "tree-row-\(label)")
        guard row.waitForExistence(timeout: timeout) else { return false }
        row.click()
        return true
    }

    /// Find the first descendant with a matching accessibility identifier,
    /// regardless of element type.  SwiftUI VStack/HStack containers register
    /// as .group in the accessibility tree, so `otherElements[id]` misses them.
    func anyDescendant(identifier: String) -> XCUIElement {
        descendants(matching: .any)
            .matching(NSPredicate(format: "identifier == %@", identifier))
            .firstMatch
    }
}

// MARK: - Existence assertions (XCTest convenience)

extension XCTestCase {
    func assertExists(_ element: XCUIElement, timeout: TimeInterval = 5,
                      _ message: String = "", file: StaticString = #file, line: UInt = #line) {
        XCTAssertTrue(element.waitForExistence(timeout: timeout),
                      message.isEmpty ? "\(element.identifier) should exist" : message,
                      file: file, line: line)
    }
}
