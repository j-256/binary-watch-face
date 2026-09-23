package dev.j256.binarywatchface.history;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class HistoryBootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
                && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(intent.getAction())) return;
        BatteryTestStore.invalidate(context, Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
                ? BatteryTrial.Issue.RESTARTED : BatteryTrial.Issue.UPDATED);
        if (new HistorySettings(context).recording()) HistoryRuntime.scheduleRegistration(context);
        HistoryRuntime.scheduleMaintenance(context);
    }
}
