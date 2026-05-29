import java.util.*;

public class Problem04_DesignBrowserHistory {
    static class Node { String url; Node prev, next; Node(String u){url=u;} }
    Node cur;
    
    Problem04_DesignBrowserHistory(String homepage) { cur = new Node(homepage); }
    void visit(String url) { Node n = new Node(url); cur.next = n; n.prev = cur; cur = n; }
    String back(int steps) { while (steps-- > 0 && cur.prev != null) cur = cur.prev; return cur.url; }
    String forward(int steps) { while (steps-- > 0 && cur.next != null) cur = cur.next; return cur.url; }
    
    public static void main(String[] args) {
        Problem04_DesignBrowserHistory b = new Problem04_DesignBrowserHistory("home");
        b.visit("a"); b.visit("b"); b.visit("c");
        System.out.println(b.back(1)); // b
        System.out.println(b.forward(1)); // c
        b.visit("d");
        System.out.println(b.back(3)); // home
    }
}
