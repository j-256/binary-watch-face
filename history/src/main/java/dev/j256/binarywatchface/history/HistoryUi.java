package dev.j256.binarywatchface.history;

import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Context;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.StateListDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.widget.AbsListView;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.CheckedTextView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.function.IntConsumer;

import static dev.j256.binarywatchface.history.HistoryColors.*;

final class HistoryUi {
    private static final int BUTTON_PADDING_DP = 12;
    private static final int BUTTON_VERTICAL_PADDING_DP = 6;
    private static final int BUTTON_MIN_HEIGHT_DP = 48;
    private static final int ACTION_MIN_HEIGHT_DP = 52;
    private static final int DIALOG_SIDE_INSET_DP = 26;
    private static final int DIALOG_END_INSET_DP = 24;

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

    static void showChoices(Context context, String title, String[] labels, int selected, IntConsumer choose) {
        Dialog dialog = new Dialog(context);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout content = new LinearLayout(context);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setGravity(Gravity.CENTER_HORIZONTAL);
        content.setBackgroundColor(Color.BLACK);
        content.setPadding(dp(context, DIALOG_SIDE_INSET_DP), dp(context, DIALOG_END_INSET_DP),
                dp(context, DIALOG_SIDE_INSET_DP), dp(context, DIALOG_END_INSET_DP));
        ListView list = new ListView(context);
        list.setChoiceMode(ListView.CHOICE_MODE_SINGLE);
        list.setDivider(new ColorDrawable(Color.BLACK));
        list.setDividerHeight(dp(context, 6));
        LinearLayout heading = new LinearLayout(context);
        heading.setPadding(0, 0, 0, dp(context, 8));
        TextView titleView = text(heading, title, 18, INK);
        titleView.setTextAlignment(View.TEXT_ALIGNMENT_CENTER);
        titleView.setAccessibilityHeading(true);
        list.addHeaderView(heading, null, false);
        LinearLayout footer = new LinearLayout(context);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(0, dp(context, 8), 0, 0);
        Button cancel = button(context, context.getString(R.string.cancel), false);
        footer.addView(cancel, new LinearLayout.LayoutParams(dp(context, 112), -2));
        cancel.setOnClickListener(view -> dialog.dismiss());
        list.addFooterView(footer, null, false);
        list.setAdapter(new ArrayAdapter<String>(context, 0, labels) {
            @Override public View getView(int position, View recycled, ViewGroup parent) {
                CheckedTextView view;
                if (recycled instanceof CheckedTextView existing) view = existing;
                else {
                    view = new CheckedTextView(context);
                    view.setTextSize(14);
                    view.setSingleLine(false);
                    view.setEllipsize(null);
                    view.setGravity(Gravity.CENTER);
                    view.setTextAlignment(View.TEXT_ALIGNMENT_CENTER);
                    view.setMinHeight(dp(context, ACTION_MIN_HEIGHT_DP));
                    view.setPadding(dp(context, BUTTON_PADDING_DP), dp(context, BUTTON_VERTICAL_PADDING_DP),
                            dp(context, BUTTON_PADDING_DP), dp(context, BUTTON_VERTICAL_PADDING_DP));
                    int[][] states = {{android.R.attr.state_checked}, {}};
                    view.setTextColor(new ColorStateList(states, new int[]{Color.BLACK, INK}));
                    StateListDrawable background = new StateListDrawable();
                    background.addState(states[0], buttonBackground(context, ACCENT));
                    background.addState(states[1], buttonBackground(context, SURFACE));
                    view.setBackground(background);
                    view.setLayoutParams(new AbsListView.LayoutParams(-1, -2));
                }
                view.setText(getItem(position));
                return view;
            }
        });
        list.setItemChecked(selected + list.getHeaderViewsCount(), true);
        list.setSelection(Math.max(0, selected + list.getHeaderViewsCount() - 1));
        content.addView(list, new LinearLayout.LayoutParams(-1, -1));
        list.setOnItemClickListener((parent, view, position, id) -> {
            int index = position - list.getHeaderViewsCount();
            if (index < 0 || index >= labels.length) return;
            dialog.dismiss();
            choose.accept(index);
        });
        dialog.setContentView(content);
        Window window = dialog.getWindow();
        window.setBackgroundDrawable(new ColorDrawable(Color.BLACK));
        window.getDecorView().setPadding(0, 0, 0, 0);
        dialog.show();
        window.setLayout(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT);
        focusScrollingView(list);
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
        button.setBackground(buttonBackground(context, selected ? ACCENT : SURFACE));
        return button;
    }

    private static GradientDrawable buttonBackground(Context context, int color) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(color);
        background.setCornerRadius(dp(context, 24));
        return background;
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
