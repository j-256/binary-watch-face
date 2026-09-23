package dev.j256.binarywatchface.history;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class HistoryActivity extends Activity {
    private static final int PERMISSION_REQUEST = 21;
    private static final int INK = Color.rgb(234, 244, 238);
    private static final int MUTED = Color.rgb(157, 179, 166);
    private static final int ACCENT = Color.rgb(147, 246, 189);
    private static final int SURFACE = Color.rgb(23, 35, 29);
    private boolean working;
    private ScrollView scroll;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setNavigationBarColor(Color.BLACK);
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
        int offset = scroll == null ? 0 : scroll.getScrollY();
        scroll = new ScrollView(this);
        scroll.setBackgroundColor(Color.BLACK);
        scroll.setFillViewport(true);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(28), dp(30), dp(28), dp(42));
        scroll.addView(content);
        text(content, getString(R.string.eyebrow), 10, ACCENT);
        TextView title = text(content, getString(R.string.title), 24, INK);
        title.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        ImageView preview = new ImageView(this);
        preview.setImageBitmap(GraphRenderer.render(series, settings.demo(), "No readings yet"));
        preview.setColorFilter(ACCENT);
        preview.setContentDescription(getString(R.string.graph_description));
        preview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        content.addView(preview, new LinearLayout.LayoutParams(-1, dp(100)));
        text(content, status(settings, series), 13, MUTED);
        TextView window = text(content, getString(R.string.span_heading), 14, INK);
        window.setPadding(0, dp(14), 0, dp(4));
        HistorySeries.Span[] spans = HistorySeries.Span.values();
        for (int row = 0; row < 2; row++) {
            LinearLayout buttons = new LinearLayout(this);
            for (int column = 0; column < 2; column++) {
                HistorySeries.Span span = spans[row * 2 + column];
                Button button = button(span.label, span == settings.span());
                LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(0, dp(48), 1);
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
            new AlertDialog.Builder(this).setTitle(R.string.labels_heading)
                    .setSingleChoiceItems(titles, settings.labels().ordinal(), (dialog, index) -> {
                        settings.labels(choices[index]);
                        HistoryRuntime.requestImage(this);
                        dialog.dismiss();
                        refresh();
                    }).setNegativeButton(R.string.not_now, null).show();
        });
        action(content, working ? R.string.working : R.string.start, true, view -> requestStart());
        action(content, R.string.sample, false, view -> {
            working = true;
            refresh();
            HistoryRuntime.stop(this, true, this::finished);
        });
        if (settings.recording() || settings.demo() || series.sampleCount > 0) {
            action(content, R.string.erase, false, view -> new AlertDialog.Builder(this)
                    .setTitle(R.string.erase_title).setMessage(R.string.erase_explanation)
                    .setNegativeButton(R.string.not_now, null)
                    .setPositiveButton(R.string.erase, (dialog, which) -> {
                        working = true;
                        refresh();
                        HistoryRuntime.stop(this, false, this::finished);
                    }).show());
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

    private String status(HistorySettings settings, HistorySeries series) {
        if (settings.demo()) return getString(R.string.status_sample);
        int error = switch (settings.status()) {
            case HistorySettings.STATUS_PERMISSION -> R.string.status_permission;
            case HistorySettings.STATUS_UNSUPPORTED -> R.string.status_unsupported;
            case HistorySettings.STATUS_ERROR -> R.string.status_error;
            case HistorySettings.STATUS_STORAGE_ERROR -> R.string.status_storage_error;
            case HistorySettings.STATUS_SCHEDULE_ERROR -> R.string.status_schedule_error;
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
            new AlertDialog.Builder(this).setTitle(R.string.background_title)
                    .setMessage(R.string.background_explanation)
                    .setNegativeButton(R.string.not_now, null)
                    .setPositiveButton(R.string.allow_background, (dialog, which) ->
                            requestPermissions(new String[]{HistorySettings.BACKGROUND_PERMISSION}, PERMISSION_REQUEST))
                    .show();
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
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER);
        view.setPadding(0, dp(3), 0, dp(3));
        parent.addView(view, new LinearLayout.LayoutParams(-1, -2));
        return view;
    }

    private Button button(String label, boolean selected) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextSize(13);
        button.setAllCaps(false);
        button.setTextColor(selected ? Color.BLACK : INK);
        button.setPadding(dp(5), 0, dp(5), 0);
        GradientDrawable background = new GradientDrawable();
        background.setColor(selected ? ACCENT : SURFACE);
        background.setCornerRadius(dp(24));
        button.setBackground(background);
        button.setEnabled(!working);
        return button;
    }

    private void action(LinearLayout parent, int label, boolean primary, View.OnClickListener listener) {
        Button button = button(getString(label), primary);
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, dp(52));
        layout.setMargins(0, dp(7), 0, 0);
        parent.addView(button, layout);
        button.setOnClickListener(listener);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
