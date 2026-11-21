import json
from datetime import datetime
from pathlib import Path


class BugReportWriter:
    """Write JSON and HTML reports for analyzed AYKSA test failures."""

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)

    def write(self, analysis):

        self.output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = (
            self.output_dir
            / f"ayksa_failure_analysis_{timestamp}.json"
        )
        html_path = (
            self.output_dir
            / f"ayksa_failure_analysis_{timestamp}.html"
        )

        with json_path.open("w", encoding="utf-8") as file:
            json.dump(
                analysis,
                file,
                indent=2,
                ensure_ascii=False
            )

        html_path.write_text(
            self.render_html(analysis),
            encoding="utf-8"
        )

        return json_path, html_path

    def render_html(self, analysis):

        summary = analysis["summary"]
        dashboard_data = {
            "summary": summary,
            "modules": analysis.get("modules", []),
            "test_cases": analysis.get("test_cases", []),
            "source_execution_report": analysis.get(
                "source_execution_report"
            ),
            "source_test_catalog": analysis.get("source_test_catalog"),
            "application_url": analysis.get("application_url"),
            "execution_time": analysis.get("execution_time"),
            "analysis_generated_at": analysis.get("analysis_generated_at"),
            "browser_errors": analysis.get("browser_errors", []),
        }
        embedded_json = json.dumps(
            dashboard_data,
            ensure_ascii=False
        ).replace("<", "\\u003c")

        page = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AYKSA QA Test Dashboard</title>
  <style>
    :root { color-scheme: light; font-family: "Segoe UI", Arial, sans-serif; color: #17212b; background: #f3f6fa; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    header { color: #fff; background: linear-gradient(120deg, #102b46, #176b70); padding: 26px max(22px, calc((100% - 1400px) / 2)); }
    header h1 { margin: 0; font-size: 1.8rem; }
    header p { margin: 8px 0 0; color: #d3e8ec; }
    main { max-width: 1400px; margin: auto; padding: 22px; }
    .notice { margin: 16px 0; padding: 13px 16px; border-left: 4px solid #d59b00; border-radius: 5px; background: #fff7db; }
    .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 12px; margin: 20px 0; }
    .metric, .panel, .module-card, .test-card { background: #fff; border: 1px solid #dce4ec; border-radius: 9px; box-shadow: 0 2px 6px #152b4010; }
    .metric { padding: 16px; display: grid; gap: 5px; }
    .metric strong { font-size: 1.7rem; }
    .metric span, .muted { color: #596a79; font-size: .9rem; }
    .overall-progress, .module-progress { overflow: hidden; display: flex; border-radius: 99px; background: #e7edf2; }
    .overall-progress { height: 14px; margin: 8px 0; }
    .module-progress { height: 9px; margin: 10px 0 5px; }
    .progress-pass { background: #27945b; }
    .progress-fail { background: #d54b43; }
    .progress-pending { background: #b6c1cb; }
    .progress-label, .chart-legend { color: #536575; font-size: .82rem; }
    .chart-legend { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-top: 7px; }
    .legend-dot { display: inline-block; width: 9px; height: 9px; margin-right: 4px; border-radius: 50%; }
    .module-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
    .module-card { padding: 14px; }
    .module-card h3 { margin: 0 0 7px; color: #153b5b; }
    .module-counts { color: #536575; font-size: .88rem; line-height: 1.7; }
    .coverage-good { color: #17653b; }
    .coverage-missing { color: #8a5c00; }
    .panel { padding: 18px; margin: 18px 0; }
    .panel h2 { margin: 0 0 14px; color: #153b5b; }
    .filters { display: grid; grid-template-columns: 2fr repeat(4, minmax(145px, 1fr)); gap: 10px; }
    input, select { width: 100%; padding: 10px 11px; border: 1px solid #bbc9d6; border-radius: 6px; background: white; color: #17212b; font: inherit; }
    .result-count { margin: 14px 0; color: #45596a; }
    .review-layout { display: grid; grid-template-columns: minmax(250px, 360px) minmax(0, 1fr); gap: 14px; align-items: start; margin-top: 16px; }
    .test-list { display: grid; gap: 7px; max-height: 72vh; overflow: auto; }
    .test-pick { width: 100%; text-align: left; padding: 11px; border: 1px solid #dce4ec; border-radius: 7px; background: #fff; cursor: pointer; color: #17212b; font: inherit; }
    .test-pick[aria-current="true"] { border-color: #176b70; box-shadow: inset 3px 0 #176b70; background: #f0f8f7; }
    .test-pick strong, .test-pick span { display: block; }
    .test-pick span { margin-top: 5px; font-size: .82rem; color: #596a79; }
    .test-pick .pick-meta { display: flex; flex-wrap: wrap; gap: 5px 10px; }
    .test-pick .pick-id { color: #153b5b; font-weight: 750; }
    .test-detail { min-height: 420px; padding: 20px; }
    .test-detail h3 { margin: 12px 0; color: #183e5c; font-size: 1.25rem; }
    .test-head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
    .case-nav { display: flex; align-items: center; gap: 8px; margin: 12px 0; }
    .case-nav button, .copy-command { padding: 8px 11px; border: 1px solid #b9c9d6; border-radius: 6px; background: #fff; cursor: pointer; color: #153b5b; font: inherit; }
    .case-nav button:disabled { opacity: .5; cursor: not-allowed; }
    .badges { display: flex; flex-wrap: wrap; gap: 6px; }
    .badge { display: inline-block; border-radius: 99px; padding: 4px 9px; background: #e9eef3; color: #33495b; font-size: .78rem; font-weight: 650; }
    .status-pass { background: #e0f5e9; color: #17653b; }
    .status-fail { background: #ffe5e2; color: #9c2c22; }
    .status-not-executed { background: #edf0f3; color: #4b5a68; }
    .status-skipped { background: #fff1d2; color: #77520a; }
    .test-data { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 9px 18px; margin-top: 12px; }
    .test-data div { overflow-wrap: anywhere; }
    .test-data strong { display: block; color: #42586b; font-size: .8rem; margin-bottom: 3px; }
    .failure { margin-top: 12px; padding: 14px; background: #fff5f4; border: 1px solid #f1c6c2; border-radius: 6px; }
    .analysis { margin-top: 14px; padding: 14px; background: #f6f9fc; border: 1px solid #dce4ec; border-radius: 6px; }
    .analysis h4 { margin: 0 0 10px; }
    .run-command { margin-top: 14px; padding: 13px; background: #edf5f8; border-radius: 6px; }
    .run-command code { display: block; margin: 8px 0; padding: 10px; overflow-wrap: anywhere; background: #fff; border: 1px solid #dce4ec; border-radius: 5px; }
    .failure p { margin: 6px 0; }
    a { color: #075da8; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; font: inherit; margin: 4px 0; }
    .empty { padding: 28px; text-align: center; color: #596a79; }
    .source { overflow-wrap: anywhere; }
    @media (max-width: 900px) { .review-layout { grid-template-columns: 1fr; } .test-list { max-height: 260px; } }
    @media (max-width: 760px) { main { padding: 14px; } .filters { grid-template-columns: 1fr 1fr; } .filters input { grid-column: 1 / -1; } }
    @media (max-width: 460px) { .filters { grid-template-columns: 1fr; } .filters input { grid-column: auto; } }
  </style>
</head>
<body>
  <header>
    <h1>AYKSA QA Test Dashboard</h1>
    <p>Test cases, execution results, and issue triage grouped by application functionality.</p>
    <p><a id="applicationLink" target="_blank" rel="noopener" style="color:#fff">Open AYKSA application</a></p>
  </header>
  <main>
    <div class="notice"><strong>Review note:</strong> failed checks are evidence for triage, not automatically confirmed application bugs. Reproduce potential UI issues manually before logging a defect.</div>
    <section class="summary" id="summary"></section>
    <div id="overallProgress"></div>
    <div class="chart-legend" aria-label="Execution result chart legend">
    <span><i class="legend-dot progress-pass"></i>Passed</span>
    <span><i class="legend-dot progress-fail"></i>Failed</span>
    <span><i class="legend-dot progress-pending"></i>Not executed</span>
    </div>
    <section class="panel">
      <h2>AYKSA functionality overview</h2>
      <div class="module-grid" id="modules"></div>
    </section>
    <section class="panel">
      <h2>All test cases and findings</h2>
      <div class="filters">
        <input id="search" type="search" placeholder="Search test ID, page, title, result, or finding">
        <select id="moduleFilter" aria-label="Filter by AYKSA functionality"><option value="">All functionalities</option></select>
        <select id="statusFilter" aria-label="Filter by execution status"><option value="">All statuses</option></select>
        <select id="categoryFilter" aria-label="Filter by test category"><option value="">All test categories</option></select>
        <select id="sortFilter" aria-label="Sort test cases">
          <option value="id">Test ID (ascending)</option>
          <option value="priority">Priority (highest first)</option>
          <option value="status">Failures first</option>
          <option value="module">Functionality (A-Z)</option>
        </select>
      </div>
      <p class="result-count" id="resultCount" aria-live="polite"></p>
      <p class="muted">Test IDs are shown in numeric order by default. Execution sequence is listed in each test detail and is based on priority.</p>
      <div class="case-nav">
        <button id="previousCase" type="button">Previous test</button>
        <span id="casePosition" aria-live="polite"></span>
        <button id="nextCase" type="button">Next test</button>
      </div>
      <div class="review-layout">
        <nav class="test-list" id="testCases" aria-label="Test case list"></nav>
        <section class="panel test-detail" id="caseDetail" aria-live="polite"></section>
      </div>
    </section>
    <section class="panel">
      <h2>Run details</h2>
      <p>Execution time: <span id="executionTime"></span></p>
      <p>Analysis generated: <span id="generatedAt"></span></p>
      <p class="source">Execution report: <span id="executionSource"></span></p>
      <p class="source">Test catalog: <span id="catalogSource"></span></p>
      <div id="browserErrors"></div>
    </section>
  </main>
  <script>
    window.AYKSA_QA_DATA = __DASHBOARD_DATA__;
    const data = window.AYKSA_QA_DATA;
    const escapeHtml = value => String(value ?? "Not recorded").replace(/[&<>"']/g, char => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[char]));
    const cases = Array.isArray(data.test_cases) ? data.test_cases : [];
    const modules = Array.isArray(data.modules) ? data.modules : [];
    const statusClass = status => {
      const normalized = String(status || "").toLowerCase().replace(/[^a-z]+/g, "-");
      if (normalized === "pass") return "status-pass";
      if (normalized === "fail") return "status-fail";
      if (normalized === "not-executed") return "status-not-executed";
      return "status-skipped";
    };
    const issueLabel = test => {
      if (!test.finding_id) return "";
      const labels = {
        AUTOMATION_LOCATOR: "Automation locator issue",
        EXECUTION_OR_ENVIRONMENT: "Execution/environment issue",
        POTENTIAL_UI_BEHAVIOR: "Potential UI issue",
        UNCLASSIFIED_FAILURE: "Needs review"
      };
      return labels[test.finding_classification] || "Needs review";
    };
    const screenshotLink = path => {
      if (!path) return "";
      const normalized = String(path).replace(/\\\\/g, "/");
      const href = /^file:/i.test(normalized) ? normalized : "file:///" + normalized.replace(/^\\/+/, "");
      return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">Open test screenshot</a>`;
    };
    const renderSummary = () => {
      const status = cases.reduce((counts, test) => {
        const key = String(test.execution_status || "NOT EXECUTED").toUpperCase();
        counts[key] = (counts[key] || 0) + 1;
        return counts;
      }, {});
      const metrics = [
        ["Test cases", cases.length],
        ["Passed", status.PASS || 0],
        ["Failed checks", status.FAIL || 0],
        ["Not executed", status["NOT EXECUTED"] || 0],
        ["Potential UI issues", data.summary.potential_ui_issues || 0],
        ["Automation locator issues", data.summary.automation_locator_issues || 0],
        ["Confirmed bugs", data.summary.confirmed_bugs || 0]
      ];
      document.getElementById("summary").innerHTML = metrics.map(([label, value]) =>
        `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`
      ).join("");
      const total = cases.length;
      const passed = status.PASS || 0;
      const failed = status.FAIL || 0;
      const pending = Math.max(0, total - passed - failed);
      const percent = count => total ? (count / total * 100) : 0;
      document.getElementById("overallProgress").innerHTML = `
        <div class="progress-label">Execution overview: ${passed} passed · ${failed} failed · ${pending} not executed</div>
        <div class="overall-progress" role="img" aria-label="${passed} passed, ${failed} failed, ${pending} not executed">
          <span class="progress-pass" style="width:${percent(passed)}%"></span>
          <span class="progress-fail" style="width:${percent(failed)}%"></span>
          <span class="progress-pending" style="width:${percent(pending)}%"></span>
        </div>`;
    };
    const renderModules = () => {
      document.getElementById("modules").innerHTML = modules.map(module => {
        const total = Number(module.total_test_cases || 0);
        const passed = Number(module.passed_checks || 0);
        const failed = Number(module.failed_checks || 0);
        const pending = Math.max(
          0,
          Number(module.not_executed_checks || 0),
          total - passed - failed
        );
        const percent = count => total ? (count / total * 100) : 0;
        const coverageStatus = String(
          module.coverage_status || "not_recorded"
        ).replaceAll("_", " ");
        const coverageClass = module.coverage_status === "discovered"
          ? "coverage-good"
          : "coverage-missing";
        return `<article class="module-card">
          <h3>${escapeHtml(module.module)}</h3>
          <div class="module-counts ${coverageClass}">
            Discovery: ${escapeHtml(coverageStatus)} · ${escapeHtml(module.discovered_pages || 0)} page(s)
          </div>
          <div class="module-progress" role="img" aria-label="${passed} passed, ${failed} failed, ${pending} not executed">
            <span class="progress-pass" style="width:${percent(passed)}%"></span>
            <span class="progress-fail" style="width:${percent(failed)}%"></span>
            <span class="progress-pending" style="width:${percent(pending)}%"></span>
          </div>
          <div class="module-counts">
            ${escapeHtml(total)} total · ${escapeHtml(passed)} passed ·
            ${escapeHtml(failed)} failed · ${escapeHtml(pending)} not executed
          </div>
          <div class="module-counts">
            ${escapeHtml(module.potential_ui_issues || 0)} potential UI ·
            ${escapeHtml(module.automation_locator_issues || 0)} locator issues
          </div>
        </article>`;
      }).join("");
    };
    const renderOptions = (id, values) => {
      const select = document.getElementById(id);
      [...new Set(values.filter(Boolean))].sort().forEach(value => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      });
    };
    const safeApplicationUrl = value => {
      try {
        const url = new URL(value || "", window.location.href);
        return ["https:", "http:"].includes(url.protocol) ? url.href : "";
      } catch {
        return "";
      }
    };
    const renderFindingAnalysis = test => {
      const finding = test.finding_analysis;
      if (!finding) {
        return `<div class="analysis"><h4>Bug analysis</h4>
          <p>${test.execution_status === "FAIL"
            ? "No linked finding analysis was generated for this result."
            : "No failed result is linked to this test in the selected execution."}</p>
        </div>`;
      }
      const steps = Array.isArray(finding.reproduction_steps)
        ? finding.reproduction_steps.map(step => `<li>${escapeHtml(step)}</li>`).join("")
        : "";
      return `<div class="analysis">
        <h4>Individual bug / failure analysis</h4>
        <div class="badges">
          <span class="badge">${escapeHtml(finding.finding_id)}</span>
          <span class="badge">${escapeHtml(issueLabel(test))}</span>
          <span class="badge">${escapeHtml(finding.classification)}</span>
          <span class="badge">${escapeHtml(finding.confirmed_bug ? "Confirmed bug" : "Not confirmed")}</span>
        </div>
        <p><strong>Triage:</strong> ${escapeHtml(finding.triage_status)}</p>
        <p><strong>Expected:</strong> ${escapeHtml(finding.expected_result || test.expected_result)}</p>
        <p><strong>Observed:</strong> ${escapeHtml(finding.observed_result)}</p>
        <p><strong>Suggested severity:</strong> ${escapeHtml(finding.suggested_severity)}</p>
        ${finding.related_finding_ids?.length
          ? `<p><strong>Related repeated findings:</strong> ${finding.related_finding_ids.map(escapeHtml).join(", ")}</p>` : ""}
        ${steps ? `<h5>Manual reproduction steps</h5><ol>${steps}</ol>` : ""}
        <p class="notice">Automation findings need review. A failed check is not a confirmed application bug until reproduced.</p>
      </div>`;
    };
    let filteredCases = [];
    let selectedTestId = null;
    const testIdNumber = test => {
      const match = String(test.test_id || "").match(/(\\d+)$/);
      return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER;
    };
    const priorityRank = test => ({
      critical: 4,
      high: 3,
      medium: 2,
      low: 1
    }[String(test.calculated_priority || test.priority || "").toLowerCase()] || 0);
    const compareCases = (left, right, mode) => {
      if (mode === "priority") {
        return priorityRank(right) - priorityRank(left)
          || testIdNumber(left) - testIdNumber(right);
      }
      if (mode === "status") {
        const rank = test => ({
          FAIL: 0,
          "NOT EXECUTED": 1,
          PASS: 2
        }[String(test.execution_status || "NOT EXECUTED").toUpperCase()] ?? 3);
        return rank(left) - rank(right)
          || testIdNumber(left) - testIdNumber(right);
      }
      if (mode === "module") {
        return String(left.module || "").localeCompare(String(right.module || ""))
          || testIdNumber(left) - testIdNumber(right);
      }
      return testIdNumber(left) - testIdNumber(right);
    };
    const renderCaseDetail = test => {
      if (!test) {
        document.getElementById("caseDetail").innerHTML =
          '<div class="empty">No test case matches the selected filters.</div>';
        document.getElementById("casePosition").textContent = "0 of 0";
        document.getElementById("previousCase").disabled = true;
        document.getElementById("nextCase").disabled = true;
        return;
      }
      const status = String(test.execution_status || "NOT EXECUTED").toUpperCase();
      const finding = test.finding_analysis;
      const applicationUrl = safeApplicationUrl(
        test.page_url || test.application_url || data.application_url
      );
      const appLink = applicationUrl
        ? `<a href="${escapeHtml(applicationUrl)}" target="_blank" rel="noopener">Open AYKSA at the recorded page</a>`
        : "Application URL was not recorded for this test.";
      const reportArg = data.source_test_catalog
        ? ` --report '${String(data.source_test_catalog).replace(/'/g, "''")}'`
        : "";
      const command = `.\\\\venv\\\\Scripts\\\\python.exe automation\\\\test_executor.py${reportArg} --test-id ${test.test_id} --analyze`;
      const executedMessage = test.execution_message || (
        status === "NOT EXECUTED" ? "This case was not executed in the selected run." : "No execution message was recorded."
      );
      document.getElementById("caseDetail").innerHTML = `
        <div class="test-head">
          <div class="badges">
            <span class="badge ${statusClass(status)}">${escapeHtml(status)}</span>
            <span class="badge">${escapeHtml(test.module)}</span>
            <span class="badge">${escapeHtml(test.category || "Uncategorized")}</span>
            <span class="badge">${escapeHtml(test.calculated_priority || test.priority || "Unprioritized")}</span>
          </div>
          <strong>${escapeHtml(test.test_id)}</strong>
        </div>
        <h3>${escapeHtml(test.title)}</h3>
        <div class="test-data">
          <div><strong>Target functionality</strong>${escapeHtml(test.module)}</div>
          <div><strong>Page checked</strong>${escapeHtml(test.page)}</div>
          <div><strong>Category</strong>${escapeHtml(test.category || "Uncategorized")}</div>
          <div><strong>Test type</strong>${escapeHtml(test.test_type)}</div>
          <div><strong>Priority</strong>${escapeHtml(test.calculated_priority || test.priority || "Unprioritized")}</div>
          <div><strong>Execution sequence</strong>${escapeHtml(test.execution_order ?? "Not assigned")}</div>
          <div><strong>Execution mode</strong>${escapeHtml(test.execution_mode)}</div>
          <div><strong>Description</strong>${escapeHtml(test.description)}</div>
          <div><strong>Expected result</strong>${escapeHtml(test.expected_result)}</div>
          <div><strong>Execution status</strong>${escapeHtml(status)}</div>
          <div><strong>Observed execution result</strong>${escapeHtml(executedMessage)}</div>
          <div><strong>Executed at</strong>${escapeHtml(test.executed_at || "Not executed")}</div>
          <div><strong>Browser page URL</strong>${escapeHtml(test.page_url || "Not captured in this run")}</div>
          <div><strong>Screenshot evidence</strong>${test.screenshot
            ? screenshotLink(test.screenshot)
            : `${status === "NOT EXECUTED" ? "Not executed" : "Not captured"}${test.screenshot_error
              ? ` — ${escapeHtml(test.screenshot_error)}`
              : ""}`}</div>
        </div>
        <p>${appLink}</p>
        ${status === "FAIL" && test.screenshot_error
          ? `<p class="notice">Screenshot capture failed: ${escapeHtml(test.screenshot_error)}</p>`
          : ""}
        ${status === "FAIL" ? renderFindingAnalysis(test) : ""}
        <div class="run-command">
          <strong>Run this case through the AYKSA Playwright agent</strong>
          <p>In PowerShell, from the project root. The command runs only this test, then generates a new case-by-case analysis report.</p>
          <code>${escapeHtml(command)}</code>
          <button class="copy-command" id="copyCommand" type="button">Copy command</button>
          <span id="copyStatus" class="muted" aria-live="polite"></span>
        </div>`;
      const position = filteredCases.findIndex(item => item.test_id === test.test_id);
      document.getElementById("casePosition").textContent =
        `${position + 1} of ${filteredCases.length}`;
      document.getElementById("previousCase").disabled = position <= 0;
      document.getElementById("nextCase").disabled =
        position < 0 || position >= filteredCases.length - 1;
      document.getElementById("copyCommand").addEventListener("click", async () => {
        const statusElement = document.getElementById("copyStatus");
        try {
          await navigator.clipboard.writeText(command);
          statusElement.textContent = "Command copied. Paste it in the project PowerShell terminal.";
        } catch {
          statusElement.textContent = "Clipboard not available. Select and copy the command above.";
        }
      });
    };
    const selectTest = testId => {
      selectedTestId = testId;
      document.querySelectorAll(".test-pick").forEach(button => {
        button.setAttribute(
          "aria-current",
          button.dataset.testId === selectedTestId ? "true" : "false"
        );
      });
      renderCaseDetail(
        filteredCases.find(test => test.test_id === selectedTestId)
      );
    };
    const applyFilters = () => {
      const search = document.getElementById("search").value.trim().toLowerCase();
      const module = document.getElementById("moduleFilter").value;
      const status = document.getElementById("statusFilter").value;
      const category = document.getElementById("categoryFilter").value;
      const sortMode = document.getElementById("sortFilter").value;
      filteredCases = cases.filter(test => {
        const searchable = [
          test.test_id, test.title, test.page, test.module, test.category,
          test.description, test.expected_result, test.execution_message,
          test.finding_id, test.finding_classification, test.triage_status
        ].join(" ").toLowerCase();
        return (!search || searchable.includes(search))
          && (!module || test.module === module)
          && (!status || test.execution_status === status)
          && (!category || test.category === category);
      }).sort((left, right) => compareCases(left, right, sortMode));
      document.getElementById("resultCount").textContent =
        `Showing ${filteredCases.length} of ${cases.length} test cases`;
      document.getElementById("testCases").innerHTML = filteredCases.length
        ? filteredCases.map(test => `
          <button class="test-pick" type="button" data-test-id="${escapeHtml(test.test_id)}"
            aria-current="${test.test_id === selectedTestId ? "true" : "false"}">
            <strong>${escapeHtml(test.title)}</strong>
            <span class="pick-meta">
              <span class="pick-id">${escapeHtml(test.test_id)}</span>
              <span>${escapeHtml(test.module)}</span>
              <span>${escapeHtml(test.page)}</span>
              <span class="badge ${statusClass(test.execution_status)}">${escapeHtml(test.execution_status)}</span>
            </span>
            ${test.finding_id ? `<span>${escapeHtml(test.finding_id)} · ${escapeHtml(issueLabel(test))}</span>` : ""}
          </button>`).join("")
        : '<div class="empty">No test cases match the selected filters.</div>';
      if (!filteredCases.some(test => test.test_id === selectedTestId)) {
        selectedTestId = filteredCases[0]?.test_id || null;
      }
      document.querySelectorAll(".test-pick").forEach(button => {
        button.addEventListener("click", () => selectTest(button.dataset.testId));
      });
      renderCaseDetail(
        filteredCases.find(test => test.test_id === selectedTestId)
      );
    };
    renderSummary();
    renderModules();
    renderOptions("moduleFilter", cases.map(test => test.module));
    renderOptions("statusFilter", cases.map(test => test.execution_status));
    renderOptions("categoryFilter", cases.map(test => test.category));
    ["search", "moduleFilter", "statusFilter", "categoryFilter", "sortFilter"].forEach(id => {
      document.getElementById(id).addEventListener("input", applyFilters);
      document.getElementById(id).addEventListener("change", applyFilters);
    });
    document.getElementById("previousCase").addEventListener("click", () => {
      const position = filteredCases.findIndex(test => test.test_id === selectedTestId);
      if (position > 0) selectTest(filteredCases[position - 1].test_id);
    });
    document.getElementById("nextCase").addEventListener("click", () => {
      const position = filteredCases.findIndex(test => test.test_id === selectedTestId);
      if (position >= 0 && position < filteredCases.length - 1) {
        selectTest(filteredCases[position + 1].test_id);
      }
    });
    document.getElementById("executionTime").textContent = data.execution_time || "Not recorded";
    document.getElementById("generatedAt").textContent = data.analysis_generated_at || "Not recorded";
    document.getElementById("executionSource").textContent = data.source_execution_report || "Not recorded";
    document.getElementById("catalogSource").textContent = data.source_test_catalog || "Not recorded";
    const applicationLink = document.getElementById("applicationLink");
    const safeBaseUrl = safeApplicationUrl(data.application_url);
    if (safeBaseUrl) {
      applicationLink.href = safeBaseUrl;
    } else {
      applicationLink.hidden = true;
    }
    document.getElementById("browserErrors").innerHTML = data.browser_errors?.length
      ? `<strong>Browser errors:</strong><ul>${data.browser_errors.map(error => `<li>${escapeHtml(error)}</li>`).join("")}</ul>`
      : '<span class="muted">No browser errors recorded.</span>';
    applyFilters();
  </script>
</body>
</html>
"""
        return page.replace(
            "__DASHBOARD_DATA__",
            embedded_json
        )