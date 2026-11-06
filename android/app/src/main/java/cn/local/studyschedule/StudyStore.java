package cn.local.studyschedule;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.Clock;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/** Each device owns a monotonically increasing counter per category and date. */
public final class StudyStore {
    public static final int PROTOCOL = 2;
    private static Clock calendarClock;
    private static Clock clock() { return calendarClock == null ? Clock.systemDefaultZone() : calendarClock; }
    private static StudyStore instance;
    private final SharedPreferences prefs;
    private JSONObject document;
    public final String device;
    private String active = "";
    private boolean paused = false;
    private double session = 0;
    private long lastTick;
    private boolean visible;
    private double focusEnd;
    private String pauseReason = "";

    public static synchronized StudyStore get(Context context) {
        if (instance == null) instance = new StudyStore(context.getApplicationContext());
        return instance;
    }

    private StudyStore(Context context) {
        prefs = context.getSharedPreferences("study", Context.MODE_PRIVATE);
        device = prefs.getString("device", UUID.randomUUID().toString().replace("-", ""));
        try {
            String original = prefs.getString("document", "{\"protocol\":2,\"items\":[]}");
            document = upgradeLocal(new JSONObject(original));
            validate(document);
            if (new JSONObject(original).getInt("protocol") == 1 && prefs.getString("document_before_1_2", "").isEmpty()) {
                if (!prefs.edit().putString("document_before_1_2", original).commit()) throw new IllegalStateException("升级备份保存失败");
            }
            active = prefs.getString("active", "");
            session = Double.longBitsToDouble(prefs.getLong("session", Double.doubleToLongBits(0)));
            // After process death recover the last saved duration in a paused state.
            paused = !active.isEmpty();
            if (find(active) == null || (find(active) != null && find(active).optBoolean("deleted"))) {
                active = ""; paused = false; session = 0;
            }
            lastTick = SystemClock.elapsedRealtime();
            pauseReason = active.isEmpty() ? "" : "上次计时已恢复，请手动继续";
            resetFocusEnd();
            focusEnd = Double.longBitsToDouble(prefs.getLong("focusEnd", Double.doubleToLongBits(focusEnd)));
            if (!Double.isFinite(focusEnd) || focusEnd < session) resetFocusEnd();
        } catch (Exception e) {
            // Keep the original data for recovery; never silently replace it.
            throw new IllegalStateException("学习记录无法读取，请勿清除应用数据：" + e.getMessage(), e);
        }
    }

    public static LocalDate currentDate() { return LocalDate.now(clock()); }
    public static String today() { return currentDate().toString(); }
    /** Only local stored v1 data is upgraded. Old wire clients must update first. */
    public static JSONObject upgradeLocal(JSONObject old) throws JSONException {
        JSONObject upgraded = cloneJson(old);
        if (upgraded.getInt("protocol") == 1) {
            JSONArray items = upgraded.getJSONArray("items");
            for (int i = 0; i < items.length(); i++) items.getJSONObject(i).put("schedule", CourseSchedule.daily());
            upgraded.put("protocol", PROTOCOL);
        }
        validate(upgraded);
        return upgraded;
    }
    public static String duration(double seconds) {
        long value = Math.max(0, (long) seconds);
        return String.format(Locale.ROOT, "%02d:%02d:%02d", value / 3600, value / 60 % 60, value % 60);
    }
    private static JSONObject cloneJson(JSONObject value) throws JSONException { return new JSONObject(value.toString()); }
    private JSONObject find(String id) {
        JSONArray items = document.optJSONArray("items");
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.optJSONObject(i);
            if (item.optString("id").equals(id)) return item;
        }
        return null;
    }
    private JSONArray nextRevision() throws JSONException {
        long maximum = 0;
        JSONArray items = document.getJSONArray("items");
        for (int i = 0; i < items.length(); i++) maximum = Math.max(maximum, items.getJSONObject(i).getJSONArray("rev").getLong(0));
        return new JSONArray().put(maximum + 1).put(device);
    }
    public synchronized List<JSONObject> items() {
        List<JSONObject> items = new ArrayList<>();
        JSONArray data = document.optJSONArray("items");
        for (int i = 0; i < data.length(); i++) {
            JSONObject item = data.optJSONObject(i);
            if (!item.optBoolean("deleted")) {
                try { items.add(cloneJson(item)); } catch (JSONException e) { throw new IllegalStateException(e); }
            }
        }
        return items;
    }
    public static double seconds(JSONObject item, String day) {
        JSONObject counters = item.optJSONObject("counters").optJSONObject(day);
        double total = 0;
        if (counters != null) {
            Iterator<String> keys = counters.keys();
            while (keys.hasNext()) total += counters.optDouble(keys.next(), 0);
        }
        return total;
    }
    public synchronized String activeId() { return active; }
    public synchronized boolean isPaused() { return paused; }
    public synchronized double sessionSeconds() { return session; }
    public synchronized String pauseReason() { return pauseReason; }
    public boolean backgroundEnabled() { return !setting("background").equals("false"); }
    public int focusMinutes() {
        try { return Math.max(0, Math.min(180, Integer.parseInt(setting("focusMinutes")))); }
        catch (NumberFormatException e) { return 0; }
    }
    public synchronized double focusRemaining() { return focusMinutes() == 0 ? 0 : Math.max(0, focusEnd - session); }
    private void resetFocusEnd() { focusEnd = session + focusMinutes() * 60.0; }
    public synchronized void setFocusMinutes(int minutes) throws JSONException {
        if (minutes < 0 || minutes > 180) throw new IllegalArgumentException("专注时长需在 0 至 180 分钟之间");
        tick(); setting("focusMinutes", String.valueOf(minutes)); resetFocusEnd(); save();
    }
    public synchronized void setVisible(boolean value) throws JSONException {
        visible = value;
        if (!visible && !backgroundEnabled()) pauseForBackground();
    }
    public synchronized boolean canRun() { return visible || backgroundEnabled(); }
    public synchronized void setBackgroundEnabled(boolean enabled) throws JSONException {
        setting("background", String.valueOf(enabled));
        if (!enabled && !visible) pauseForBackground();
        save();
    }
    private void pauseForBackground() throws JSONException {
        if (!active.isEmpty() && !paused) {
            tick();
            if (!paused) { paused = true; pauseReason = "已离开应用，计时自动暂停"; }
            save();
        }
    }

    public synchronized void edit(String id, String name, int goal) throws JSONException {
        JSONObject existing = find(id);
        edit(id, name, goal, existing == null ? CourseSchedule.daily() : existing.getJSONObject("schedule"));
    }
    public synchronized void edit(String id, String name, int goal, JSONObject schedule) throws JSONException {
        CourseSchedule.validate(schedule);
        name = name.trim();
        if (name.isEmpty() || name.length() > 200 || goal < 1 || goal > 1000000) throw new IllegalArgumentException("请输入 1 至 200 字的名称和 1 至 1000000 的整数分钟数");
        for (JSONObject other : items()) if (!other.optString("id").equals(id) && other.optString("name").equals(name)) throw new IllegalArgumentException("类目名称重复");
        JSONObject item = find(id);
        if (item != null && item.optBoolean("deleted")) throw new IllegalArgumentException("这个类目已在同步时被删除，请关闭后重新选择");
        tick();
        JSONArray rev = nextRevision();
        if (item == null) {
            item = new JSONObject().put("id", UUID.randomUUID().toString().replace("-", "")).put("counters", new JSONObject()).put("deleted", false);
            document.getJSONArray("items").put(item);
        }
        item.put("name", name).put("goal", goal).put("schedule", cloneJson(schedule)).put("rev", rev);
        pauseIfUnscheduled();
        save();
    }
    public synchronized void delete(String id) throws JSONException {
        if (id.equals(active)) throw new IllegalArgumentException("请先停止该类目的计时");
        JSONObject item = find(id);
        if (item != null) item.put("deleted", true).put("rev", nextRevision());
        save();
    }
    public synchronized void start(String id) throws JSONException {
        if (!canRun()) throw new IllegalArgumentException("请回到应用后开始计时");
        if (!active.isEmpty()) throw new IllegalArgumentException("请先停止当前计时");
        JSONObject item = find(id);
        if (item == null || item.optBoolean("deleted")) throw new IllegalArgumentException("请选择一个类目");
        if (!CourseSchedule.isDue(item, currentDate())) throw new IllegalArgumentException("今天未安排此课程，请选择今日课程或修改安排");
        active = id; paused = false; session = 0; lastTick = SystemClock.elapsedRealtime();
        pauseReason = ""; resetFocusEnd();
        save();
    }
    public synchronized void togglePause() throws JSONException {
        if (active.isEmpty()) return;
        boolean wasPaused = paused;
        if (wasPaused && !CourseSchedule.isDue(find(active), currentDate())) throw new IllegalArgumentException("今天未安排此课程，请停止后选择今日课程");
        if (wasPaused && !canRun()) throw new IllegalArgumentException("后台计时已关闭，请回到应用后继续");
        tick();
        // A timer reaching its focus limit during this tick must remain paused.
        if (wasPaused) { paused = false; pauseReason = ""; if (session >= focusEnd) resetFocusEnd(); }
        else if (!paused) { paused = true; pauseReason = "已手动暂停"; }
        lastTick = SystemClock.elapsedRealtime(); save();
    }
    public synchronized void stop() throws JSONException {
        tick(); active = ""; paused = false; session = 0; pauseReason = ""; save();
    }
    public synchronized boolean tick() throws JSONException {
        long nowTick = SystemClock.elapsedRealtime();
        double elapsed = Math.max(0, (nowTick - lastTick) / 1000.0);
        lastTick = nowTick;
        if (active.isEmpty() || paused || elapsed == 0) return false;
        double counted = focusMinutes() == 0 ? elapsed : Math.min(elapsed, Math.max(0, focusEnd - session));
        JSONObject item = find(active);
        if (item == null || item.optBoolean("deleted")) { active = ""; paused = false; session = 0; return false; }
        double before = seconds(item, today());
        long cursor = clock().millis() - (long) (elapsed * 1000);
        long end = cursor + (long) Math.round(counted * 1000);
        JSONObject counters = item.getJSONObject("counters");
        ZoneId zone = clock().getZone();
        double recorded = 0;
        boolean scheduleEnded = false;
        while (cursor < end) {
            LocalDate day = Instant.ofEpochMilli(cursor).atZone(zone).toLocalDate();
            if (!CourseSchedule.isDue(item, day)) { scheduleEnded = true; break; }
            long boundary = day.plusDays(1).atStartOfDay(zone).toInstant().toEpochMilli();
            long until = Math.min(end, boundary);
            JSONObject values = counters.optJSONObject(day.toString());
            if (values == null) { values = new JSONObject(); counters.put(day.toString(), values); }
            values.put(device, values.optDouble(device, 0) + (until - cursor) / 1000.0);
            recorded += (until - cursor) / 1000.0;
            cursor = until;
        }
        session += recorded;
        if (scheduleEnded || !CourseSchedule.isDue(item, currentDate())) {
            paused = true; pauseReason = "日历已切换，今天未安排此课程，请停止后选择今日课程"; save();
        }
        if (!paused && focusMinutes() > 0 && session >= focusEnd) {
            paused = true; pauseReason = "本轮专注完成，休息后点击继续"; save();
        }
        return before < item.optInt("goal") * 60.0 && seconds(item, today()) >= item.optInt("goal") * 60.0;
    }
    public synchronized JSONObject snapshot() throws JSONException { tick(); return cloneJson(document); }
    private void pauseIfUnscheduled() {
        JSONObject item = find(active);
        if (item != null && !paused && !CourseSchedule.isDue(item, currentDate())) {
            paused = true; pauseReason = "今天未安排此课程，已暂停，请停止后选择今日课程";
        }
    }
    public synchronized void merge(JSONObject incoming) throws JSONException {
        tick();
        document = mergeDocuments(document, incoming);
        JSONObject item = find(active);
        if (item == null || item.optBoolean("deleted")) { active = ""; paused = false; session = 0; }
        pauseIfUnscheduled();
        save();
    }
    public synchronized void save() {
        boolean saved = prefs.edit().putString("device", device).putString("document", document.toString())
                .putString("active", active).putLong("session", Double.doubleToLongBits(session))
                .putLong("focusEnd", Double.doubleToLongBits(focusEnd)).commit();
        if (!saved) throw new IllegalStateException("保存失败，请检查手机存储空间");
    }
    public String setting(String key) { return prefs.getString(key, ""); }
    public void setting(String key, String value) { prefs.edit().putString(key, value).apply(); }

    public static void validate(JSONObject doc) throws JSONException {
        if (doc.getInt("protocol") != PROTOCOL) throw new JSONException("课程表同步需要电脑和手机均升级至 1.2 或更高版本");
        JSONArray items = doc.getJSONArray("items");
        if (items.length() > 10000) throw new JSONException("类目数量过多");
        Map<String, Boolean> seen = new HashMap<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.getJSONObject(i);
            String id = item.getString("id");
            if (!id.matches("[A-Za-z0-9_-]{1,128}") || seen.put(id, true) != null) throw new JSONException("类目编号有误");
            String name = item.getString("name");
            if (name.trim().isEmpty() || name.length() > 200) throw new JSONException("类目名称有误");
            double goal = item.getDouble("goal");
            if (goal < 1 || goal > 1000000 || goal != Math.floor(goal)) throw new JSONException("目标有误");
            CourseSchedule.validate(item.getJSONObject("schedule"));
            JSONArray rev = item.getJSONArray("rev");
            double revision = rev.getDouble(0);
            if (rev.length() != 2 || revision < 0 || revision >= 9007199254740992.0 || revision != Math.floor(revision) || !rev.getString(1).matches("[A-Za-z0-9_-]{1,128}")) throw new JSONException("版本有误");
            if (!(item.get("deleted") instanceof Boolean)) throw new JSONException("删除标记有误");
            JSONObject days = item.getJSONObject("counters");
            Iterator<String> dates = days.keys();
            while (dates.hasNext()) {
                String day = dates.next();
                try { if (!LocalDate.parse(day).toString().equals(day)) throw new IllegalArgumentException(); }
                catch (Exception e) { throw new JSONException("日期有误"); }
                JSONObject values = days.getJSONObject(day);
                Iterator<String> devices = values.keys();
                while (devices.hasNext()) {
                    String device = devices.next();
                    double value = values.getDouble(device);
                    if (!device.matches("[A-Za-z0-9_-]{1,128}") || !Double.isFinite(value) || value < 0 || value > 1e12) throw new JSONException("学习时间有误");
                }
            }
        }
    }
    public static JSONObject mergeDocuments(JSONObject left, JSONObject right) throws JSONException {
        validate(left); validate(right);
        Map<String, JSONObject> all = new HashMap<>();
        JSONArray leftItems = left.getJSONArray("items"), rightItems = right.getJSONArray("items");
        for (int i = 0; i < leftItems.length(); i++) { JSONObject item = leftItems.getJSONObject(i); all.put(item.getString("id"), cloneJson(item)); }
        for (int i = 0; i < rightItems.length(); i++) {
            JSONObject remote = rightItems.getJSONObject(i);
            String id = remote.getString("id");
            JSONObject local = all.get(id);
            if (local == null) { all.put(id, cloneJson(remote)); continue; }
            JSONArray a = local.getJSONArray("rev"), b = remote.getJSONArray("rev");
            boolean remoteWins = b.getLong(0) > a.getLong(0) || (b.getLong(0) == a.getLong(0) && b.getString(1).compareTo(a.getString(1)) > 0);
            JSONObject winner = cloneJson(remoteWins ? remote : local);
            winner.put("deleted", local.getBoolean("deleted") || remote.getBoolean("deleted"));
            JSONObject counters = winner.getJSONObject("counters");
            for (JSONObject source : new JSONObject[]{local, remote}) {
                JSONObject days = source.getJSONObject("counters");
                Iterator<String> dates = days.keys();
                while (dates.hasNext()) {
                    String day = dates.next();
                    JSONObject target = counters.optJSONObject(day);
                    if (target == null) { target = new JSONObject(); counters.put(day, target); }
                    JSONObject values = days.getJSONObject(day);
                    Iterator<String> devices = values.keys();
                    while (devices.hasNext()) { String device = devices.next(); target.put(device, Math.max(target.optDouble(device, 0), values.getDouble(device))); }
                }
            }
            all.put(id, winner);
        }
        List<JSONObject> sorted = new ArrayList<>(all.values());
        sorted.sort(Comparator.comparing(item -> item.optString("id")));
        JSONArray result = new JSONArray(); for (JSONObject item : sorted) result.put(item);
        return new JSONObject().put("protocol", PROTOCOL).put("items", result);
    }
}
