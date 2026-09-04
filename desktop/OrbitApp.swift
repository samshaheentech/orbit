// Orbit desktop shell. One window around the local webapp, a menu bar item, notifications.
// Build: bash desktop/build.sh   (uses swiftc from the Xcode Command Line Tools; no Xcode project)
import AppKit
import WebKit
import UserNotifications

let ORBIT_URL = URL(string: ProcessInfo.processInfo.environment["ORBIT_URL"] ?? "http://localhost:4242")!
let ORBIT_HOME = ProcessInfo.processInfo.environment["ORBIT_HOME"] ?? (NSHomeDirectory() + "/git/orbit")

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var status: NSStatusItem!
    var timer: Timer?
    var lastBriefTs = ""
    var lastFireTs = ""

    func applicationDidFinishLaunching(_ note: Notification) {
        NSApp.setActivationPolicy(.regular)
        buildMenu()
        buildWindow()
        buildStatusItem()
        if Bundle.main.bundleIdentifier != nil {
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, _ in }
        }
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true); return true
    }

    // MARK: window
    func buildWindow() {
        let cfg = WKWebViewConfiguration()
        cfg.preferences.setValue(true, forKey: "developerExtrasEnabled")
        web = WKWebView(frame: .zero, configuration: cfg)
        web.navigationDelegate = self
        web.uiDelegate = self
        web.setValue(false, forKey: "drawsBackground")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1180, height: 820),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable, .fullSizeContentView],
                          backing: .buffered, defer: false)
        window.title = "Orbit"
        window.titlebarAppearsTransparent = true
        window.appearance = NSAppearance(named: .darkAqua)
        window.backgroundColor = NSColor(red: 0.059, green: 0.067, blue: 0.078, alpha: 1)
        window.minSize = NSSize(width: 720, height: 520)
        window.contentView = web
        window.setFrameAutosaveName("OrbitMain")
        window.makeKeyAndOrderFront(nil)
        web.load(URLRequest(url: ORBIT_URL))
        NSApp.activate(ignoringOtherApps: true)
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) { showOffline() }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) { showOffline() }
    func showOffline() {
        let html = """
        <body style="background:#0f1114;color:#a7a399;font:15px -apple-system;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
        <div style="max-width:420px;line-height:1.6"><b style="color:#ebe8e1">Orbit's server isn't running.</b><br>
        Start it with <code>launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sam.orbit-server.plist</code>
        or run <code>bash install.sh</code> again. Press ⌘R to retry.</div></body>
        """
        web.loadHTMLString(html, baseURL: nil)
    }

    // external links open in the browser; localhost stays inside
    func webView(_ webView: WKWebView, decidePolicyFor action: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        if let url = action.request.url, action.navigationType == .linkActivated, url.host != ORBIT_URL.host {
            NSWorkspace.shared.open(url); decisionHandler(.cancel); return
        }
        decisionHandler(.allow)
    }
    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration, for action: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = action.request.url { NSWorkspace.shared.open(url) }
        return nil
    }
    // microphone for the Sim's Dictate button
    @available(macOS 12.0, *)
    func webView(_ webView: WKWebView, requestMediaCapturePermissionFor origin: WKSecurityOrigin, initiatedByFrame frame: WKFrameInfo, type: WKMediaCaptureType, decisionHandler: @escaping (WKPermissionDecision) -> Void) {
        decisionHandler(.grant)
    }
    // JS alert/confirm/prompt (the window sync uses prompt)
    func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
        let a = NSAlert(); a.messageText = message; a.runModal(); completionHandler()
    }
    func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?, initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (String?) -> Void) {
        let a = NSAlert(); a.messageText = prompt; a.addButton(withTitle: "OK"); a.addButton(withTitle: "Cancel")
        let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 240, height: 24)); field.stringValue = defaultText ?? ""
        a.accessoryView = field; a.window.initialFirstResponder = field
        completionHandler(a.runModal() == .alertFirstButtonReturn ? field.stringValue : nil)
    }

    // MARK: menu bar
    func buildStatusItem() {
        status = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        status.button?.title = "◌ Orbit"
        let m = NSMenu()
        m.addItem(withTitle: "Open Orbit", action: #selector(openWindow), keyEquivalent: "o")
        m.addItem(withTitle: "Run a fire now", action: #selector(runFire), keyEquivalent: "")
        m.addItem(withTitle: "Pause schedule", action: #selector(pauseSchedule), keyEquivalent: "")
        m.addItem(withTitle: "Resume schedule", action: #selector(resumeSchedule), keyEquivalent: "")
        m.addItem(NSMenuItem.separator())
        m.addItem(withTitle: "Quit Orbit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        status.menu = m
    }
    func buildMenu() {
        let main = NSMenu()
        let app = NSMenuItem(); main.addItem(app)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Reload", action: #selector(reload), keyEquivalent: "r")
        appMenu.addItem(withTitle: "Hide Orbit", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        appMenu.addItem(withTitle: "Quit Orbit", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        app.submenu = appMenu
        let edit = NSMenuItem(); main.addItem(edit)
        let editMenu = NSMenu(title: "Edit")
        editMenu.addItem(withTitle: "Cut", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "Copy", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "Paste", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "Select All", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        edit.submenu = editMenu
        NSApp.mainMenu = main
    }
    @objc func openWindow() { window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true) }
    @objc func reload() { web.load(URLRequest(url: ORBIT_URL)) }
    @objc func runFire() { shell("/bin/bash", [ORBIT_HOME + "/run.sh"], manual: true) }
    @objc func pauseSchedule() { shell("/bin/launchctl", ["bootout", "gui/\(getuid())/com.sam.orbit-runner"]) }
    @objc func resumeSchedule() { shell("/bin/launchctl", ["bootstrap", "gui/\(getuid())", NSHomeDirectory() + "/Library/LaunchAgents/com.sam.orbit-runner.plist"]) }
    func shell(_ path: String, _ args: [String], manual: Bool = false) {
        let p = Process(); p.executableURL = URL(fileURLWithPath: path); p.arguments = args
        var env = ProcessInfo.processInfo.environment; env["ORBIT_HOME"] = ORBIT_HOME; if manual { env["ORBIT_MANUAL"] = "1" }; p.environment = env
        try? p.run()
    }

    // MARK: polling: next fire, window countdown, new brief, blocked tasks
    func refresh() {
        get("/api/health") { ok, _ in
            if !ok { DispatchQueue.main.async { self.status.button?.title = "◌ Orbit offline" }; return }
            self.get("/data/window.json") { _, data in
                var title = "◌ " + self.nextFire()
                if let d = data, let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                   let synced = j["synced"] as? Bool, synced, let left = j["minutes_left"] as? Int {
                    title += "  \(left / 60)h \(String(format: "%02d", left % 60))m"
                }
                DispatchQueue.main.async { self.status.button?.title = title }
            }
            self.get("/api/events") { _, data in
                guard let d = data, let arr = try? JSONSerialization.jsonObject(with: d) as? [[String: Any]] else { return }
                if let b = arr.last(where: { ($0["type"] as? String) == "brief" }), let ts = b["ts"] as? String, ts != self.lastBriefTs {
                    if !self.lastBriefTs.isEmpty { self.notify("Morning brief is ready", "Open Orbit to read it.") }
                    self.lastBriefTs = ts
                }
                if let f = arr.last(where: { ($0["type"] as? String) == "fire_end" }), let ts = f["ts"] as? String, ts != self.lastFireTs {
                    if !self.lastFireTs.isEmpty, let note = f["note"] as? String { self.notify("Fire finished", note) }
                    self.lastFireTs = ts
                }
                if let blocked = arr.last(where: { ($0["type"] as? String) == "task_blocked" }), let ts = blocked["ts"] as? String,
                   ts > self.lastFireTs, let task = blocked["task"] as? String {
                    self.notify("Task blocked", task + ": " + ((blocked["note"] as? String) ?? "see the brief"))
                }
            }
        }
    }
    func nextFire() -> String {
        let fires = [22, 3].sorted()
        let h = Calendar.current.component(.hour, from: Date())
        let n = fires.first { $0 > h } ?? fires[0]
        return String(format: "%02d:00", n)
    }
    func get(_ path: String, _ done: @escaping (Bool, Data?) -> Void) {
        var req = URLRequest(url: ORBIT_URL.appendingPathComponent(path)); req.timeoutInterval = 5
        URLSession.shared.dataTask(with: req) { data, resp, _ in
            let ok = (resp as? HTTPURLResponse)?.statusCode == 200
            done(ok, data)
        }.resume()
    }
    func notify(_ title: String, _ body: String) {
        guard Bundle.main.bundleIdentifier != nil else { return }
        let c = UNMutableNotificationContent(); c.title = title; c.body = body
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: UUID().uuidString, content: c, trigger: nil))
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
