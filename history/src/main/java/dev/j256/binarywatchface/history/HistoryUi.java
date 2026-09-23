package dev.j256.binarywatchface.history;

import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.AbsListView;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import static dev.j256.binarywatchface.history.HistoryColors.*;

final class HistoryUi {
    private static final int BUTTON_PADDING_DP = 12;
    private static final int BUTTON_VERTICAL_PADDING_DP = 6;
    private static final int BUTTON_MIN_HEIGHT_DP = 48;
    private static final int ACTION_MIN_HEIGHT_DP = 52;

    static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static ScrollView scroll(Context context) {
        ScrollView scroll = new ScrollView(context);
        scroll.setBackgroundColor(Color.BLACK);
        scroll.setFillViewport(true);
        focusScrollingView(scroll);
        return scroll;
    }

    static void showDialog(AlertDialog.Builder builder) {
        AlertDialog dialog = builder.show();
        focusScrollingView(dialog.getWindow().getDecorView());
    }

    private static boolean focusScrollingView(View view) {
        if (view instanceof ScrollView || view instanceof AbsListView) {
            // Crown events follow input focus, including while the screen is in touch mode
            view.setFocusableInTouchMode(true);
            return view.requestFocus();
        }
        if (view instanceof ViewGroup group) for (int index = 0; index < group.getChildCount(); index++) {
            if (focusScrollingView(group.getChildAt(index))) return true;
        }
        return false;
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
        button.setGravity(Gravity.CENTER);
        button.setMinHeight(dp(context, BUTTON_MIN_HEIGHT_DP));
        int padding = dp(context, BUTTON_PADDING_DP);
        int verticalPadding = dp(context, BUTTON_VERTICAL_PADDING_DP);
        button.setPadding(padding, verticalPadding, padding, verticalPadding);
        GradientDrawable background = new GradientDrawable();
        background.setColor(selected ? ACCENT : SURFACE);
        background.setCornerRadius(dp(context, 24));
        button.setBackground(background);
        return button;
    }

    static Button action(LinearLayout parent, String label, boolean primary, View.OnClickListener listener) {
        Context context = parent.getContext();
        Button button = button(context, label, primary);
        button.setMinHeight(dp(context, ACTION_MIN_HEIGHT_DP));
        LinearLayout.LayoutParams layout = new LinearLayout.LayoutParams(-1, -2);
        layout.setMargins(0, dp(context, 7), 0, 0);
        parent.addView(button, layout);
        button.setOnClickListener(listener);
        return button;
    }

    private HistoryUi() {}
}
