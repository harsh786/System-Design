import java.util.*;

/**
 * Problem 15: Design Browser History
 * 
 * API Contract:
 * - visit(url): Visit URL, clear forward history
 * - back(steps): Go back up to steps pages
 * - forward(steps): Go forward up to steps pages
 * 
 * Complexity: O(1) for all operations with ArrayList approach
 * Data Structure: ArrayList + current index pointer
 * 
 * Production Analogy: Browser navigation, undo/redo systems,
 * text editor history, IDE navigation stack
 */
public class Problem15_DesignBrowserHistory {

    static class BrowserHistory {
        private List<String> history;
        private int current;

        public BrowserHistory(String homepage) {
            history = new ArrayList<>();
            history.add(homepage);
            current = 0;
        }

        public void visit(String url) {
            // Clear forward history
            while (history.size() > current + 1) history.remove(history.size() - 1);
            history.add(url);
            current++;
        }

        public String back(int steps) {
            current = Math.max(0, current - steps);
            return history.get(current);
        }

        public String forward(int steps) {
            current = Math.min(history.size() - 1, current + steps);
            return history.get(current);
        }
    }

    public static void main(String[] args) {
        BrowserHistory bh = new BrowserHistory("leetcode.com");
        bh.visit("google.com");
        bh.visit("facebook.com");
        bh.visit("youtube.com");
        assert bh.back(1).equals("facebook.com");
        assert bh.back(1).equals("google.com");
        assert bh.forward(1).equals("facebook.com");
        bh.visit("linkedin.com"); // clears forward
        assert bh.forward(2).equals("linkedin.com"); // can't go forward
        assert bh.back(2).equals("google.com");
        assert bh.back(7).equals("leetcode.com"); // clamped

        System.out.println("All tests passed!");
    }
}
