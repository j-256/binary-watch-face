package dev.j256.binarywatchface.history;

import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

import static dev.j256.binarywatchface.history.HistoryColors.*;

final class HistoryUi {
    static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static TextView text(LinearLayout parent, String value, int size, int color) {
        TextView view = new TextView(parent.getContext());
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setGravity(Gravity.CENTER);
        int padding = dp(parent.getContext(), 3);
        view.setPadding(0, padding, 0, padding);
        parent.addView(view, new LinearLayout.LayoutParams(-1, -2));
        return view;
    }

    static Button button(Context context, String label, boolean selected) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextSize(13);
        button.setAllCaps(false);
        button.setTextColor(selected ? Color.BLACK : INK);
        button.setPadding(dp(context, 5), 0, dp(context, 5), 0);
        GradientDrawable background = new GradientDrawable();
        background.setColor(selected ? ACCENT : SURFACE);
        background.setCornerRadius(dp(context, 24));
        button.setBackground(background);
        return button;
    }

    static Button action(LinearLayout parent, String label, boolean primary, View.OnClickListener listener) {
        Context context = parent.getContext();
        Button button = button(context, label, primary);
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, dp(context, 52));
        layout.setMargins(0, dp(context, 7), 0, 0);
        parent.addView(button, layout);
        button.setOnClickListener(listener);
        return button;
    }

    private HistoryUi() {}
}
