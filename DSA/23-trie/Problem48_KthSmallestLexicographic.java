/**
 * Problem 48: K-th Smallest in Lexicographic Order
 * 
 * Given n and k, find the k-th smallest number in lexicographic order among [1..n].
 * Uses a virtual trie (denary/10-ary trie) without actually building it.
 * 
 * Time Complexity: O(log(n)^2) 
 * Space Complexity: O(1)
 * 
 * Production Analogy: Pagination in sorted datasets, database OFFSET queries optimization,
 * file explorer sorted listing, lexicographic cursor-based pagination.
 */
public class Problem48_KthSmallestLexicographic {

    public static int findKthNumber(int n, int k) {
        int curr = 1;
        k--; // curr=1 is the first number
        while (k > 0) {
            long steps = countSteps(n, curr, curr + 1);
            if (steps <= k) {
                // Skip entire subtree rooted at curr
                k -= steps;
                curr++;
            } else {
                // Go deeper into subtree
                k--;
                curr *= 10;
            }
        }
        return curr;
    }

    // Count numbers in [curr, next) that are <= n in the virtual trie
    static long countSteps(int n, long curr, long next) {
        long steps = 0;
        while (curr <= n) {
            steps += Math.min(n + 1, next) - curr;
            curr *= 10;
            next *= 10;
        }
        return steps;
    }

    public static void main(String[] args) {
        System.out.println(findKthNumber(13, 2));  // 10 (1,10,11,12,13,2,3,...) -> 2nd is 10
        System.out.println(findKthNumber(1, 1));   // 1
        System.out.println(findKthNumber(100, 10));// 17 (1,10,100,11,12,13,14,15,16,17)
        System.out.println(findKthNumber(681692778, 351251360)); // large test
    }
}
