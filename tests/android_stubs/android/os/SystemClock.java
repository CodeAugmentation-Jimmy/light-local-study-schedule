package android.os;

/** Controllable monotonic clock for host tests only; never packaged in the APK. */
public final class SystemClock {
    private static long time;
    public static long elapsedRealtime() { return time; }
    public static void advance(long milliseconds) { time += milliseconds; }
}
