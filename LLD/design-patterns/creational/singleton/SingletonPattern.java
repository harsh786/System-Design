import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Singleton Design Pattern - Complete Implementation
 * 
 * Three approaches demonstrated:
 * 1. Double-Checked Locking (Thread-safe, Lazy)
 * 2. Enum-based Singleton (Joshua Bloch / Bill Pugh recommended)
 * 3. Inner Static Helper Class (Bill Pugh's Initialization-on-demand holder)
 */

// ============================================================
// 1. DOUBLE-CHECKED LOCKING SINGLETON
// ============================================================
class DatabaseConnectionPool {
    private static volatile DatabaseConnectionPool instance;
    
    private final List<String> connectionPool;
    private final int maxConnections;
    private final AtomicInteger activeConnections;
    
    private DatabaseConnectionPool(int maxConnections) {
        this.maxConnections = maxConnections;
        this.connectionPool = new ArrayList<>();
        this.activeConnections = new AtomicInteger(0);
        initializePool();
        System.out.println("[DCL] DatabaseConnectionPool created with " + maxConnections + " connections");
    }
    
    public static DatabaseConnectionPool getInstance() {
        if (instance == null) {                      // First check (no lock)
            synchronized (DatabaseConnectionPool.class) {
                if (instance == null) {              // Second check (with lock)
                    instance = new DatabaseConnectionPool(10);
                }
            }
        }
        return instance;
    }
    
    private void initializePool() {
        for (int i = 0; i < maxConnections; i++) {
            connectionPool.add("Connection-" + (i + 1));
        }
    }
    
    public String getConnection() {
        if (activeConnections.get() < maxConnections) {
            int idx = activeConnections.getAndIncrement();
            return connectionPool.get(idx);
        }
        throw new RuntimeException("No available connections");
    }
    
    public void releaseConnection() {
        activeConnections.decrementAndGet();
    }
    
    public int getActiveCount() {
        return activeConnections.get();
    }
    
    // Prevent cloning
    @Override
    protected Object clone() throws CloneNotSupportedException {
        throw new CloneNotSupportedException("Singleton cannot be cloned");
    }
}

// ============================================================
// 2. ENUM-BASED SINGLETON (Serialization-safe, Reflection-safe)
// ============================================================
enum ConfigurationManager {
    INSTANCE;
    
    private final ConcurrentHashMap<String, String> config = new ConcurrentHashMap<>();
    
    ConfigurationManager() {
        // Load default configuration
        config.put("app.name", "MyApplication");
        config.put("app.version", "1.0.0");
        config.put("db.host", "localhost");
        config.put("db.port", "5432");
        System.out.println("[ENUM] ConfigurationManager initialized");
    }
    
    public String get(String key) {
        return config.get(key);
    }
    
    public void set(String key, String value) {
        config.put(key, value);
    }
    
    public int size() {
        return config.size();
    }
}

// ============================================================
// 3. INNER STATIC HELPER CLASS (Initialization-on-demand holder)
// ============================================================
class Logger {
    private final List<String> logs = new ArrayList<>();
    
    private Logger() {
        System.out.println("[HOLDER] Logger instance created");
    }
    
    // Inner class is not loaded until getInstance() is called
    private static class LoggerHolder {
        private static final Logger INSTANCE = new Logger();
    }
    
    public static Logger getInstance() {
        return LoggerHolder.INSTANCE;
    }
    
    public synchronized void log(String level, String message) {
        String entry = "[" + level + "] " + message;
        logs.add(entry);
        System.out.println("  LOG: " + entry);
    }
    
    public void info(String msg)  { log("INFO", msg); }
    public void warn(String msg)  { log("WARN", msg); }
    public void error(String msg) { log("ERROR", msg); }
    
    public int getLogCount() {
        return logs.size();
    }
}

// ============================================================
// MAIN - Demonstration
// ============================================================
public class SingletonPattern {
    
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== SINGLETON DESIGN PATTERN DEMO ===\n");
        
        // --- 1. Double-Checked Locking ---
        System.out.println("--- 1. Double-Checked Locking: Database Connection Pool ---");
        DatabaseConnectionPool pool1 = DatabaseConnectionPool.getInstance();
        DatabaseConnectionPool pool2 = DatabaseConnectionPool.getInstance();
        System.out.println("Same instance? " + (pool1 == pool2));
        String conn = pool1.getConnection();
        System.out.println("Got connection: " + conn);
        System.out.println("Active connections: " + pool1.getActiveCount());
        pool1.releaseConnection();
        System.out.println();
        
        // --- 2. Enum-based Singleton ---
        System.out.println("--- 2. Enum Singleton: Configuration Manager ---");
        ConfigurationManager cfg1 = ConfigurationManager.INSTANCE;
        ConfigurationManager cfg2 = ConfigurationManager.INSTANCE;
        System.out.println("Same instance? " + (cfg1 == cfg2));
        System.out.println("App name: " + cfg1.get("app.name"));
        cfg1.set("app.env", "production");
        System.out.println("Env from cfg2: " + cfg2.get("app.env"));
        System.out.println();
        
        // --- 3. Static Inner Class ---
        System.out.println("--- 3. Static Inner Class: Logger ---");
        Logger log1 = Logger.getInstance();
        Logger log2 = Logger.getInstance();
        System.out.println("Same instance? " + (log1 == log2));
        log1.info("Application started");
        log2.warn("Low memory");
        log1.error("Connection timeout");
        System.out.println("Total logs: " + log1.getLogCount());
        System.out.println();
        
        // --- Thread Safety Test ---
        System.out.println("--- Thread Safety Verification ---");
        final int THREADS = 10;
        Thread[] threads = new Thread[THREADS];
        DatabaseConnectionPool[] instances = new DatabaseConnectionPool[THREADS];
        
        for (int i = 0; i < THREADS; i++) {
            final int idx = i;
            threads[i] = new Thread(() -> {
                instances[idx] = DatabaseConnectionPool.getInstance();
            });
            threads[i].start();
        }
        for (Thread t : threads) t.join();
        
        boolean allSame = true;
        for (int i = 1; i < THREADS; i++) {
            if (instances[i] != instances[0]) { allSame = false; break; }
        }
        System.out.println("All " + THREADS + " threads got same instance? " + allSame);
        System.out.println("\n=== DEMO COMPLETE ===");
    }
}
