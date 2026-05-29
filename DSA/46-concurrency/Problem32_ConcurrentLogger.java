import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem32_ConcurrentLogger {
    /**
     * Problem: Concurrent Logger
     * Thread-safe logger with buffered writes.
     * Time: O(1) log, O(n) flush | Space: O(buffer_size)
     * Production Analogy: Log4j async appender buffering log entries before disk write.
     */
    private final List<String> buffer = new ArrayList<>();
    private final int flushSize;
    private final ReentrantLock lock = new ReentrantLock();

    public Problem32_ConcurrentLogger(int flushSize) { this.flushSize = flushSize; }

    public void log(String message) {
        lock.lock();
        try {
            buffer.add(System.currentTimeMillis() + " [" + Thread.currentThread().getName() + "] " + message);
            if (buffer.size() >= flushSize) flush();
        } finally { lock.unlock(); }
    }

    private void flush() {
        System.out.println("--- FLUSH ---");
        for (String s : buffer) System.out.println(s);
        buffer.clear();
    }

    public void close() { lock.lock(); try { if (!buffer.isEmpty()) flush(); } finally { lock.unlock(); } }

    public static void main(String[] args) throws InterruptedException {
        Problem32_ConcurrentLogger logger = new Problem32_ConcurrentLogger(3);
        Thread[] ts = new Thread[5];
        for (int i = 0; i < 5; i++) { final int id = i; ts[i] = new Thread(() -> logger.log("Message " + id)); ts[i].start(); }
        for (Thread t : ts) t.join();
        logger.close();
    }
}
