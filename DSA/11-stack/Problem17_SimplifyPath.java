import java.util.*;

/**
 * Problem 17: Simplify Path (LeetCode 71)
 * 
 * Given absolute Unix path, simplify it (handle ., .., multiple slashes).
 * 
 * Approach: Split by '/', use deque as stack. Push valid dirs, pop for '..'.
 * 
 * Time Complexity: O(n)
 * Space Complexity: O(n)
 * 
 * Production Analogy: Like URL path normalization in web servers/reverse proxies
 * to prevent path traversal attacks and normalize routes for caching.
 */
public class Problem17_SimplifyPath {

    public static String simplifyPath(String path) {
        Deque<String> stack = new ArrayDeque<>();
        for (String part : path.split("/")) {
            if (part.equals("..")) {
                if (!stack.isEmpty()) stack.pop();
            } else if (!part.isEmpty() && !part.equals(".")) {
                stack.push(part);
            }
        }
        StringBuilder sb = new StringBuilder();
        while (!stack.isEmpty()) {
            sb.insert(0, "/" + stack.pop());
        }
        return sb.length() == 0 ? "/" : sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(simplifyPath("/home/"));          // /home
        System.out.println(simplifyPath("/../"));            // /
        System.out.println(simplifyPath("/home//foo/"));     // /home/foo
        System.out.println(simplifyPath("/a/./b/../../c/")); // /c
        System.out.println(simplifyPath("/a/b/../c"));       // /a/c
    }
}
