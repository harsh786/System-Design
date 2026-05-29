import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem43_CompletableFuturePipeline {
    /**
     * Problem: CompletableFuture Pipeline
     * Chain async operations using CompletableFuture.
     * Time: depends on pipeline stages | Space: O(1)
     * Production Analogy: Microservice orchestration - call service A, then B with result, then C.
     */
    static CompletableFuture<String> fetchUser(int id) {
        return CompletableFuture.supplyAsync(() -> { sleep(100); return "User-" + id; });
    }

    static CompletableFuture<String> fetchOrders(String user) {
        return CompletableFuture.supplyAsync(() -> { sleep(100); return user + "-Orders[3]"; });
    }

    static CompletableFuture<String> enrichWithRecommendations(String orders) {
        return CompletableFuture.supplyAsync(() -> { sleep(50); return orders + "+Recs"; });
    }

    static void sleep(long ms) { try { Thread.sleep(ms); } catch (InterruptedException e) {} }

    public static void main(String[] args) throws Exception {
        // Sequential pipeline
        String result = fetchUser(1)
            .thenCompose(user -> fetchOrders(user))
            .thenCompose(orders -> enrichWithRecommendations(orders))
            .get();
        System.out.println("Pipeline result: " + result);

        // Parallel fan-out
        CompletableFuture<String> f1 = fetchUser(1);
        CompletableFuture<String> f2 = fetchUser(2);
        CompletableFuture<Void> all = CompletableFuture.allOf(f1, f2);
        all.get();
        System.out.println("Parallel: " + f1.get() + ", " + f2.get());
    }
}
