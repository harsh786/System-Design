import java.util.*;

/**
 * Problem 21: Maximum Genetic Difference Query
 * 
 * Given a rooted tree, answer queries: for node x with value val, find maximum XOR
 * of val with any ancestor value (including x itself).
 * Use binary trie with DFS (add on enter, remove on exit).
 * 
 * Time Complexity: O((n + q) * 18) where 18 = max bits
 * Space Complexity: O(n * 18)
 * 
 * Production Analogy: Hierarchical access control (finding max privilege difference),
 * network topology analysis, genetic sequence comparison in bioinformatics.
 */
public class Problem21_MaxGeneticDifferenceQuery {

    static final int BITS = 18;

    static class TrieNode {
        TrieNode[] children = new TrieNode[2];
        int count = 0;
    }

    static TrieNode root = new TrieNode();

    static void add(int num) {
        TrieNode node = root;
        for (int i = BITS - 1; i >= 0; i--) {
            int bit = (num >> i) & 1;
            if (node.children[bit] == null) node.children[bit] = new TrieNode();
            node = node.children[bit];
            node.count++;
        }
    }

    static void remove(int num) {
        TrieNode node = root;
        for (int i = BITS - 1; i >= 0; i--) {
            int bit = (num >> i) & 1;
            node = node.children[bit];
            node.count--;
        }
    }

    static int maxXor(int num) {
        TrieNode node = root;
        int xor = 0;
        for (int i = BITS - 1; i >= 0; i--) {
            int bit = (num >> i) & 1;
            int want = 1 - bit;
            if (node.children[want] != null && node.children[want].count > 0) {
                xor |= (1 << i);
                node = node.children[want];
            } else {
                node = node.children[bit];
            }
        }
        return xor;
    }

    public static int[] maxGeneticDifference(int[] parents, int[][] queries) {
        int n = parents.length;
        List<int[]>[] queryMap = new List[n];
        List<Integer>[] children = new List[n];
        for (int i = 0; i < n; i++) { queryMap[i] = new ArrayList<>(); children[i] = new ArrayList<>(); }

        int rootNode = -1;
        for (int i = 0; i < n; i++) {
            if (parents[i] == -1) rootNode = i;
            else children[parents[i]].add(i);
        }
        for (int i = 0; i < queries.length; i++) queryMap[queries[i][0]].add(new int[]{queries[i][1], i});

        int[] ans = new int[queries.length];
        root = new TrieNode();
        dfs(rootNode, children, queryMap, ans);
        return ans;
    }

    static void dfs(int node, List<Integer>[] children, List<int[]>[] queryMap, int[] ans) {
        add(node);
        for (int[] q : queryMap[node]) ans[q[1]] = maxXor(q[0]);
        for (int child : children[node]) dfs(child, children, queryMap, ans);
        remove(node);
    }

    public static void main(String[] args) {
        int[] parents = {-1, 0, 0, 2, 2};
        int[][] queries = {{0, 2}, {3, 2}, {2, 5}};
        System.out.println(Arrays.toString(maxGeneticDifference(parents, queries)));
        // [2, 3, 7]
    }
}
