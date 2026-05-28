import java.util.*;

/**
 * Problem 20: Simplify Path (LeetCode 71)
 * 
 * Approach: Split by '/', use stack. Skip "." and "", pop for "..". O(n) time, O(n) space.
 * 
 * Production Analogy: Like URL path normalization in a web server/reverse proxy.
 */
public class Problem20_SimplifyPath {

    public static String simplifyPath(String path) {
        Deque<String> stack = new ArrayDeque<>();
        for (String part : path.split("/")) {
            if (part.equals("..")) { if (!stack.isEmpty()) stack.pop(); }
            else if (!part.isEmpty() && !part.equals(".")) stack.push(part);
        }
        StringBuilder sb = new StringBuilder();
        for (String s : stack) sb.insert(0, "/" + s);
        return sb.length() == 0 ? "/" : sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(simplifyPath("/home/"));           // "/home"
        System.out.println(simplifyPath("/../"));             // "/"
        System.out.println(simplifyPath("/home//foo/"));      // "/home/foo"
        System.out.println(simplifyPath("/a/./b/../../c/"));  // "/c"
    }
}
