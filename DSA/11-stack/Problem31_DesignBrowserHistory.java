import java.util.*;

/**
 * Problem 31: Design Browser History (LeetCode 1472)
 * 
 * Implement browser history with visit, back, forward operations.
 * 
 * Approach: Two stacks - back stack and forward stack. Visit clears forward stack.
 * 
 * Time Complexity: O(1) visit, O(steps) back/forward
 * Space Complexity: O(n)
 * 
 * Production Analogy: Exactly the browser history pattern - also used in
 * undo/redo systems in text editors, IDEs, and design tools.
 */
public class Problem31_DesignBrowserHistory {

    static class BrowserHistory {
        Deque<String> backStack = new ArrayDeque<>();
        Deque<String> forwardStack = new ArrayDeque<>();
        String current;

        public BrowserHistory(String homepage) { current = homepage; }

        public void visit(String url) {
            backStack.push(current);
            current = url;
            forwardStack.clear();
        }

        public String back(int steps) {
            while (steps > 0 && !backStack.isEmpty()) {
                forwardStack.push(current);
                current = backStack.pop();
                steps--;
            }
            return current;
        }

        public String forward(int steps) {
            while (steps > 0 && !forwardStack.isEmpty()) {
                backStack.push(current);
                current = forwardStack.pop();
                steps--;
            }
            return current;
        }
    }

    public static void main(String[] args) {
        BrowserHistory bh = new BrowserHistory("leetcode.com");
        bh.visit("google.com");
        bh.visit("facebook.com");
        bh.visit("youtube.com");
        System.out.println(bh.back(1));    // facebook.com
        System.out.println(bh.back(1));    // google.com
        System.out.println(bh.forward(1)); // facebook.com
        bh.visit("linkedin.com");
        System.out.println(bh.forward(2)); // linkedin.com (no forward)
        System.out.println(bh.back(2));    // google.com
        System.out.println(bh.back(7));    // leetcode.com
    }
}
