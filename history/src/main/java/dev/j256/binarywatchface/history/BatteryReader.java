package dev.j256.binarywatchface.history;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.SystemClock;
import android.provider.Settings;

final class BatteryReader {
    static BatteryTrial.Reading read(Context context) {
        BatteryManager manager = context.getSystemService(BatteryManager.class);
        Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        int charge = manager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CHARGE_COUNTER);
        int boot = Settings.Global.getInt(context.getContentResolver(), Settings.Global.BOOT_COUNT, BatteryTrial.UNKNOWN);
        return new BatteryTrial.Reading(System.currentTimeMillis(), SystemClock.elapsedRealtime(), boot,
                percent(battery),
                charge < 0 ? BatteryTrial.UNKNOWN : charge,
                battery == null || battery.getIntExtra(BatteryManager.EXTRA_PLUGGED, BatteryTrial.UNKNOWN) != 0,
                version(context));
    }

    static int percent(Intent battery) {
        if (battery == null) return BatteryTrial.UNKNOWN;
        int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, BatteryTrial.UNKNOWN);
        int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, BatteryTrial.UNKNOWN);
        if (scale <= 0 || level < 0 || level > scale) return BatteryTrial.UNKNOWN;
        return (int) ((level * 100L + scale / 2L) / scale);
    }

    static long version(Context context) {
        try {
            return context.getPackageManager().getPackageInfo(context.getPackageName(), 0).getLongVersionCode();
        } catch (PackageManager.NameNotFoundException error) {
            throw new IllegalStateException("History package metadata unavailable", error);
        }
    }

    static String configuration(Context context) {
        HistorySettings settings = new HistorySettings(context);
        return "v" + version(context) + " / " + Build.MODEL + " / " + Build.VERSION.RELEASE
                + " / " + Build.VERSION.INCREMENTAL
                + " / " + settings.span().name() + " / " + settings.labels().name()
                + " / " + settings.markers().name() + " / " + settings.density().name();
    }

    private BatteryReader() {}
}
