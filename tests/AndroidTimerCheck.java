import android.content.Context;
import android.os.SystemClock;
import cn.local.studyschedule.StudyStore;
import cn.local.studyschedule.StudyStats;
import cn.local.studyschedule.CourseSchedule;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneId;
import java.lang.reflect.Field;
import java.time.LocalDate;
import java.util.List;
import org.json.JSONObject;

public class AndroidTimerCheck {
    private static void check(boolean value, String message) {
        if (!value) throw new AssertionError(message);
    }
    private static void near(double expected, double actual) {
        check(Math.abs(expected - actual) < .01, "Expected " + expected + " but got " + actual);
    }
    private static void advance(StudyStore store, int seconds) throws Exception {
        SystemClock.advance(seconds * 1000L); store.tick();
    }
    private static void wall(String timestamp) throws Exception {
        Field clock = StudyStore.class.getDeclaredField("calendarClock"); clock.setAccessible(true);
        clock.set(null, Clock.fixed(Instant.parse(timestamp), ZoneId.of("UTC")));
    }
    public static void main(String[] args) throws Exception {
        Context context = new Context(); StudyStore store = StudyStore.get(context);
        store.setVisible(true); store.edit("", "Math", 30);
        String id = store.items().get(0).getString("id");
        store.start(id);
        switch (args[0]) {
            case "calendar_rules":
                JSONObject odd = new JSONObject().put("schedule", new JSONObject().put("mode", "odd"));
                JSONObject even = new JSONObject().put("schedule", new JSONObject().put("mode", "even"));
                for (String day : new String[]{"2026-10-31", "2026-11-01", "2028-02-29", "2028-03-01", "2027-01-01"}) {
                    check(CourseSchedule.isDue(odd, LocalDate.parse(day)), "Odd day failed: " + day);
                    check(!CourseSchedule.isDue(even, LocalDate.parse(day)), "Even day failed: " + day);
                }
                check(CourseSchedule.nextDate(even, LocalDate.parse("2026-10-31")).equals(LocalDate.parse("2026-11-02")), "Month boundary next date wrong");
                JSONObject week = new JSONObject("{\"schedule\":{\"mode\":\"weekdays\",\"days\":[1,3,7]}}");
                for (int i = 0; i < 7; i++) check(CourseSchedule.isDue(week, LocalDate.parse("2026-11-02").plusDays(i)) == (i == 0 || i == 2 || i == 6), "Weekday wrong");
                for (String bad : new String[]{"[]", "[0]", "[2,1]", "[1,1]", "[8]", "[true]", "[1.5]"}) {
                    boolean invalid = false;
                    try { CourseSchedule.validate(new JSONObject("{\"mode\":\"weekdays\",\"days\":" + bad + "}")); }
                    catch (Exception e) { invalid = true; }
                    check(invalid, "Invalid weekday accepted: " + bad);
                }
                break;
            case "calendar_midnight":
                store.stop(); wall("2026-11-05T23:59:50Z");
                store.edit(id, "Math", 30, new JSONObject().put("mode", "odd")); store.start(id);
                wall("2026-11-06T00:00:15Z"); advance(store, 25);
                near(10, store.sessionSeconds()); check(store.isPaused(), "Midnight must pause off-day course");
                near(10, StudyStore.seconds(store.items().get(0), "2026-11-05"));
                near(0, StudyStore.seconds(store.items().get(0), "2026-11-06"));
                boolean blocked = false;
                try { store.togglePause(); } catch (IllegalArgumentException e) { blocked = true; }
                check(blocked, "Off-day resume accepted");
                store.stop(); blocked = false;
                try { store.start(id); } catch (IllegalArgumentException e) { blocked = true; }
                check(blocked, "Off-day start accepted");
                break;
            case "calendar_sync":
                store.stop(); wall("2026-11-05T12:00:00Z"); store.start(id);
                advance(store, 10);
                JSONObject change = store.snapshot();
                change.getJSONArray("items").getJSONObject(0).put("schedule", new JSONObject().put("mode", "even"))
                        .put("rev", new org.json.JSONArray().put(99).put("pc"));
                store.merge(change); check(store.isPaused(), "Synced schedule must pause off-day timer");
                near(10, store.sessionSeconds());
                check(store.items().get(0).getJSONObject("schedule").getString("mode").equals("even"), "Synced rule lost");
                break;
            case "calendar_upgrade":
                store.stop(); JSONObject old = store.snapshot(); old.put("protocol", 1);
                old.getJSONArray("items").getJSONObject(0).remove("schedule");
                JSONObject upgraded = StudyStore.upgradeLocal(old);
                check(upgraded.getInt("protocol") == 2, "Protocol not upgraded");
                check(upgraded.getJSONArray("items").getJSONObject(0).getJSONObject("schedule").getString("mode").equals("daily"), "Legacy course not daily");
                boolean oldRejected = false;
                try { store.merge(old); } catch (Exception e) { oldRejected = true; }
                check(oldRejected, "Old wire protocol must be rejected");
                context.getSharedPreferences("study", 0).edit().putString("document", old.toString()).commit();
                Field instance = StudyStore.class.getDeclaredField("instance"); instance.setAccessible(true); instance.set(null, null);
                store = StudyStore.get(context);
                check(store.snapshot().getInt("protocol") == 2, "Stored legacy data not migrated");
                check(context.getSharedPreferences("study", 0).getString("document_before_1_2", "").equals(old.toString()), "Migration backup missing");
                break;
            case "background_off":
                store.setBackgroundEnabled(false); advance(store, 12);
                store.setVisible(false); advance(store, 90);
                check(store.isPaused(), "Leaving app must pause"); near(12, store.sessionSeconds());
                boolean rejected = false;
                try { store.togglePause(); } catch (IllegalArgumentException e) { rejected = true; }
                check(rejected, "Hidden notification must not resume timer");
                store.setVisible(true); advance(store, 20); near(12, store.sessionSeconds());
                store.togglePause(); advance(store, 8); near(20, store.sessionSeconds());
                break;
            case "background_on":
                check(store.backgroundEnabled(), "Upgrade must preserve default background behavior");
                advance(store, 10); store.setVisible(false); advance(store, 50);
                check(!store.isPaused(), "Background mode must keep running"); near(60, store.sessionSeconds());
                store.setBackgroundEnabled(false); advance(store, 30); near(60, store.sessionSeconds());
                break;
            case "focus_limit":
                store.setFocusMinutes(1); advance(store, 90);
                near(60, store.sessionSeconds()); check(store.isPaused(), "Focus limit must pause");
                near(60, StudyStore.seconds(store.items().get(0), StudyStore.today()));
                advance(store, 300); near(60, store.sessionSeconds());
                store.togglePause(); advance(store, 10); near(70, store.sessionSeconds());
                near(50, store.focusRemaining());
                break;
            case "manual_pause":
                store.setFocusMinutes(1); advance(store, 20); store.togglePause();
                advance(store, 100); store.togglePause(); advance(store, 10);
                near(30, store.sessionSeconds()); near(30, store.focusRemaining());
                advance(store, 40); near(60, store.sessionSeconds()); check(store.isPaused(), "Pause must preserve round remaining time");
                break;
            case "boundary_pause":
                store.setFocusMinutes(1); SystemClock.advance(65000); store.togglePause();
                check(store.isPaused(), "Pause at focus boundary must not accidentally resume"); near(60, store.sessionSeconds());
                break;
            case "recovery":
                store.setBackgroundEnabled(false); store.setFocusMinutes(1); advance(store, 20); store.save();
                Field singleton = StudyStore.class.getDeclaredField("instance"); singleton.setAccessible(true); singleton.set(null, null);
                SystemClock.advance(600000); store = StudyStore.get(context);
                check(store.isPaused(), "Recovered timer must be paused");
                check(!store.backgroundEnabled(), "Background preference must persist");
                near(20, store.sessionSeconds()); near(40, store.focusRemaining());
                store.setVisible(true); store.togglePause(); advance(store, 50); near(60, store.sessionSeconds());
                check(store.isPaused(), "Recovered round must retain its remaining time");
                break;
            case "settings":
                store.setFocusMinutes(1); advance(store, 20); store.setFocusMinutes(2);
                near(120, store.focusRemaining()); advance(store, 30);
                store.setFocusMinutes(0); advance(store, 300); near(350, store.sessionSeconds());
                check(!store.isPaused(), "Free mode must not pause at old limit");
                boolean invalid = false;
                try { store.setFocusMinutes(181); } catch (IllegalArgumentException e) { invalid = true; }
                check(invalid, "Invalid focus limit accepted");
                break;
            case "sync":
                store.setFocusMinutes(1); advance(store, 20);
                JSONObject remote = store.snapshot();
                remote.getJSONArray("items").getJSONObject(0).getJSONObject("counters")
                        .getJSONObject(StudyStore.today()).put("pc", 100);
                store.merge(remote); store.merge(remote); advance(store, 50);
                near(160, StudyStore.seconds(store.items().get(0), StudyStore.today()));
                near(60, store.sessionSeconds());
                check(!store.snapshot().has("background"), "Local timer preferences must not change wire protocol");
                break;
            case "statistics":
                LocalDate today = LocalDate.of(2026, 10, 28);
                JSONObject item = store.items().get(0), days = new JSONObject(); item.put("counters", days);
                for (int i : new int[]{1, 2, 3, 6, 7}) days.put(today.minusDays(i).toString(), new JSONObject().put("phone", 60).put("pc", 40));
                StudyStats stats = new StudyStats(List.of(item), today);
                near(400, stats.total); check(stats.streak == 3 && stats.studiedDays == 4, "Streak/week boundaries wrong");
                days.put(today.toString(), new JSONObject().put("phone", 20));
                stats = new StudyStats(List.of(item), today);
                near(420, stats.total); check(stats.streak == 4 && stats.studiedDays == 5, "Today missing from streak");
                stats = new StudyStats(List.of(), today); near(0, stats.total); check(stats.streak == 0, "Empty streak wrong");
                break;
            default: throw new AssertionError("Unknown scenario");
        }
        System.out.println("PASS " + args[0]);
    }
}
