/**
 * Problem: Design Browser History (LeetCode 1472)
 * Approach: ArrayList with pointer tracking current position
 * Complexity: O(1) per operation
 * Production Analogy: Navigation history in web browsers with forward/back
 */
import java.util.*;
public class Problem23_DesignBrowserHistory {
    List<String> history = new ArrayList<>();
    int cur = 0;

    public Problem23_DesignBrowserHistory(String homepage) { history.add(homepage); }
    public void visit(String url) {
        while (history.size() > cur+1) history.remove(history.size()-1);
        history.add(url); cur++;
    }
    public String back(int steps) { cur = Math.max(0, cur-steps); return history.get(cur); }
    public String forward(int steps) { cur = Math.min(history.size()-1, cur+steps); return history.get(cur); }

    public static void main(String[] args) {
        Problem23_DesignBrowserHistory b = new Problem23_DesignBrowserHistory("leetcode.com");
        b.visit("google.com"); b.visit("facebook.com"); b.visit("youtube.com");
        System.out.println(b.back(1)); // facebook.com
        System.out.println(b.forward(1)); // youtube.com
    }
}
