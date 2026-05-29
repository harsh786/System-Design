import java.util.*;

public class Problem39_FlattenMultilevelDLLIterator implements Iterator<Integer> {
    static class Node { int val; Node prev, next, child; Node(int v){val=v;} }

    Deque<Node> stack = new ArrayDeque<>();

    public Problem39_FlattenMultilevelDLLIterator(Node head) { if (head != null) stack.push(head); }

    public boolean hasNext() { return !stack.isEmpty(); }

    public Integer next() {
        Node node = stack.pop();
        if (node.next != null) stack.push(node.next);
        if (node.child != null) stack.push(node.child);
        return node.val;
    }

    public static void main(String[] args) {
        Node n1 = new Node(1), n2 = new Node(2), n3 = new Node(3);
        Node c1 = new Node(4), c2 = new Node(5);
        n1.next = n2; n2.next = n3;
        n2.child = c1; c1.next = c2;
        Problem39_FlattenMultilevelDLLIterator it = new Problem39_FlattenMultilevelDLLIterator(n1);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 1 4 5 2 3 (DFS order with child first)
    }
}
