import java.util.*;

/**
 * Problem 37: Combination Iterator (LeetCode 1286)
 * 
 * Design an iterator that generates combinations of length k from sorted string characters.
 * 
 * Search Tree:
 * - Pre-generate all combinations using backtracking
 * - Store in a queue/list for iteration
 * 
 * Pruning Strategy:
 * - Same as Combinations: start index ensures no duplicates
 * - Generated in lexicographic order naturally since input is sorted
 * 
 * Time Complexity: O(C(n,k) * k) for initialization
 * Space Complexity: O(C(n,k) * k)
 * 
 * Production Analogy:
 * - Paginated enumeration of configurations for A/B testing frameworks.
 */
public class Problem37_CombinationIterator {

    private Queue<String> queue;

    public Problem37_CombinationIterator() {
        queue = new LinkedList<>();
    }

    public void init(String characters, int combinationLength) {
        queue = new LinkedList<>();
        generate(characters, combinationLength, 0, new StringBuilder());
    }

    private void generate(String chars, int k, int start, StringBuilder sb) {
        if (sb.length() == k) {
            queue.offer(sb.toString());
            return;
        }
        for (int i = start; i <= chars.length() - (k - sb.length()); i++) {
            sb.append(chars.charAt(i));
            generate(chars, k, i + 1, sb);
            sb.deleteCharAt(sb.length() - 1);
        }
    }

    public String next() { return queue.poll(); }
    public boolean hasNext() { return !queue.isEmpty(); }

    public static void main(String[] args) {
        Problem37_CombinationIterator iter = new Problem37_CombinationIterator();
        iter.init("abc", 2);

        System.out.println(iter.next());    // "ab"
        System.out.println(iter.hasNext()); // true
        System.out.println(iter.next());    // "ac"
        System.out.println(iter.hasNext()); // true
        System.out.println(iter.next());    // "bc"
        System.out.println(iter.hasNext()); // false

        iter.init("abcde", 3);
        while (iter.hasNext()) System.out.print(iter.next() + " ");
        System.out.println();
    }
}
