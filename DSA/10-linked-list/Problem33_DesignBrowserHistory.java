/**
 * Problem 33: Design Browser History
 * 
 * Approach: Doubly linked list. Visit creates new node, truncates forward history.
 * Time Complexity: O(steps) for back/forward, O(1) for visit
 * Space Complexity: O(n)
 * 
 * Production Analogy: Browser tab navigation - each page is a node, back/forward
 * traverse the history chain, new navigation truncates forward stack.
 */
public class Problem33_DesignBrowserHistory {
    static class Node {
        String url;
        Node prev, next;
        Node(String url) { this.url = url; }
    }

    static class BrowserHistory {
        Node curr;

        public BrowserHistory(String homepage) { curr = new Node(homepage); }

        public void visit(String url) {
            Node node = new Node(url);
            curr.next = node;
            node.prev = curr;
            curr = node;
        }

        public String back(int steps) {
            while (steps > 0 && curr.prev != null) { curr = curr.prev; steps--; }
            return curr.url;
        }

        public String forward(int steps) {
            while (steps > 0 && curr.next != null) { curr = curr.next; steps--; }
            return curr.url;
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
        System.out.println(bh.forward(2)); // linkedin.com (can't go forward)
        System.out.println(bh.back(2));    // google.com
        System.out.println(bh.back(7));    // leetcode.com
    }
}
