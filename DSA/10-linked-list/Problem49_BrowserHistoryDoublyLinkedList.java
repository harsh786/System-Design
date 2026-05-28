/**
 * Problem 49: Browser History with Doubly Linked List
 * (More detailed implementation with page tracking)
 * 
 * Approach: DLL with current pointer. Visit truncates forward, back/forward navigate.
 * Time Complexity: O(1) visit, O(steps) for back/forward
 * Space Complexity: O(n)
 * 
 * Production Analogy: Undo/redo system in a collaborative editor where each
 * edit creates a node, branching truncates the redo stack.
 */
public class Problem49_BrowserHistoryDoublyLinkedList {
    static class Node {
        String url;
        Node prev, next;
        Node(String u) { url = u; }
    }

    static class BrowserHistory {
        Node curr;
        int backCount, forwardCount;

        public BrowserHistory(String homepage) { curr = new Node(homepage); }

        public void visit(String url) {
            Node node = new Node(url);
            curr.next = node;
            node.prev = curr;
            curr = node;
            forwardCount = 0;
        }

        public String back(int steps) {
            while (steps > 0 && curr.prev != null) { curr = curr.prev; steps--; }
            return curr.url;
        }

        public String forward(int steps) {
            while (steps > 0 && curr.next != null) { curr = curr.next; steps--; }
            return curr.url;
        }

        public String current() { return curr.url; }
    }

    public static void main(String[] args) {
        BrowserHistory bh = new BrowserHistory("home.com");
        bh.visit("a.com"); bh.visit("b.com"); bh.visit("c.com");
        System.out.println(bh.back(1));    // b.com
        System.out.println(bh.back(1));    // a.com
        System.out.println(bh.forward(1)); // b.com
        bh.visit("d.com");                 // truncates c.com
        System.out.println(bh.forward(1)); // d.com (can't go forward)
        System.out.println(bh.back(2));    // a.com
        System.out.println(bh.back(10));   // home.com
    }
}
