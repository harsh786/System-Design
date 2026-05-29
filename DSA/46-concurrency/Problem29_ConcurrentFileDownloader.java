import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;

public class Problem29_ConcurrentFileDownloader {
    /**
     * Problem: Concurrent File Downloader
     * Download multiple files concurrently with progress tracking.
     * Approach: ExecutorService + Future for each download task.
     * Time: O(total_size / bandwidth)
     * Production Analogy: Package manager (npm, maven) downloading dependencies in parallel.
     */
    public static String download(String url) throws InterruptedException {
        Thread.sleep((long)(Math.random() * 200));
        return "Downloaded: " + url + " (" + (int)(Math.random() * 1000) + " KB)";
    }

    public static void main(String[] args) throws Exception {
        ExecutorService executor = Executors.newFixedThreadPool(3);
        List<String> urls = Arrays.asList("file1.dat", "file2.dat", "file3.dat", "file4.dat", "file5.dat");
        List<Future<String>> futures = new ArrayList<>();
        for (String url : urls) futures.add(executor.submit(() -> download(url)));
        for (Future<String> f : futures) System.out.println(f.get());
        executor.shutdown();
    }
}
