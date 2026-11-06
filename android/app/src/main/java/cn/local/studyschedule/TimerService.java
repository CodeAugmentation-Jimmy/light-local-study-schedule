package cn.local.studyschedule;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.widget.Toast;
import org.json.JSONObject;

public class TimerService extends Service {
    private StudyStore store;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private int ticks = 0;
    private final Runnable ticker = new Runnable() {
        @Override public void run() {
            try {
                boolean wasPaused = store.isPaused();
                store.tick();
                if (!wasPaused && store.isPaused()) {
                    Notification reminder = new Notification.Builder(TimerService.this, "complete")
                            .setSmallIcon(R.drawable.ic_timer).setContentTitle(store.pauseReason().contains("课程") ? "今日课程表已更新" : "本轮专注完成，休息一下")
                            .setContentText(store.pauseReason())
                            .setContentIntent(openApp()).setAutoCancel(true).build();
                    getSystemService(NotificationManager.class).notify(3, reminder);
                    getSystemService(NotificationManager.class).notify(1, notification());
                }
                for (JSONObject item : store.items()) {
                    if (item.optString("id").equals(store.activeId()) && CourseSchedule.isDue(item, StudyStore.currentDate()) && StudyStore.seconds(item, StudyStore.today()) >= item.optInt("goal") * 60.0) {
                        String key = "notified_" + store.activeId();
                        if (store.setting(key).equals(StudyStore.today())) break;
                        store.setting(key, StudyStore.today());
                        Notification n = new Notification.Builder(TimerService.this, "complete")
                                .setSmallIcon(R.drawable.ic_timer).setContentTitle("今日学习目标已完成")
                                .setContentText(store.isPaused() ? "计时已暂停，休息后可继续学习。" : "计时仍在继续，可以暂停休息或停止本次学习。")
                                .setContentIntent(openApp()).setAutoCancel(true).build();
                        getSystemService(NotificationManager.class).notify(2, n);
                        break;
                    }
                }
                if (store.activeId().isEmpty() || !store.canRun()) { finishTimer(); return; }
                if (++ticks % 15 == 0) {
                    store.save();
                    getSystemService(NotificationManager.class).notify(1, notification());
                }
                handler.postDelayed(this, 1000);
            } catch (Exception e) { fail(e); }
        }
    };

    @Override public void onCreate() {
        super.onCreate();
        store = StudyStore.get(this);
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel("timer", "学习计时", NotificationManager.IMPORTANCE_LOW));
        manager.createNotificationChannel(new NotificationChannel("complete", "目标完成提醒", NotificationManager.IMPORTANCE_DEFAULT));
        if (Build.VERSION.SDK_INT >= 34) startForeground(1, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
        else startForeground(1, notification());
    }
    private PendingIntent openApp() {
        Intent intent = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        return PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
    private PendingIntent command(String action, int request) {
        return PendingIntent.getService(this, request, new Intent(this, TimerService.class).setAction(action), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
    private Notification notification() {
        String name = "学习日程";
        for (JSONObject item : store.items()) if (item.optString("id").equals(store.activeId())) name = item.optString("name");
        Notification.Builder builder = new Notification.Builder(this, "timer").setSmallIcon(R.drawable.ic_timer)
                .setContentTitle((store.isPaused() ? "已暂停 · " : "正在学习 · ") + name)
                .setContentText("本次专注 " + StudyStore.duration(store.sessionSeconds()))
                .setContentIntent(openApp()).setOngoing(true).setOnlyAlertOnce(true)
                .addAction(new Notification.Action.Builder(null, store.isPaused() ? "继续" : "暂停", command("PAUSE", 1)).build())
                .addAction(new Notification.Action.Builder(null, "停止", command("STOP", 2)).build());
        if (!store.isPaused() && !store.activeId().isEmpty()) {
            builder.setWhen(System.currentTimeMillis() - (long) (store.sessionSeconds() * 1000)).setUsesChronometer(true);
        }
        return builder.build();
    }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        try {
            String action = intent == null ? "" : intent.getAction();
            if ("START".equals(action)) store.start(intent.getStringExtra("id"));
            else if ("PAUSE".equals(action)) store.togglePause();
            else if ("STOP".equals(action)) store.stop();
            if (store.activeId().isEmpty() || !store.canRun()) { finishTimer(); return START_NOT_STICKY; }
            getSystemService(NotificationManager.class).notify(1, notification());
            handler.removeCallbacks(ticker);
            handler.post(ticker);
        } catch (Exception e) { fail(e); }
        return START_NOT_STICKY;
    }
    private void finishTimer() {
        handler.removeCallbacks(ticker);
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }
    private void fail(Exception error) {
        Toast.makeText(this, error.getMessage(), Toast.LENGTH_LONG).show();
        try { if (!store.activeId().isEmpty() && !store.isPaused()) store.togglePause(); } catch (Exception ignored) { }
        finishTimer();
    }
    @Override public void onDestroy() {
        handler.removeCallbacks(ticker);
        try { store.tick(); store.save(); } catch (Exception ignored) { }
        super.onDestroy();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
}
