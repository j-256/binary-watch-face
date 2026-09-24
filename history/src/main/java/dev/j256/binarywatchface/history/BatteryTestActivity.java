package dev.j256.binarywatchface.history;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.graphics.Color;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.window.OnBackInvokedDispatcher;

import java.text.DateFormat;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.function.Consumer;

import static dev.j256.binarywatchface.history.HistoryColors.*;

public final class BatteryTestActivity extends Activity {
    private BatteryTrial.Mode selected = BatteryTrial.Mode.BASELINE;
    private boolean results;
    private String detailId;
    private String message;
    private boolean working;
    private final Consumer<String> operationFinished = this::completed;
    private final BroadcastReceiver charging = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            HistoryRuntime.IO.execute(() -> {
                BatteryTestStore.invalidate(context, BatteryTrial.Issue.CHARGING);
                refresh();
            });
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setNavigationBarColor(Color.BLACK);
        if (state != null) {
            selected = BatteryTrial.Mode.valueOf(state.getString("mode", BatteryTrial.Mode.BASELINE.name()));
            results = state.getBoolean("results");
            detailId = state.getString("detail");
        }
        getOnBackInvokedDispatcher().registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, () -> {
            if (detailId != null) { detailId = null; refresh(); }
            else if (results) { results = false; refresh(); }
            else finish();
        });
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putString("mode", selected.name());
        state.putBoolean("results", results);
        state.putString("detail", detailId);
        super.onSaveInstanceState(state);
    }

    @Override protected void onResume() {
        super.onResume();
        BatteryTestCoordinator.observe(operationFinished);
        registerReceiver(charging, new IntentFilter(Intent.ACTION_POWER_CONNECTED), Context.RECEIVER_NOT_EXPORTED);
        refresh();
    }

    @Override protected void onPause() {
        unregisterReceiver(charging);
        BatteryTestCoordinator.stopObserving(operationFinished);
        super.onPause();
    }

    private void refresh() {
        HistoryRuntime.IO.execute(() -> {
            try {
                BatteryTestStore store = new BatteryTestStore(this);
                BatteryTrial.Reading reading = BatteryReader.read(this);
                if (reading.plugged()) BatteryTestStore.invalidate(this, BatteryTrial.Issue.CHARGING);
                BatteryTrial.Run saved = store.active();
                if (saved != null && saved.started() && !saved.finished()) {
                    BatteryTestStore.invalidate(this, saved.observe(reading, false, true).issue());
                    if (!saved.configuration().equals(BatteryReader.configuration(this))) {
                        BatteryTestStore.invalidate(this, BatteryTrial.Issue.SETTINGS_CHANGED);
                    }
                }
                BatteryTrial.Run active = store.active();
                List<BatteryTrial.Run> runs = store.results(System.currentTimeMillis());
                String configuration = BatteryReader.configuration(this);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) render(active, runs, configuration, reading);
                });
            } catch (RuntimeException error) {
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) return;
                    LinearLayout content = content("Battery test");
                    text(content, "Battery records could not be read. " + error.getMessage(), 13, INK);
                    action(content, "Retry", true, view -> refresh());
                    action(content, "Reset battery tests", false, view -> HistoryUi.showDialog(new AlertDialog.Builder(this)
                            .setTitle("Reset battery tests?")
                            .setMessage("Removes unreadable tests and results. Heart-rate history is kept. Confirm your recording mode in History settings afterward.")
                            .setNegativeButton(R.string.not_now, null).setPositiveButton("Reset", (dialog, which) -> {
                                HistoryRuntime.IO.execute(() -> {
                                    try { new BatteryTestStore(this).reset(); refresh(); }
                                    catch (RuntimeException failure) { completed(failure.getMessage()); }
                                });
                            })));
                    action(content, "Back", false, view -> finish());
                });
            }
        });
    }

    private void render(BatteryTrial.Run active, List<BatteryTrial.Run> runs, String configuration, BatteryTrial.Reading reading) {
        LinearLayout content = content(results ? "Battery results" : "Battery test");
        if (message != null) text(content, message, 13, INK);
        if (detailId != null) {
            for (BatteryTrial.Run run : runs) if (run.id().equals(detailId)) { renderDetail(content, run); return; }
            detailId = null;
        }
        if (results) { renderResults(content, runs, configuration); return; }
        if (active == null) {
            text(content, "Compare whole-watch drain with tracking and the background graph on or off.", 13, MUTED);
            action(content, BatteryText.mode(selected), false, view -> {
                BatteryTrial.Mode[] choices = BatteryTrial.Mode.values();
                String[] titles = new String[choices.length];
                for (int index = 0; index < choices.length; index++) titles[index] = BatteryText.mode(choices[index]);
                HistoryUi.showDialog(new AlertDialog.Builder(this).setTitle("Test mode")
                        .setSingleChoiceItems(titles, selected.ordinal(), (dialog, which) -> {
                            selected = choices[which];
                            dialog.dismiss();
                            message = null;
                            refresh();
                        }).setNegativeButton(R.string.not_now, null));
            });
            text(content, description(selected), 13, INK);
            action(content, "Set up mode", true, view -> {
                if (selected.recording && !HistorySettings.hasPermissions(this)) {
                    message = "First grant heart-rate and background access using Start recording in History settings.";
                    refresh();
                } else operate(done -> BatteryTestCoordinator.prepare(this, selected, done));
            });
            text(content, "Your previous recording mode is restored when you finish or cancel. Existing readings are kept until they expire.", 12, MUTED);
        } else if (active.finished()) {
            text(content, "Run saved. Restore your previous recording mode before starting another.", 14, INK);
            action(content, "Retry restore", true, view -> operate(done -> BatteryTestCoordinator.finish(this, false, done)));
        } else if (!active.started()) {
            text(content, BatteryText.mode(active.mode()), 18, INK);
            if (!active.ready()) {
                text(content, "Apply the recording mode, then confirm the graph on your watch face.", 13, MUTED);
                action(content, "Apply mode", true, view -> operate(done -> BatteryTestCoordinator.prepare(this, active.mode(), done)));
            } else {
                text(content, "Recording mode is ready.", 13, ACCENT);
                text(content, active.mode().graph
                        ? "In Binary Pulse, choose a Layout with heart history. Confirm the graph is visible."
                        : "In Binary Pulse, choose a Layout without heart history. Keep the same ordinary complication count.", 13, INK);
                text(content, "Keep brightness, always-on display, colors, and other settings the same across runs. Unplug before starting.", 12, MUTED);
                if (active.mode() == BatteryTrial.Mode.GRAPH) text(content, "The graph uses invented preview data while tracking is off.", 12, MUTED);
                CheckBox confirmed = new CheckBox(this);
                confirmed.setText(R.string.battery_layout_confirmed);
                confirmed.setTextSize(13);
                confirmed.setTextColor(INK);
                content.addView(confirmed, new LinearLayout.LayoutParams(-1, -2));
                Button start = action(content, "Start run", true, view -> operate(done -> BatteryTestCoordinator.start(this, done)));
                start.setEnabled(false);
                confirmed.setOnCheckedChangeListener((button, checked) -> start.setEnabled(checked && !working && !BatteryTestCoordinator.busy()));
            }
            action(content, "Cancel setup", false, view -> operate(done -> BatteryTestCoordinator.cancel(this, done)));
        } else {
            text(content, BatteryText.mode(active.mode()) + " running", 18, INK);
            double elapsed = reading.bootCount() == active.first().bootCount()
                    ? Math.max(0, reading.elapsedMs() - active.first().elapsedMs()) / (double) BatteryTrial.HOUR_MS : 0;
            text(content, BatteryText.hours(elapsed) + " elapsed", 22, ACCENT);
            text(content, active.first().percent() + "% at start / " + (reading.available() ? reading.percent() + "% now" : "reading unavailable"), 13, INK);
            if (active.issue() != BatteryTrial.Issue.NONE) text(content, "Excluded: " + BatteryText.issue(active.issue()), 13, INK);
            action(content, "Finish run", true, view -> HistoryUi.showDialog(new AlertDialog.Builder(this)
                    .setTitle("Uninterrupted run?")
                    .setMessage("Did the watch stay unplugged with the same face and settings, without force-stopping History? Brief interruptions between readings cannot be detected reliably.")
                    .setPositiveButton("Yes, save", (dialog, which) -> operate(done -> BatteryTestCoordinator.finish(this, true, done)))
                    .setNegativeButton("No, exclude", (dialog, which) -> operate(done -> BatteryTestCoordinator.finish(this, false, done)))
                    .setNeutralButton("Keep running", null)));
            action(content, "Add battery reading", false, view -> operate(done -> BatteryTestCoordinator.checkpoint(this, done)));
            text(content, "Close the app and wear your watch normally. Aim for 12-24 hours. Start, finish, and added readings are saved; no background polling runs.", 12, MUTED);
            if (active.mode() == BatteryTrial.Mode.GRAPH) text(content, "Preview graph active. Your heart-rate recording is paused.", 12, MUTED);
            action(content, "View readings", false, view -> HistoryUi.showDialog(new AlertDialog.Builder(this)
                    .setTitle("Observed battery")
                    .setView(new BatteryReadingsView(this, active))
                    .setPositiveButton("Close", null)));
        }
        action(content, "Results", false, view -> { results = true; message = null; refresh(); });
        text(content, "Repeat each mode on comparable days. Battery percentage is coarse; small differences may be noise.", 12, MUTED);
        action(content, "Back to history", false, view -> finish());
    }

    private void renderResults(LinearLayout content, List<BatteryTrial.Run> runs, String configuration) {
        text(content, "Whole-watch drain", 17, INK);
        text(content, "Percentage points per hour (pp/h)", 12, MUTED);
        content.addView(new BatteryComparisonView(this, runs, configuration), new LinearLayout.LayoutParams(-1, dp(160)));
        text(content, "Lower uses less battery. Bars show the duration-weighted average; dots show individual runs.", 12, MUTED);
        text(content, "Only uninterrupted runs of at least 12 hours with this app build, time window, labels, and markers enter the comparison.", 12, MUTED);
        BatteryTrial.Summary baseline = BatteryTrial.summarize(runs, BatteryTrial.Mode.BASELINE, configuration);
        for (BatteryTrial.Mode mode : BatteryTrial.Mode.values()) {
            BatteryTrial.Summary summary = BatteryTrial.summarize(runs, mode, configuration);
            if (summary.runs() == 0) continue;
            text(content, BatteryText.mode(mode) + ": " + summary.runs() + " runs / " + BatteryText.hours(summary.hours()), 13, INK);
            if (mode != BatteryTrial.Mode.BASELINE && baseline.runs() > 0) {
                String delta = String.format(Locale.getDefault(), "%+.2f pp/h vs baseline", summary.rate() - baseline.rate());
                text(content, delta, 14, ACCENT);
                if (Math.min(baseline.runs(), summary.runs()) < 2) text(content, "Preliminary: repeat both modes", 12, MUTED);
            }
        }
        BatteryTrial.Summary both = BatteryTrial.summarize(runs, BatteryTrial.Mode.BOTH, configuration);
        BatteryTrial.Summary tracking = BatteryTrial.summarize(runs, BatteryTrial.Mode.RECORDING, configuration);
        if (both.runs() > 0 && tracking.runs() > 0) {
            text(content, "Graph added to tracking", 14, INK);
            text(content, String.format(Locale.getDefault(), "%+.2f pp/h", both.rate() - tracking.rate()), 16, ACCENT);
            if (Math.min(both.runs(), tracking.runs()) < 2) text(content, "Preliminary: repeat both modes", 12, MUTED);
        }
        text(content, "Different routines, face settings, signal, or workouts can change drain. These differences are estimates, not per-app energy attribution.", 12, MUTED);
        text(content, "Saved runs", 18, INK);
        if (runs.isEmpty()) text(content, "Finish a run to see its readings here.", 13, MUTED);
        for (BatteryTrial.Run run : runs) {
            action(content, BatteryText.mode(run.mode()) + " / " + date(run.createdMs()), false, view -> { detailId = run.id(); refresh(); });
            text(content, result(run) + (run.configuration().equals(configuration) ? "" : " / different setup"), 12, MUTED);
        }
        if (!runs.isEmpty()) {
            action(content, "Share results", false, view -> share());
            action(content, "Clear battery results", false, view -> HistoryUi.showDialog(new AlertDialog.Builder(this)
                    .setTitle("Clear battery results?").setMessage("Heart-rate history and an active test are kept.")
                    .setNegativeButton(R.string.not_now, null).setPositiveButton("Clear", (dialog, which) -> {
                        HistoryRuntime.IO.execute(() -> {
                            try { new BatteryTestStore(this).clearResults(); refresh(); }
                            catch (RuntimeException error) { completed(error.getMessage()); }
                        });
                    })));
        }
        text(content, "Results stay on this watch unless you choose to share them. Retains the latest "
                + BatteryTestStore.MAX_RUNS + " runs for up to " + BatteryTestStore.RETENTION_MS / (24 * BatteryTrial.HOUR_MS)
                + " days, cleaned when opened.", 12, MUTED);
        action(content, "Back to test", false, view -> { results = false; refresh(); });
    }

    private void renderDetail(LinearLayout content, BatteryTrial.Run run) {
        text(content, BatteryText.mode(run.mode()), 18, INK);
        text(content, result(run), 14, ACCENT);
        text(content, date(run.first().wallMs()) + " / " + BatteryText.hours(Math.max(0, run.hours())), 13, MUTED);
        content.addView(new BatteryReadingsView(this, run), new LinearLayout.LayoutParams(-1, dp(130)));
        text(content, "Dots are observed readings; the gaps were not measured.", 12, MUTED);
        text(content, run.first().percent() + "% to " + run.last().percent() + "%", 17, INK);
        if (Double.isFinite(run.mahPerHour())) text(content, String.format(Locale.getDefault(), "Charge counter: %.2f mAh/h", run.mahPerHour()), 12, MUTED);
        else text(content, "Charge-counter rate unavailable", 12, MUTED);
        for (BatteryTrial.Reading point : run.readings()) {
            text(content, date(point.wallMs()) + " / " + point.percent() + "%", 12, MUTED);
        }
        text(content, "Setup: " + run.configuration(), 11, MUTED);
        action(content, "Back to results", false, view -> { detailId = null; refresh(); });
    }

    private void share() {
        HistoryRuntime.IO.execute(() -> {
            try {
                Intent report = BatteryReport.intent(this);
                runOnUiThread(() -> {
                    if (isDestroyed()) return;
                    try {
                        startActivity(Intent.createChooser(report, "Share battery results"));
                    } catch (ActivityNotFoundException error) {
                        message = "No sharing app is available on this watch. Results remain available here.";
                        refresh();
                    }
                });
            } catch (RuntimeException error) { completed(error.getMessage()); }
        });
    }

    private void operate(Consumer<Consumer<String>> operation) {
        working = true;
        message = null;
        refresh();
        operation.accept(operationFinished);
    }

    private void completed(String error) {
        runOnUiThread(() -> {
            working = false;
            message = error;
            if (!isDestroyed()) refresh();
        });
    }

    private LinearLayout content(String title) {
        ScrollView scroll = HistoryUi.scroll(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(28), dp(30), dp(28), dp(42));
        scroll.addView(content);
        setContentView(scroll);
        text(content, title, 24, INK);
        if (working || BatteryTestCoordinator.busy()) text(content, "Applying recording mode...", 13, MUTED);
        return content;
    }

    private Button action(LinearLayout parent, String label, boolean primary, View.OnClickListener listener) {
        Button button = HistoryUi.action(parent, label, primary, listener);
        button.setEnabled(!working && !BatteryTestCoordinator.busy());
        return button;
    }

    private void text(LinearLayout parent, String value, int size, int color) { HistoryUi.text(parent, value, size, color); }
    private int dp(int value) { return HistoryUi.dp(this, value); }
    private static String date(long time) { return DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(new Date(time)); }

    private static String result(BatteryTrial.Run run) {
        if (run.issue() != BatteryTrial.Issue.NONE) return "Excluded: " + BatteryText.issue(run.issue());
        return BatteryText.rate(run.percentPerHour()) + (run.comparable() ? "" : " / short run, outside comparison");
    }

    private static String description(BatteryTrial.Mode mode) {
        return switch (mode) {
            case BASELINE -> "Tracking off. Background graph off.";
            case RECORDING -> "Tracking on. Background graph off.";
            case GRAPH -> "Tracking off. Background graph on, using populated preview data.";
            case BOTH -> "Tracking on. Background graph on, using your recorded readings.";
        };
    }
}
