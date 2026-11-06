package android.content;

import java.util.HashMap;
import java.util.Map;

public class Context {
    public static final int MODE_PRIVATE = 0;
    private final Map<String, Object> values = new HashMap<>();
    public Context getApplicationContext() { return this; }
    public SharedPreferences getSharedPreferences(String name, int mode) {
        return new SharedPreferences() {
            public String getString(String key, String fallback) { return (String) values.getOrDefault(key, fallback); }
            public long getLong(String key, long fallback) { return (Long) values.getOrDefault(key, fallback); }
            public Editor edit() {
                return new Editor() {
                    private final Map<String, Object> pending = new HashMap<>();
                    public Editor putString(String key, String value) { pending.put(key, value); return this; }
                    public Editor putLong(String key, long value) { pending.put(key, value); return this; }
                    public boolean commit() { values.putAll(pending); return true; }
                    public void apply() { commit(); }
                };
            }
        };
    }
}
