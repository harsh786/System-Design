import java.util.*;

/**
 * Problem 25: Remove Invalid Parentheses (LeetCode 301)
 * 
 * Remove minimum number of invalid parentheses to make input valid. Return all results.
 * 
 * Approach: BFS - try removing one parenthesis at each position. Level by level,
 * first level with valid strings is the answer (minimum removals).
 * 
 * Time Complexity: O(2^n) worst case
 * Space Complexity: O(2^n)
 * 
 * Production Analogy: Like finding minimum edits to fix malformed configuration files
 * while exploring all possible valid corrections.
 */
public class Problem25_RemoveInvalidParentheses {

    public static List<String> removeInvalidParentheses(String s) {
        List<String> result = new ArrayList<>();
        Set<String> visited = new HashSet<>();
        Queue<String> queue = new LinkedList<>();
        queue.offer(s);
        visited.add(s);
        boolean found = false;
        while (!queue.isEmpty()) {
            String curr = queue.poll();
            if (isValid(curr)) {
                result.add(curr);
                found = true;
            }
            if (found) continue; // only collect at this level
            for (int i = 0; i < curr.length(); i++) {
                if (curr.charAt(i) != '(' && curr.charAt(i) != ')') continue;
                String next = curr.substring(0, i) + curr.substring(i + 1);
                if (visited.add(next)) queue.offer(next);
            }
        }
        return result;
    }

    private static boolean isValid(String s) {
        int count = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') count++;
            else if (c == ')') count--;
            if (count < 0) return false;
        }
        return count == 0;
    }

    public static void main(String[] args) {
        System.out.println(removeInvalidParentheses("()())()")); // ["(())()","()()()"]
        System.out.println(removeInvalidParentheses("(a)())()")); // ["(a())()","(a)()()"]
        System.out.println(removeInvalidParentheses(")(")); // [""]
    }
}
