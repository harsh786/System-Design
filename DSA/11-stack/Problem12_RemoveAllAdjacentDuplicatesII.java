import java.util.*;

/**
 * Problem 12: Remove All Adjacent Duplicates in String II (LeetCode 1209)
 * 
 * Remove k adjacent duplicates repeatedly until no more can be removed.
 * 
 * Approach: Stack of pairs (character, count). When top char matches current and
 * count reaches k, pop it off.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like deduplication in log aggregation - when k identical
 * events arrive consecutively, they collapse into a single summary event.
 */
public class Problem12_RemoveAllAdjacentDuplicatesII {

    public static String removeDuplicates(String s, int k) {
        Deque<int[]> stack = new ArrayDeque<>(); // [char, count]
        for (char c : s.toCharArray()) {
            if (!stack.isEmpty() && stack.peek()[0] == c) {
                stack.peek()[1]++;
                if (stack.peek()[1] == k) stack.pop();
            } else {
                stack.push(new int[]{c, 1});
            }
        }
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) {
            int[] pair = stack.pollLast();
            for (int i = 0; i < pair[1]; i++) sb.append((char) pair[0]);
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(removeDuplicates("abcd", 2));       // abcd
        System.out.println(removeDuplicates("deeedbbcccbdaa", 3)); // aa
        System.out.println(removeDuplicates("pbbcggttciiippooaais", 2)); // ps
    }
}
