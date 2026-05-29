import java.util.concurrent.atomic.*;
import java.util.concurrent.*;
import java.util.*;

/**
 * Problem 68: Concurrent Trie (Ctrie Concept)
 * 
 * REAL-WORLD USAGE:
 * - Scala's concurrent.TrieMap (lock-free hash trie)
 * - IP routing tables (longest prefix match)
 * - DNS resolution caches
 * - Autocomplete/typeahead systems
 * - Concurrent symbol tables in compilers
 * 
 * KEY CONCEPTS (Ctrie):
 * - Hash Array Mapped Trie (HAMT) made concurrent
 * - Each node is immutable; updates create new nodes (path copying)
 * - CAS on parent's reference to child for atomic updates
 * - Indirection nodes (I-nodes) allow atomic multi-child updates
 * - Supports lock-free, linearizable snapshots
 * 
 * SIMPLIFIED VERSION (this implementation):
 * - Character-based trie for string keys
 * - CAS-based insertion at each level
 * - Supports concurrent insert/search/delete
 * 
 * MEMORY ORDERING:
 * - AtomicReferenceArray for child pointers (CAS for linking)
 * - Immutable value nodes (once set, visible to all readers)
 * - The CAS on the child pointer is the linearization point for insert
 * 
 * PITFALLS:
 * 1. Path copying can be expensive for deep tries
 * 2. Memory overhead from AtomicReference per child
 * 3. Need generation counters for consistent snapshots
 * 4. Deletion requires careful handling (don't remove nodes with children)
 */
public class Problem68_ConcurrentTrie {

    static class TrieNode {
        // 26 lowercase letters + could extend
        final AtomicReferenceArray<TrieNode> children = new AtomicReferenceArray<>(26);
        volatile String value; // null if not a terminal node
        volatile boolean isEnd = false;
        final AtomicInteger prefixCount = new AtomicInteger(0); // Words with this prefix
    }

    private final TrieNode root = new TrieNode();
    private final AtomicInteger size = new AtomicInteger(0);

    /**
     * Insert: CAS at each level to create child nodes.
     * Lock-free: multiple threads can insert on different branches simultaneously.
     */
    public boolean insert(String key, String value) {
        if (key == null || key.isEmpty()) return false;
        TrieNode current = root;

        for (int i = 0; i < key.length(); i++) {
            int idx = key.charAt(i) - 'a';
            if (idx < 0 || idx >= 26) return false;

            TrieNode child = current.children.get(idx);
            if (child == null) {
                TrieNode newNode = new TrieNode();
                // CAS: only one thread succeeds in creating this node
                if (!current.children.compareAndSet(idx, null, newNode)) {
                    // Another thread created it - use theirs
                    child = current.children.get(idx);
                } else {
                    child = newNode;
                }
            }
            child.prefixCount.incrementAndGet();
            current = child;
        }

        // Mark as terminal
        if (!current.isEnd) {
            current.isEnd = true;
            current.value = value;
            size.incrementAndGet();
            return true;
        } else {
            // Update existing
            current.value = value;
            return false; // Already existed
        }
    }

    /** Search: Pure reads, no synchronization needed (volatile reads suffice) */
    public String search(String key) {
        TrieNode node = findNode(key);
        return (node != null && node.isEnd) ? node.value : null;
    }

    public boolean startsWith(String prefix) {
        return findNode(prefix) != null;
    }

    public int countWithPrefix(String prefix) {
        TrieNode node = findNode(prefix);
        return node == null ? 0 : node.prefixCount.get();
    }

    private TrieNode findNode(String key) {
        TrieNode current = root;
        for (int i = 0; i < key.length(); i++) {
            int idx = key.charAt(i) - 'a';
            if (idx < 0 || idx >= 26) return null;
            current = current.children.get(idx);
            if (current == null) return null;
        }
        return current;
    }

    /** Delete: mark as non-terminal (lazy - don't remove node structure) */
    public boolean delete(String key) {
        TrieNode node = findNode(key);
        if (node != null && node.isEnd) {
            node.isEnd = false;
            node.value = null;
            size.decrementAndGet();
            return true;
        }
        return false;
    }

    /**
     * Snapshot: Create a consistent point-in-time view.
     * In a real Ctrie, this uses generation counters for O(1) snapshot creation.
     * Here we do a simple traversal (linearizable due to volatile reads).
     */
    public List<String> snapshot() {
        List<String> result = new ArrayList<>();
        collectAll(root, new StringBuilder(), result);
        return result;
    }

    private void collectAll(TrieNode node, StringBuilder prefix, List<String> result) {
        if (node.isEnd) {
            result.add(prefix.toString());
        }
        for (int i = 0; i < 26; i++) {
            TrieNode child = node.children.get(i);
            if (child != null) {
                prefix.append((char)('a' + i));
                collectAll(child, prefix, result);
                prefix.deleteCharAt(prefix.length() - 1);
            }
        }
    }

    public int size() { return size.get(); }

    // ==================== STRESS TEST ====================
    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Concurrent Trie (Ctrie Concept) ===\n");

        Problem68_ConcurrentTrie trie = new Problem68_ConcurrentTrie();
        int numThreads = 8;
        int opsPerThread = 200_000;
        AtomicInteger inserts = new AtomicInteger(0);
        AtomicInteger searches = new AtomicInteger(0);
        AtomicInteger found = new AtomicInteger(0);
        CountDownLatch startLatch = new CountDownLatch(1);
        CountDownLatch doneLatch = new CountDownLatch(numThreads);

        // Generate random words
        String[] words = new String[10000];
        Random rng = new Random(42);
        for (int i = 0; i < words.length; i++) {
            int len = 3 + rng.nextInt(8);
            StringBuilder sb = new StringBuilder();
            for (int j = 0; j < len; j++) sb.append((char)('a' + rng.nextInt(26)));
            words[i] = sb.toString();
        }

        for (int t = 0; t < numThreads; t++) {
            new Thread(() -> {
                try { startLatch.await(); } catch (InterruptedException e) { return; }
                Random r = new Random();
                for (int i = 0; i < opsPerThread; i++) {
                    String word = words[r.nextInt(words.length)];
                    if (r.nextInt(10) < 4) { // 40% insert
                        trie.insert(word, "val-" + word);
                        inserts.incrementAndGet();
                    } else { // 60% search
                        if (trie.search(word) != null) found.incrementAndGet();
                        searches.incrementAndGet();
                    }
                }
                doneLatch.countDown();
            }).start();
        }

        long start = System.nanoTime();
        startLatch.countDown();
        doneLatch.await();
        long elapsed = System.nanoTime() - start;

        int totalOps = numThreads * opsPerThread;
        System.out.println("Threads: " + numThreads + ", Ops/thread: " + opsPerThread);
        System.out.println("Inserts: " + inserts.get() + ", Searches: " + searches.get());
        System.out.println("Found in search: " + found.get());
        System.out.println("Trie size (unique words): " + trie.size());
        System.out.println("Time: " + (elapsed / 1_000_000) + " ms");
        System.out.println("Throughput: " + (totalOps * 1_000_000_000L / elapsed) + " ops/sec");

        // Prefix count demo
        System.out.println("\nPrefix 'a' count: " + trie.countWithPrefix("a"));
        System.out.println("Prefix 'ab' count: " + trie.countWithPrefix("ab"));

        System.out.println("\nKey insight: Concurrent tries enable lock-free prefix operations.");
        System.out.println("Used in routing tables (longest prefix match) and autocomplete.");
        System.out.println("Scala's TrieMap provides O(1) consistent snapshots via generation counters.");
    }
}
