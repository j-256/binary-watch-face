package dev.j256.binarywatchface.history;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.window.OnBackInvokedDispatcher;

import static dev.j256.binarywatchface.history.HistoryColors.INK;
import static dev.j256.binarywatchface.history.HistoryColors.MUTED;

public final class HistoryActivity extends Activity {
    private static final int PERMISSION_REQUEST = 21;
    private static final int MINUTES_PER_HOUR = 60;
    private static final String SETTINGS_SCREEN = "settings-screen";
    private boolean working;
    private boolean showingSettings;
    private ScrollView scroll;
    private HistorySettings displayedSettings;
    private HistorySeries displayedSeries;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setNavigationBarColor(Color.BLACK);
        showingSettings = state != null && state.getBoolean(SETTINGS_SCREEN);
        getOnBackInvokedDispatcher().registerOnBackInvokedCallback(OnBackInvokedDispatcher.PRIORITY_DEFAULT, () -> {
            if (showingSettings && displayedSeries != null) {
                showingSettings = false;
                render(displayedSettings, displayedSeries);
            } else finish();
        });
    }

    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean(SETTINGS_SCREEN, showingSettings);
        super.onSaveInstanceState(state);
    }

    @Override public void onResume() {
        super.onResume();
        refresh();
    }

    private void refresh() {
        HistoryRuntime.IO.execute(() -> {
            HistorySettings settings = new HistorySettings(this);
            HistorySeries series;
            try (HistoryStore store = new HistoryStore(this)) {
                series = settings.demo() ? HistorySeries.demo(settings.span(), System.currentTimeMillis())
                        : store.read(settings.span(), System.currentTimeMillis());
            } catch (RuntimeException error) {
                settings.status(HistorySettings.STATUS_STORAGE_ERROR);
                series = new HistorySeries(settings.span(), System.currentTimeMillis());
            }
            HistorySeries snapshot = series;
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) render(settings, snapshot);
            });
        });
    }

    private void render(HistorySettings settings, HistorySeries series) {
        displayedSettings = settings;
        displayedSeries = series;
        if (!showingSettings) {
            renderGraph(settings, series);
            return;
        }
        int offset = scroll == null ? 0 : scroll.getScrollY();
        scroll = HistoryUi.scroll(this);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(28), dp(30), dp(28), dp(42));
        scroll.addView(content);
        TextView title = text(content, getString(R.string.settings), 24, INK);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        action(content, R.string.view_graph, false, view -> {
            showingSettings = false;
            render(settings, series);
        }).setEnabled(true);
        action(content, R.string.battery_test, false,
                view -> startActivity(new Intent(this, BatteryTestActivity.class)));
        text(content, status(settings, series), 13, MUTED);
        TextView window = text(content, getString(R.string.span_heading), 14, INK);
        window.setPadding(0, dp(14), 0, dp(4));
        HistorySeries.Span[] spans = HistorySeries.Span.values();
        for (int row = 0; row < 2; row++) {
            LinearLayout buttons = new LinearLayout(this);
            buttons.setBaselineAligned(false);
            for (int column = 0; column < 2; column++) {
                HistorySeries.Span span = spans[row * 2 + column];
                Button button = button(span.label, span == settings.span());
                LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(0, -1, 1);
                layout.setMargins(dp(2), dp(3), dp(2), dp(3));
                buttons.addView(button, layout);
                button.setOnClickListener(view -> {
                    settings.span(span);
                    HistoryRuntime.requestImage(this);
                    refresh();
                });
            }
            content.addView(buttons);
        }
        TextView labelsHeading = text(content, getString(R.string.labels_heading), 14, INK);
        labelsHeading.setPadding(0, dp(14), 0, dp(4));
        action(content, settings.labels().title, false, view -> {
            HistorySettings.Labels[] choices = HistorySettings.Labels.values();
            String[] titles = new String[choices.length];
            for (int index = 0; index < choices.length; index++) titles[index] = getString(choices[index].title);
            HistoryUi.showDialog(new AlertDialog.Builder(this).setTitle(R.string.labels_heading)
                    .setSingleChoiceItems(titles, settings.labels().ordinal(), (dialog, index) -> {
                        settings.labels(choices[index]);
                        HistoryRuntime.requestImage(this);
                        dialog.dismiss();
                        refresh();
                    }).setNegativeButton(R.string.not_now, null));
        });
        if (settings.labels() != HistorySettings.Labels.NONE) {
            long minutes = HistoryTimeline.intervalMs(settings.span()) / HistorySeries.MINUTE_MS;
            String interval = minutes < MINUTES_PER_HOUR ? minutes + " min" : minutes / MINUTES_PER_HOUR + " h";
            text(content, getString(R.string.mark_spacing, interval), 12, MUTED);
        }
        text(content, getString(R.string.brightness_help), 12, MUTED).setPadding(0, dp(12), 0, dp(4));
        action(content, working ? R.string.working : R.string.start, true, view -> requestStart());
        if (settings.recording()) action(content, R.string.pause, false, view -> {
            working = true;
            refresh();
            HistoryRuntime.pause(this, this::finished);
        });
        action(content, R.string.sample, false, view -> {
            working = true;
            refresh();
            HistoryRuntime.stop(this, true, this::finished);
        });
        if (settings.recording() || settings.demo() || series.sampleCount > 0) {
            action(content, R.string.erase, false, view -> HistoryUi.showDialog(new AlertDialog.Builder(this)
                    .setTitle(R.string.erase_title).setMessage(R.string.erase_explanation)
                    .setNegativeButton(R.string.not_now, null)
                    .setPositiveButton(R.string.erase, (dialog, which) -> {
                        working = true;
                        refresh();
                        HistoryRuntime.stop(this, false, this::finished);
                    })));
        }
        if (!HistorySettings.hasPermissions(this)) {
            action(content, R.string.permissions, false, view -> startActivity(new Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + getPackageName()))));
        }
        text(content, getString(R.string.show_on_face), 12, MUTED).setPadding(0, dp(16), 0, dp(12));
        text(content, getString(R.string.privacy), 12, MUTED);
        setContentView(scroll);
        scroll.post(() -> scroll.scrollTo(0, offset));
    }

    private void renderGraph(HistorySettings settings, HistorySeries series) {
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER_HORIZONTAL);
        content.setBackgroundColor(Color.BLACK);
        content.setPadding(0, dp(10), 0, dp(20));
        content.addView(new HistoryGraphView(this, series, settings.demo()), new LinearLayout.LayoutParams(-1, 0, 1));
        Button settingsButton = button(getString(R.string.settings), false);
        settingsButton.setEnabled(true);
        settingsButton.setMinHeight(dp(40));
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(dp(112), -2);
        layout.topMargin = dp(7);
        content.addView(settingsButton, layout);
        settingsButton.setOnClickListener(view -> {
            showingSettings = true;
            render(settings, series);
        });
        setContentView(content);
    }

    private String status(HistorySettings settings, HistorySeries series) {
        if (settings.demo()) return getString(R.string.status_sample);
        int error = switch (settings.status()) {
            case HistorySettings.STATUS_PERMISSION -> R.string.status_permission;
            case HistorySettings.STATUS_UNSUPPORTED -> R.string.status_unsupported;
            case HistorySettings.STATUS_ERROR -> R.string.status_error;
            case HistorySettings.STATUS_STORAGE_ERROR -> R.string.status_storage_error;
            case HistorySettings.STATUS_SCHEDULE_ERROR -> R.string.status_schedule_error;
            case HistorySettings.STATUS_PAUSE_ERROR -> R.string.status_pause_error;
            case HistorySettings.STATUS_PAUSING -> R.string.working;
            default -> 0;
        };
        if (error != 0) return getString(error);
        if (!settings.recording()) return getString(R.string.status_paused);
        if (!HistorySettings.hasPermissions(this)) return getString(R.string.status_permission);
        int age = (int) ((series.endMs - series.latestMs) / HistorySeries.MINUTE_MS);
        return series.sampleCount == 0 ? getString(R.string.status_waiting)
                : getResources().getQuantityString(R.plurals.status_recording, age, age);
    }

    private void requestStart() {
        if (checkSelfPermission(HistorySettings.HEART_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{HistorySettings.HEART_PERMISSION}, PERMISSION_REQUEST);
        } else if (checkSelfPermission(HistorySettings.BACKGROUND_PERMISSION) != PackageManager.PERMISSION_GRANTED) {
            HistoryUi.showDialog(new AlertDialog.Builder(this).setTitle(R.string.background_title)
                    .setMessage(R.string.background_explanation)
                    .setNegativeButton(R.string.not_now, null)
                    .setPositiveButton(R.string.allow_background, (dialog, which) ->
                            requestPermissions(new String[]{HistorySettings.BACKGROUND_PERMISSION}, PERMISSION_REQUEST)));
        } else {
            working = true;
            refresh();
            HistoryRuntime.start(this, this::finished);
        }
    }

    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request != PERMISSION_REQUEST) return;
        if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) requestStart();
        else {
            new HistorySettings(this).status(HistorySettings.STATUS_PERMISSION);
            refresh();
        }
    }

    private void finished() {
        runOnUiThread(() -> {
            working = false;
            if (!isDestroyed()) refresh();
        });
    }

    private TextView text(LinearLayout parent, String value, int size, int color) {
        return HistoryUi.text(parent, value, size, color);
    }

    private Button button(String label, boolean selected) {
        Button button = HistoryUi.button(this, label, selected);
        button.setEnabled(!working);
        return button;
    }

    private Button action(LinearLayout parent, int label, boolean primary, View.OnClickListener listener) {
        Button button = HistoryUi.action(parent, getString(label), primary, listener);
        button.setEnabled(!working);
        return button;
    }

    private int dp(int value) {
        return HistoryUi.dp(this, value);
    }
}
