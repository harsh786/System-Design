/**
 * Problem: Web Crawler Multithreaded
 * Crawl URLs starting from a seed, using multiple threads, avoid duplicates.
 * 
 * Approach: ConcurrentHashMap for visited set + ExecutorService thread pool.
 * Time Complexity: O(V + E) for graph traversal
 * Space Complexity: O(V)
 * 
 * Production Analogy: Search engine crawler (Googlebot) - distributed crawling
 * with deduplication and politeness constraints.
 */
import java.util.*;
import java.util.concurrent.*;

public class Problem08_WebCrawlerMultithreaded {
    private Set<String> visited = ConcurrentHashMap.newKeySet();
    private List<String> result = Collections.synchronizedList(new ArrayList<>());

    // Simulated URL fetcher
    private List<String> getUrls(String url) {
        Map<String, List<String>> graph = new HashMap<>();
        graph.put("http://a.com", Arrays.asList("http://a.com/1", "http://a.com/2"));
        graph.put("http://a.com/1", Arrays.asList("http://a.com/3"));
        graph.put("http://a.com/2", Arrays.asList("http://a.com/3"));
        graph.put("http://a.com/3", Collections.emptyList());
        return graph.getOrDefault(url, Collections.emptyList());
    }

    private String getHostname(String url) {
        return url.split("/")[2];
    }

    public List<String> crawl(String startUrl) {
        String hostname = getHostname(startUrl);
        ExecutorService executor = Executors.newFixedThreadPool(4);
        visited.add(startUrl);
        result.add(startUrl);
        CountDownLatch latch = new CountDownLatch(1);
        crawlHelper(startUrl, hostname, executor, latch);
        executor.shutdown();
        try { executor.awaitTermination(5, TimeUnit.SECONDS); } catch (InterruptedException e) {}
        return result;
    }

    private void crawlHelper(String url, String hostname, ExecutorService executor, CountDownLatch latch) {
        executor.submit(() -> {
            for (String next : getUrls(url)) {
                if (getHostname(next).equals(hostname) && visited.add(next)) {
                    result.add(next);
                    crawlHelper(next, hostname, executor, latch);
                }
            }
        });
    }

    public static void main(String[] args) {
        Problem08_WebCrawlerMultithreaded crawler = new Problem08_WebCrawlerMultithreaded();
        List<String> crawled = crawler.crawl("http://a.com");
        System.out.println("Crawled: " + crawled);
    }
}
