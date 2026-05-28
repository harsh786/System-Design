/**
 * Problem 20: Flatten a Multilevel Doubly Linked List
 * 
 * Approach: DFS - when encountering child, flatten child list and insert between
 * current and next. Use stack or recursion.
 * Time Complexity: O(n)
 * Space Complexity: O(n) for stack depth
 * 
 * Production Analogy: Flattening nested comment threads into a single feed view.
 */
public class Problem20_FlattenMultilevelDoublyLinkedList {
    static class Node {
        int val;
        Node prev, next, child;
        Node(int val) { this.val = val; }
    }

    public static Node flatten(Node head) {
        Node curr = head;
        while (curr != null) {
            if (curr.child != null) {
                Node child = curr.child;
                Node childTail = child;
                while (childTail.next != null) childTail = childTail.next;
                Node next = curr.next;
                curr.next = child;
                child.prev = curr;
                curr.child = null;
                childTail.next = next;
                if (next != null) next.prev = childTail;
            }
            curr = curr.next;
        }
        return head;
    }

    static String toString(Node h) {
        StringBuilder sb = new StringBuilder();
        while (h != null) { sb.append(h.val).append("->"); h = h.next; }
        sb.append("null"); return sb.toString();
    }

    public static void main(String[] args) {
        // 1-2-3-4-5-6 with 3 having child 7-8-9 and 8 having child 11-12
        Node n1=new Node(1),n2=new Node(2),n3=new Node(3),n4=new Node(4),n5=new Node(5),n6=new Node(6);
        Node n7=new Node(7),n8=new Node(8),n9=new Node(9),n11=new Node(11),n12=new Node(12);
        n1.next=n2;n2.prev=n1;n2.next=n3;n3.prev=n2;n3.next=n4;n4.prev=n3;n4.next=n5;n5.prev=n4;n5.next=n6;n6.prev=n5;
        n7.next=n8;n8.prev=n7;n8.next=n9;n9.prev=n8;
        n11.next=n12;n12.prev=n11;
        n3.child=n7; n8.child=n11;
        System.out.println("Test1: " + toString(flatten(n1)));
        // 1->2->3->7->8->11->12->9->4->5->6->null
    }
}
