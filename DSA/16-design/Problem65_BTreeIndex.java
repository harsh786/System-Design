import java.util.*;

/**
 * Problem 65: B-Tree Index (Insert, Split, Search)
 * 
 * PRODUCTION MAPPING: PostgreSQL/MySQL indexes, filesystem metadata (NTFS, HFS+, ext4),
 *                     SQLite, MongoDB WiredTiger, Oracle B*Tree
 * 
 * Properties:
 * - All leaves at same depth (perfectly balanced)
 * - Node can hold t-1 to 2t-1 keys (t = minimum degree)
 * - Internal nodes have between t and 2t children
 * - O(log n) search, insert, delete
 * - Optimized for disk: wide nodes = fewer I/Os
 * 
 * Why B-Trees for databases (not BST/Red-Black):
 * - Disk I/O is the bottleneck, not CPU
 * - B-Tree node = 1 disk page (4-16KB)
 * - Branching factor 100-1000 = tree depth 3-4 for billions of keys
 * - Sequential access within page = cache-friendly
 * 
 * This implementation: B-Tree of order 2t (minimum degree t)
 */
public class Problem65_BTreeIndex {

    static class BTree {
        private final int t; // minimum degree (each node has at least t-1 keys)
        private Node root;

        static class Node {
            int[] keys;
            Node[] children;
            int numKeys;
            boolean leaf;

            Node(int t, boolean leaf) {
                this.keys = new int[2 * t - 1];
                this.children = new Node[2 * t];
                this.numKeys = 0;
                this.leaf = leaf;
            }
        }

        public BTree(int t) {
            this.t = t;
            this.root = new Node(t, true);
        }

        // ---- Search ----
        public boolean search(int key) {
            return search(root, key);
        }

        private boolean search(Node node, int key) {
            int i = 0;
            while (i < node.numKeys && key > node.keys[i]) i++;

            if (i < node.numKeys && node.keys[i] == key) return true;
            if (node.leaf) return false;
            return search(node.children[i], key);
        }

        // ---- Insert ----
        public void insert(int key) {
            if (root.numKeys == 2 * t - 1) {
                // Root is full, split it
                Node newRoot = new Node(t, false);
                newRoot.children[0] = root;
                splitChild(newRoot, 0);
                root = newRoot;
            }
            insertNonFull(root, key);
        }

        private void insertNonFull(Node node, int key) {
            int i = node.numKeys - 1;

            if (node.leaf) {
                // Shift keys and insert
                while (i >= 0 && node.keys[i] > key) {
                    node.keys[i + 1] = node.keys[i];
                    i--;
                }
                node.keys[i + 1] = key;
                node.numKeys++;
            } else {
                // Find child to descend into
                while (i >= 0 && node.keys[i] > key) i--;
                i++;
                // If child is full, split first
                if (node.children[i].numKeys == 2 * t - 1) {
                    splitChild(node, i);
                    if (key > node.keys[i]) i++;
                }
                insertNonFull(node.children[i], key);
            }
        }

        /**
         * Split the i-th child of parent (which must be full).
         * The median key moves up to parent.
         */
        private void splitChild(Node parent, int i) {
            Node fullChild = parent.children[i];
            Node newNode = new Node(t, fullChild.leaf);
            newNode.numKeys = t - 1;

            // Copy right half of keys to new node
            for (int j = 0; j < t - 1; j++) {
                newNode.keys[j] = fullChild.keys[j + t];
            }
            if (!fullChild.leaf) {
                for (int j = 0; j < t; j++) {
                    newNode.children[j] = fullChild.children[j + t];
                }
            }
            fullChild.numKeys = t - 1;

            // Make room in parent for new child and key
            for (int j = parent.numKeys; j > i; j--) {
                parent.children[j + 1] = parent.children[j];
            }
            parent.children[i + 1] = newNode;

            for (int j = parent.numKeys - 1; j >= i; j--) {
                parent.keys[j + 1] = parent.keys[j];
            }
            parent.keys[i] = fullChild.keys[t - 1]; // median moves up
            parent.numKeys++;
        }

        // ---- Range Query ----
        public List<Integer> rangeQuery(int low, int high) {
            List<Integer> result = new ArrayList<>();
            rangeQuery(root, low, high, result);
            return result;
        }

        private void rangeQuery(Node node, int low, int high, List<Integer> result) {
            int i = 0;
            while (i < node.numKeys && node.keys[i] < low) i++;

            while (i < node.numKeys && node.keys[i] <= high) {
                if (!node.leaf) rangeQuery(node.children[i], low, high, result);
                result.add(node.keys[i]);
                i++;
            }
            if (!node.leaf) rangeQuery(node.children[i], low, high, result);
        }

        // ---- Utilities ----
        public int height() { return height(root); }
        private int height(Node node) {
            if (node.leaf) return 1;
            return 1 + height(node.children[0]);
        }

        public int countKeys() { return countKeys(root); }
        private int countKeys(Node node) {
            int count = node.numKeys;
            if (!node.leaf) {
                for (int i = 0; i <= node.numKeys; i++) {
                    count += countKeys(node.children[i]);
                }
            }
            return count;
        }

        // In-order traversal
        public List<Integer> inOrder() {
            List<Integer> result = new ArrayList<>();
            inOrder(root, result);
            return result;
        }
        private void inOrder(Node node, List<Integer> result) {
            for (int i = 0; i < node.numKeys; i++) {
                if (!node.leaf) inOrder(node.children[i], result);
                result.add(node.keys[i]);
            }
            if (!node.leaf) inOrder(node.children[node.numKeys], result);
        }
    }

    public static void main(String[] args) {
        System.out.println("=== B-Tree Index ===\n");

        // Test 1: Basic insert and search
        BTree tree = new BTree(3); // min degree 3: nodes hold 2-5 keys
        int[] keys = {10, 20, 5, 6, 12, 30, 7, 17};
        for (int k : keys) tree.insert(k);

        for (int k : keys) {
            assert tree.search(k) : "Should find " + k;
        }
        assert !tree.search(99);
        assert !tree.search(0);
        System.out.println("PASS: Insert and search for " + keys.length + " keys");

        // Test 2: Sorted order maintained
        List<Integer> sorted = tree.inOrder();
        for (int i = 1; i < sorted.size(); i++) {
            assert sorted.get(i) > sorted.get(i-1) : "Not sorted!";
        }
        System.out.println("PASS: In-order traversal is sorted: " + sorted);

        // Test 3: Large insertion with split
        tree = new BTree(3);
        for (int i = 1; i <= 100; i++) tree.insert(i);
        assert tree.countKeys() == 100;
        assert tree.search(1) && tree.search(50) && tree.search(100);
        assert !tree.search(101);
        System.out.printf("PASS: 100 sequential inserts, height=%d\n", tree.height());

        // Test 4: Height is logarithmic
        tree = new BTree(50); // high branching factor (like real DB)
        for (int i = 0; i < 10000; i++) tree.insert(i);
        int height = tree.height();
        System.out.printf("PASS: 10000 keys with t=50, height=%d (max branch=100)\n", height);
        assert height <= 4 : "Height should be small with high branching factor";

        // Test 5: Range query
        tree = new BTree(3);
        for (int i = 0; i < 50; i++) tree.insert(i * 2); // even numbers 0-98
        List<Integer> range = tree.rangeQuery(20, 40);
        System.out.println("PASS: Range [20,40] = " + range);
        assert range.size() == 11; // 20,22,24,...,40
        assert range.get(0) == 20 && range.get(range.size()-1) == 40;

        // Test 6: Random insertions
        tree = new BTree(4);
        Random rng = new Random(42);
        Set<Integer> inserted = new HashSet<>();
        for (int i = 0; i < 1000; i++) {
            int val = rng.nextInt(10000);
            tree.insert(val);
            inserted.add(val);
        }
        for (int val : inserted) {
            assert tree.search(val) : "Missing: " + val;
        }
        sorted = tree.inOrder();
        for (int i = 1; i < sorted.size(); i++) {
            assert sorted.get(i) >= sorted.get(i-1);
        }
        System.out.printf("PASS: %d random keys, all found, sorted, height=%d\n", 
            inserted.size(), tree.height());

        // Test 7: Disk I/O comparison
        int n = 1000000;
        int bstHeight = (int)(Math.log(n) / Math.log(2)); // ~20
        int btreeHeight = (int)(Math.log(n) / Math.log(200)); // ~3 with t=100
        System.out.printf("\nFor %d keys:\n", n);
        System.out.printf("  BST height (disk I/Os): ~%d\n", bstHeight);
        System.out.printf("  B-Tree height (t=100): ~%d\n", btreeHeight);
        System.out.printf("  Speedup: %.0fx fewer disk reads\n", (double)bstHeight / btreeHeight);

        System.out.println("\nAll tests passed!");
    }
}
